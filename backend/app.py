from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify
from flask_cors import CORS
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from groq import Groq
from langgraph.graph import StateGraph, END
from typing import TypedDict
from rank_bm25 import BM25Okapi
import groq
import json
import time
import os
import re
import shutil
import tempfile
import uuid
from loaders import load_file, file_kind
import tables

app = Flask(__name__)
CORS(app)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
# Smaller, faster model: used for easy jobs (routing) and as a fallback when MODEL is busy
FAST_MODEL = os.getenv("GROQ_FAST_MODEL", "openai/gpt-oss-20b")
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Everything Sage stores lives in backend/data (ignored by Git):
#   data/chroma/          ChromaDB: one collection of chunks per uploaded document
#   data/docs/<id>.json   the document's name, type and text sections (for summary/overview)
#   data/tables/<id>.csv  a copy of each uploaded CSV, for exact table queries
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma")
DOCS_DIR = os.path.join(DATA_DIR, "docs")
TABLES_DIR = os.path.join(DATA_DIR, "tables")
os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)

# Set DEBUG_RETRIEVAL=1 in .env to print routing and search details in the terminal
DEBUG_RETRIEVAL = os.getenv("DEBUG_RETRIEVAL") == "1"

def debug(message):
    if DEBUG_RETRIEVAL:
        print(message)

# Common words that carry no meaning for keyword search
STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "by", "with", "and", "or",
    "is", "are", "was", "were", "be", "been", "do", "does", "did", "what", "which",
    "who", "whom", "how", "why", "when", "where", "this", "that", "these", "those",
    "it", "its", "they", "their", "them", "we", "our", "you", "your", "i", "me", "my",
    "can", "could", "would", "should", "much", "many", "used", "use", "from", "as",
    "about", "into", "than", "then", "there", "set", "paper",
}

def tokenize(text):
    """Lowercase words for BM25. 'd_model' also adds 'dmodel', matching how PDFs often extract it."""
    tokens = []
    for word in re.findall(r"[a-z0-9_]+", text.lower()):
        parts = [p for p in word.split("_") if p]
        if len(parts) > 1:
            tokens.append("".join(parts))
        tokens.extend(parts)
    return [t for t in tokens if t not in STOPWORDS]


# ---------- Document storage ----------

_cache = {}  # doc_id -> loaded document (vector store, BM25 index, chunks, sections)

def is_valid_doc_id(doc_id):
    return isinstance(doc_id, str) and re.fullmatch(r"[0-9a-f]{32}", doc_id) is not None

def open_vector_store(doc_id):
    # cosine space so search scores are easy to read (distance = 1 - cosine similarity)
    return Chroma(
        collection_name=f"doc_{doc_id}",
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR,
        collection_metadata={"hnsw:space": "cosine"},
    )

def load_document(doc_id):
    """Return a document from memory, or load it from disk (e.g. after a backend restart)."""
    if doc_id in _cache:
        return _cache[doc_id]
    if not is_valid_doc_id(doc_id):
        return None
    meta_path = os.path.join(DOCS_DIR, f"{doc_id}.json")
    if not os.path.exists(meta_path):
        return None

    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    store = open_vector_store(doc_id)

    # Rebuild the BM25 keyword index from the chunks saved in ChromaDB
    saved = store.get(include=["documents", "metadatas"])
    chunks = [Document(page_content=text, metadata=md)
              for text, md in zip(saved["documents"], saved["metadatas"])]
    chunks.sort(key=lambda c: c.metadata["chunk_id"])
    for c in chunks:  # documents uploaded before TXT/CSV support only stored 'page'
        c.metadata.setdefault("location", f"Page {c.metadata.get('page', 0) + 1}")

    # Older uploads saved "pages"; newer ones save labelled "sections"
    sections = meta.get("sections") or [[f"Page {i + 1}", p] for i, p in enumerate(meta["pages"])]

    doc = {
        "name": meta["name"],
        "kind": meta.get("kind", "pdf"),
        "sections": sections,
        "store": store,
        "chunks": chunks,
        "bm25": BM25Okapi([tokenize(c.page_content) for c in chunks]),
    }
    _cache[doc_id] = doc
    return doc


def get_table(doc_id, doc):
    """The full CSV as a pandas table (loaded once), or None for other file types."""
    if doc["kind"] != "csv":
        return None
    if "table" not in doc:
        path = os.path.join(TABLES_DIR, f"{doc_id}.csv")
        doc["table"] = tables.load_table(path) if os.path.exists(path) else None
    return doc["table"]


# ---------- Routes ----------

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if file is None:
        return jsonify({"error": "No file received."}), 400

    if file_kind(file.filename) is None:
        return jsonify({"error": "Only PDF, TXT, MD and CSV files are supported."}), 400

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > 10 * 1024 * 1024:
        return jsonify({"error": "File is too large. Please upload a file under 10MB."}), 413

    # Save the file temporarily, read and chunk it by type, then delete the temp file
    suffix = "." + file.filename.rsplit(".", 1)[-1].lower()
    doc_id = uuid.uuid4().hex
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.close()
        file.save(tmp.name)
        kind, sections, chunks, stats = load_file(tmp.name, file.filename)
        if kind == "csv":  # keep the full table for exact queries
            shutil.copy(tmp.name, os.path.join(TABLES_DIR, f"{doc_id}.csv"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        print(f"[error] upload: {e}")
        return jsonify({"error": "Could not read this file. It may be corrupted."}), 422
    finally:
        os.remove(tmp.name)

    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = i  # lets us match dense and keyword results

    # Save chunks to ChromaDB and the text sections to a JSON file
    store = open_vector_store(doc_id)
    store.add_documents(chunks, ids=[f"{doc_id}-{i}" for i in range(len(chunks))])
    with open(os.path.join(DOCS_DIR, f"{doc_id}.json"), "w", encoding="utf-8") as f:
        json.dump({"name": file.filename, "kind": kind, "stats": stats, "sections": sections}, f)

    _cache[doc_id] = {
        "name": file.filename,
        "kind": kind,
        "sections": sections,
        "store": store,
        "chunks": chunks,
        "bm25": BM25Okapi([tokenize(c.page_content) for c in chunks]),
    }

    return jsonify({
        "message": "File uploaded and processed successfully",
        "doc_id": doc_id,
        "kind": kind,
        "stats": stats,
        "pages": len(sections) if kind == "pdf" else None,
        "chunks": len(chunks),
    })

@app.route("/summarize", methods=["POST"])
def summarize():
    doc = load_document((request.json or {}).get("doc_id"))
    if doc is None:
        return jsonify({"error": "Document not found. Please upload it again."}), 404

    doc_text = "\n".join(text for _, text in doc["sections"])
    try:
        summary = ask_llm(
            "Summarize the following document in 3-4 sentences. Be concise and focus "
            f"on the main topic and key points.\n\nDocument:\n{doc_text[:4000]}"
        )
    except Exception as e:
        print(f"[error] summarize: {e}")
        return jsonify({"error": "The AI service is unavailable right now. Please try again."}), 502

    return jsonify({"summary": summary})


# ---------- LangGraph: classify the question, then route it ----------

class AskState(TypedDict, total=False):
    question: str
    doc_id: str
    mode: str        # retrieval mode: "hybrid" (default), or "dense"/"keyword" for evaluation
    intent: str
    answer: str
    sources: list
    evidence: list   # chunks shown in the Evidence panel (retrieval route only)
    table: dict      # query plan + result (table route only)
    error: str

REFUSAL_MESSAGE = "I couldn't find this in the document."

# Formatting rule shared by answer prompts so the frontend can render maths
FORMAT_RULES = (
    "Format the answer in Markdown. Write any maths with LaTeX between $...$ "
    "(inline) or $$...$$ (on its own line)."
)

# Errors worth retrying: Groq busy/over capacity (5xx), rate limits (429), network problems
RETRYABLE = (groq.InternalServerError, groq.RateLimitError, groq.APIConnectionError, groq.APITimeoutError)

def ask_llm(prompt, fast=False, effort="low"):
    """Call Groq with retries (waiting 1s, then 2s) and fall back to the smaller model
    if the main one stays unavailable. fast=True uses the small model directly."""
    models = [FAST_MODEL] if fast else [MODEL, FAST_MODEL]
    last_error = None
    for model in models:
        for attempt in range(3):
            try:
                extra = {"reasoning_effort": effort} if "gpt-oss" in model else {}
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    extra_body=extra,
                )
                if model != models[0]:
                    print(f"[info] answered with fallback model {model}")
                return response.choices[0].message.content
            except RETRYABLE as e:
                last_error = e
                print(f"[retry] {model} attempt {attempt + 1} failed: {type(e).__name__}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
    raise last_error

# Words that almost always mean "calculate over the table" (exact lookups are left to the classifier)
TABLE_WORDS = re.compile(
    r"\b(how many|count|number of|total|sum|average|avg|mean|median|highest|lowest|"
    r"maximum|minimum|max|min|most|least|per|by each|for each|each|group|percent|percentage|"
    r"ratio|rank|top \d+|bottom \d+)\b",
    re.IGNORECASE,
)

def classify_intent(state):
    question = state["question"]
    doc = load_document(state["doc_id"])
    is_table = doc is not None and get_table(state["doc_id"], doc) is not None
    table_option = (
        "'table_query' (questions about the table that need exact lookups by a value such as "
        "an ID or name, counting, totals, averages, min/max, sorting or grouping over rows), "
        if is_table else ""
    )
    label = ask_llm(
        "Classify the message below as exactly one word: "
        "'casual' (greetings, small talk, thanks, or questions about what you can do), "
        "'overview' (questions about the document as a whole: its main idea, summary, "
        "title, authors, or what it is about), "
        + table_option +
        "or 'document_question' (any other question to be answered from an uploaded document). "
        "Any specific factual or technical question counts as document_question. "
        "If unsure, choose document_question. "
        f"Reply with only that one word.\n\nMessage: {question}",
        fast=True,  # routing is an easy job, so use the small model
    ).strip().lower().strip(".'\"")
    allowed = ("casual", "overview", "table_query") if is_table else ("casual", "overview")
    intent = label if label in allowed else "document_question"
    # Safety net: for tables, calculation words override a "document_question" label
    if is_table and intent == "document_question" and TABLE_WORDS.search(question):
        intent = "table_query"
    debug(f"[route] {question!r} -> {intent} (model said: {label!r})")
    return {"intent": intent}

def direct_answer(state):
    answer = ask_llm(
        "You are Sage, a friendly document-chat assistant. Reply briefly and "
        "naturally to this message. If asked what you can do, explain that you can "
        "answer questions about the user's uploaded document (PDF, TXT or CSV) with citations, give an "
        "overview of it (main idea, authors), and say so when something isn't in the "
        "document. Do not answer factual or technical questions; instead, ask the user "
        "to ask about their uploaded document."
        f"\n\nMessage: {state['question']}"
    )
    return {"answer": answer, "sources": [], "evidence": []}

def overview_answer(state):
    """Whole-document questions (main idea, authors, title). Small chunks can't answer
    these, so we use the start of the document: title, authors, abstract, introduction."""
    doc = load_document(state["doc_id"])
    if doc is None:
        return {"error": "Document not found. Please upload it again."}

    OVERVIEW_CHARS = 6000
    context, sources = "", []
    for label, text in doc["sections"]:
        if len(context) >= OVERVIEW_CHARS:
            break
        context += text + "\n"
        sources.append(label)
    context = context[:OVERVIEW_CHARS]

    answer = ask_llm(
        "Below is the beginning of a document (title, authors, abstract, introduction). "
        "Answer the question using ONLY this text. "
        "If the text does not contain the answer, reply exactly: "
        f"\"{REFUSAL_MESSAGE}\" {FORMAT_RULES}\n\n"
        f"Document start: {context}\n\nQuestion: {state['question']}"
    )
    if REFUSAL_MESSAGE.lower() in answer.lower():
        sources = []
    return {"answer": answer, "sources": sources, "evidence": []}

def find_citations(answer, count):
    """Return the chunk numbers the answer cites, e.g. 'GPUs [1][3]' or '[1, 3]' -> [1, 3]."""
    cited = []
    for group in re.findall(r"\[(\d+(?:\s*,\s*\d+)*)\]", answer):
        for n in group.split(","):
            n = int(n)
            if 1 <= n <= count and n not in cited:
                cited.append(n)
    return sorted(cited)

def normalize_citations(answer):
    """Turn '【1】', '【1†L3】' (GPT-OSS style) and '[1, 3]' into '[1]' / '[1][3]'
    so the frontend only has one format to handle."""
    answer = re.sub(r"【\s*(\d+(?:\s*,\s*\d+)*)[^】]*】", r"[\1]", answer)
    return re.sub(
        r"\[(\d+(?:\s*,\s*\d+)+)\]",
        lambda m: "".join(f"[{n.strip()}]" for n in m.group(1).split(",")),
        answer,
    )

def cosine_scores(store, question, chunk_ids, doc_id):
    """Meaning similarity (cosine) between the question and each chunk, for display."""
    saved = store.get(ids=[f"{doc_id}-{i}" for i in chunk_ids], include=["embeddings", "metadatas"])
    by_id = {md["chunk_id"]: emb for md, emb in zip(saved["metadatas"], saved["embeddings"])}
    q = embeddings.embed_query(question)
    q_norm = sum(x * x for x in q) ** 0.5 or 1.0
    scores = {}
    for cid, emb in by_id.items():
        e_norm = sum(x * x for x in emb) ** 0.5 or 1.0
        scores[cid] = sum(a * b for a, b in zip(q, emb)) / (q_norm * e_norm)
    return scores

def retrieve_and_answer(state):
    doc = load_document(state["doc_id"])
    if doc is None:
        return {"error": "Document not found. Please upload it again."}

    question = state["question"]
    chunks = doc["chunks"]

    # Hybrid search: combine dense (meaning) search with BM25 (keyword) search.
    # Dense search alone missed questions like "what hardware was used?", because
    # MiniLM didn't match them to "8 NVIDIA P100 GPUs". Keywords catch those.
    CANDIDATES = 10   # results taken from each search
    TOP_K = 5         # chunks sent to the LLM
    RRF_K = 60        # standard constant for Reciprocal Rank Fusion
    MIN_COSINE = 0.3  # loose junk filter for dense search (see below)

    # 1. Dense search. The collection uses cosine distance, so similarity = 1 - distance.
    dense = doc["store"].similarity_search_with_score(question, k=min(CANDIDATES, len(chunks)))
    dense_ids = [d.metadata["chunk_id"] for d, _ in dense]
    best_cosine = 1 - float(dense[0][1]) if dense else 0.0

    # 2. Keyword search (only chunks sharing at least one keyword count)
    bm25_scores = doc["bm25"].get_scores(tokenize(question))
    ranked = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)
    bm25_ids = [i for i in ranked[:CANDIDATES] if bm25_scores[i] > 0]

    # Evaluation only: switch one search off to measure what each one adds (ablation)
    mode = state.get("mode") or "hybrid"
    if mode == "dense":
        bm25_ids = []
    elif mode == "keyword":
        dense_ids, best_cosine = [], 0.0

    debug(f"[dense] best cosine={best_cosine:.3f}, top ids={dense_ids[:5]}")
    debug(f"[bm25] top ids={bm25_ids[:5]}, top score={max(bm25_scores, default=0):.2f}")

    # Early refusal: no shared keywords AND weak meaning match -> clearly off-topic.
    # Everything else goes to the LLM, which refuses if the chunks lack the answer.
    if (not bm25_ids and best_cosine < MIN_COSINE and mode != "dense") or \
            (mode == "dense" and best_cosine < MIN_COSINE) or (mode == "keyword" and not bm25_ids):
        return {"answer": REFUSAL_MESSAGE, "sources": [], "evidence": []}

    # 3. Reciprocal Rank Fusion: a chunk ranked high in either list scores high
    fused = {}
    for ranking in (dense_ids, bm25_ids):
        for rank, chunk_id in enumerate(ranking):
            fused[chunk_id] = fused.get(chunk_id, 0) + 1 / (RRF_K + rank + 1)
    top_ids = sorted(fused, key=fused.get, reverse=True)[:TOP_K]
    relevant_docs = [chunks[i] for i in top_ids]
    debug(f"[fused] ids={top_ids}, top chunk={relevant_docs[0].page_content[:100]!r}")

    # Number the chunks [1]..[n] so the model can cite exactly which one it used.
    context = "\n\n".join(
        f"[{n}] ({d.metadata['location']})\n{d.page_content}"
        for n, d in enumerate(relevant_docs, start=1)
    )
    # Tables: retrieval only shows a few rows, so be honest about calculations
    table_note = (
        "The context shows only some rows of a larger table. If the question needs "
        "every row (totals, averages, counts), say that you can only see some rows "
        "and answer from the rows shown. "
        if doc["kind"] == "csv" else ""
    )

    answer = ask_llm(
        "Answer the question using ONLY the numbered context chunks below. " + table_note +
        "After each fact, cite the chunk it came from with its number in square brackets, "
        "like [1] or [2][3]. Only cite chunks that actually support the fact. "
        "If the context does not contain the answer, reply exactly: "
        f"\"{REFUSAL_MESSAGE}\" {FORMAT_RULES}\n\n"
        f"Context:\n{context}\n\nQuestion: {question}"
    )
    answer = normalize_citations(answer)
    refused = REFUSAL_MESSAGE.lower() in answer.lower()
    cited = [] if refused else find_citations(answer, len(relevant_docs))
    # Drop citation numbers that don't match any chunk (e.g. a made-up [9])
    answer = re.sub(r"\[(\d+)\]",
                    lambda m: m.group(0) if 1 <= int(m.group(1)) <= len(relevant_docs) else "",
                    answer)

    # Evidence for the frontend panel: every retrieved chunk, how it was found,
    # its scores, and whether the answer actually cited it.
    meaning = cosine_scores(doc["store"], question, top_ids, state["doc_id"])
    max_bm25 = max(bm25_scores, default=0) or 1.0
    evidence = []
    for n, (chunk_id, d) in enumerate(zip(top_ids, relevant_docs), start=1):
        found_by = []
        if chunk_id in bm25_ids:
            found_by.append("keyword")
        if chunk_id in dense_ids[:TOP_K]:
            found_by.append("meaning")
        evidence.append({
            "n": n,
            "location": d.metadata["location"],
            "text": d.page_content,
            "found_by": found_by,
            "meaning_score": round(float(meaning.get(chunk_id, 0.0)), 3),
            "keyword_score": round(float(bm25_scores[chunk_id]) / max_bm25, 3),
            "cited": n in cited,
        })
    debug(f"[cited] {cited}")

    # Citations: locations of the cited chunks (or all retrieved ones if the
    # model answered without citing anything), in document order
    used = [e for e in evidence if e["cited"]] or ([] if refused else evidence)
    used_docs = sorted((relevant_docs[e["n"] - 1] for e in used), key=lambda d: d.metadata["chunk_id"])
    sources = list(dict.fromkeys(d.metadata["location"] for d in used_docs))
    return {"answer": answer, "sources": sources, "evidence": evidence}

def table_answer(state):
    """Exact answers for CSVs: the LLM writes a JSON query plan, pandas runs it."""
    doc = load_document(state["doc_id"])
    if doc is None:
        return {"error": "Document not found. Please upload it again."}
    df = get_table(state["doc_id"], doc)
    question = state["question"]

    try:
        plan = tables.parse_plan(ask_llm(
            f"{tables.PLAN_INSTRUCTIONS}\n\nTable:\n{tables.describe(df)}\n\nQuestion: {question}",
            effort="medium",  # planning needs more care than phrasing an answer
        ))
        # Self-check: the question mentions a column the plan never uses -> probably a
        # forgotten condition. Send the plan back once with that feedback.
        missing = tables.unused_columns(plan, question, df)
        if missing:
            debug(f"[table] plan ignores {missing}; asking for a corrected plan")
            plan = tables.parse_plan(ask_llm(
                f"{tables.PLAN_INSTRUCTIONS}\n\nTable:\n{tables.describe(df)}\n\nQuestion: {question}\n\n"
                f"Your previous plan was: {json.dumps(plan)}\n"
                f"The question mentions {', '.join(missing)}, but the plan never uses "
                f"{'it' if len(missing) == 1 else 'them'}. If that is a condition in the question, "
                "add a filter for it. Reply with the corrected JSON plan only.",
                effort="medium",
            ))
        result = tables.run_plan(df, plan)
    except Exception as e:
        # A bad plan shouldn't break the chat: fall back to normal search
        debug(f"[table] plan failed ({e}); falling back to search")
        return {**retrieve_and_answer(state), "intent": "document_question"}
    debug(f"[table] plan={plan} matched={result['matched_rows']}")

    # Describe the result in plain words (raw JSON tempted the model to invent "Row 1"),
    # including exactly which filters ran, so a wrong plan can't be passed off as right
    computed = tables.describe_plan(plan)
    if result["kind"] == "value":
        result_text = f"{result['label']} = {result['value']} (computed over all {result['total_rows']} rows)"
        rows_hint = "Do not mention row numbers. "
    else:
        header = "| " + " | ".join(map(str, result["columns"])) + " |"
        divider = "|" + "---|" * len(result["columns"])
        body = "\n".join("| " + " | ".join("" if v is None else str(v) for v in row) + " |"
                         for row in result["rows"])
        result_text = (f"{result['matched_rows']} of {result['total_rows']} rows matched. "
                       f"Showing up to 20:\n{header}\n{divider}\n{body}")
        rows_hint = ("When you mention a row, use its number from the 'Row' column (e.g. Row 3). "
                     if result["kind"] == "rows" else "Do not mention row numbers. ")

    answer = ask_llm(
        "Answer the question using ONLY the result below, which was computed exactly "
        "over the full table. Give the direct answer first in 1-3 sentences, with no "
        "heading. Use a small table only if there are several rows or groups. "
        + rows_hint +
        "Describe exactly what was computed: never say a filter was applied unless it is "
        "listed under 'Filters applied'. If the computation doesn't match the question "
        "(for example a condition from the question is missing), say what was actually "
        "computed and that it may not fully answer the question. "
        "Do not add citation markers. If the result doesn't answer the question, "
        f"reply exactly: \"{REFUSAL_MESSAGE}\" {FORMAT_RULES}\n\nQuestion: {question}\n"
        f"What was computed: {computed}\nResult: {result_text}"
    )
    answer = re.sub(r"【[^】]*】", "", answer).strip()  # drop stray GPT-OSS-style markers
    summary = f"Table query · {result['matched_rows']:,} of {result['total_rows']:,} rows matched"
    return {
        "answer": answer,
        "sources": [summary],
        "evidence": [],
        "table": {"plan": plan, "result": result},
    }

graph = StateGraph(AskState)
graph.add_node("classify_intent", classify_intent)
graph.add_node("direct_answer", direct_answer)
graph.add_node("retrieve_and_answer", retrieve_and_answer)
graph.add_node("overview_answer", overview_answer)
graph.add_node("table_answer", table_answer)
graph.set_entry_point("classify_intent")
graph.add_conditional_edges("classify_intent", lambda state: state["intent"], {
    "casual": "direct_answer",
    "overview": "overview_answer",
    "table_query": "table_answer",
    "document_question": "retrieve_and_answer"
})
graph.add_edge("direct_answer", END)
graph.add_edge("retrieve_and_answer", END)
graph.add_edge("overview_answer", END)
graph.add_edge("table_answer", END)
ask_graph = graph.compile()

@app.route("/ask", methods=["POST"])
def ask():
    body = request.json or {}
    question = (body.get("question") or "").strip()
    doc_id = body.get("doc_id")
    mode = body.get("mode") if body.get("mode") in ("hybrid", "dense", "keyword") else "hybrid"
    if not question:
        return jsonify({"error": "Please type a question."}), 400
    if load_document(doc_id) is None:
        return jsonify({"error": "Document not found. Please upload it again."}), 404

    try:
        result = ask_graph.invoke({"question": question, "doc_id": doc_id, "mode": mode})
    except Exception as e:
        print(f"[error] ask: {e}")
        return jsonify({"error": "The AI service is unavailable right now. Please try again."}), 502

    if "error" in result:
        return jsonify({"error": result["error"]}), 400

    return jsonify({
        "answer": result["answer"],
        "sources": result["sources"],
        "route": result.get("intent"),
        "evidence": result.get("evidence", []),
        "table": result.get("table"),
    })

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1", port=5000, use_reloader=False)
