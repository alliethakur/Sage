from dotenv import load_dotenv
load_dotenv()  
from flask import Flask, request, jsonify
from flask_cors import CORS
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from groq import Groq
from langgraph.graph import StateGraph, END
from typing import TypedDict
import os
import re
import tempfile
from rank_bm25 import BM25Okapi

app = Flask(__name__)
CORS(app)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vectorstore = None   # dense (meaning-based) search index
bm25 = None          # keyword search index
chunk_list = None    # all chunks, in the same order as the BM25 index
doc_text = None
doc_pages = None     # text of each page, used by the overview route

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

@app.route("/upload", methods=["POST"])
def upload():
    global vectorstore, bm25, chunk_list, doc_text, doc_pages
    file = request.files["file"]

    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported."}), 400

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > 10 * 1024 * 1024:
        return jsonify({"error": "PDF is too large. Please upload a file under 10MB."}), 413

    # Save PDF temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)

        # Load and split PDF
        loader = PyPDFLoader(tmp.name)
        docs = loader.load()
        extracted_text = "\n".join([d.page_content for d in docs])

        if not extracted_text.strip():
            return jsonify({"error": "This PDF appears to be scanned. Please upload a text-based PDF."}), 422

        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = splitter.split_documents(docs)
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_id"] = i  # lets us match dense and keyword results

        # Build both search indexes
        vectorstore = FAISS.from_documents(chunks, embeddings)
        bm25 = BM25Okapi([tokenize(c.page_content) for c in chunks])
        chunk_list = chunks
        doc_text = extracted_text
        doc_pages = [d.page_content for d in docs]

    return jsonify({"message": "PDF uploaded and processed successfully"})

@app.route("/summarize", methods=["POST"])
def summarize():
    global doc_text
    if not doc_text:
        return jsonify({"error": "Please upload a PDF first"}), 400

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": f"Summarize the following document in 3-4 sentences. Be concise and focus on the main topic and key points.\n\nDocument:\n{doc_text[:4000]}"
        }]
    )

    return jsonify({"summary": response.choices[0].message.content})

class AskState(TypedDict, total=False):
    question: str
    intent: str
    answer: str
    sources: list
    error: str

def classify_intent(state):
    question = state["question"]
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": (
                "Classify the message below as exactly one word: "
                "'casual' (greetings, small talk, thanks, or questions about what you can do), "
                "'overview' (questions about the document as a whole: its main idea, summary, "
                "title, authors, or what it is about), "
                "or 'document_question' (any other question to be answered from an uploaded document). "
                "Any specific factual or technical question counts as document_question. "
                "If unsure, choose document_question. "
                f"Reply with only that one word.\n\nMessage: {question}"
            )
        }]
    )
    label = response.choices[0].message.content.strip().lower().strip(".'\"")
    intent = label if label in ("casual", "overview") else "document_question"
    print(f"[route] {question!r} -> {intent} (model said: {label!r})")  # temporary, for testing
    return {"intent": intent}

def direct_answer(state):
    question = state["question"]
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": (
                "You are Sage, a friendly document-chat assistant. Reply briefly and "
                "naturally to this message. If asked what you can do, explain that you can "
                "answer questions about the user's uploaded PDF with page citations, give an "
                "overview of it (main idea, authors), and say so when something isn't in the "
                "document. Do not answer factual or technical questions; instead, ask the user "
                "to ask about their uploaded document."
                f"\n\nMessage: {question}"
            )
        }]
    )
    return {"answer": response.choices[0].message.content, "sources": []}

REFUSAL_MESSAGE = "I couldn't find this in the document."

# Formatting rule shared by answer prompts so the frontend can render maths
FORMAT_RULES = (
    "Format the answer in Markdown. Write any maths with LaTeX between $...$ "
    "(inline) or $$...$$ (on its own line)."
)

def overview_answer(state):
    """Whole-document questions (main idea, authors, title). Small chunks can't answer
    these, so we use the start of the document: title, authors, abstract, introduction."""
    if not doc_pages:
        return {"error": "Please upload a PDF first"}

    question = state["question"]
    OVERVIEW_CHARS = 6000
    context, sources = "", []
    for page_number, page_text in enumerate(doc_pages, start=1):
        if len(context) >= OVERVIEW_CHARS:
            break
        context += page_text + "\n"
        sources.append(f"PDF Page {page_number}")
    context = context[:OVERVIEW_CHARS]

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": (
                "Below is the beginning of a document (title, authors, abstract, introduction). "
                "Answer the question using ONLY this text. "
                "If the text does not contain the answer, reply exactly: "
                f"\"{REFUSAL_MESSAGE}\" {FORMAT_RULES}\n\n"
                f"Document start: {context}\n\nQuestion: {question}"
            )
        }]
    )
    answer = response.choices[0].message.content
    if REFUSAL_MESSAGE.lower() in answer.lower():
        sources = []
    return {"answer": answer, "sources": sources}

def retrieve_and_answer(state):
    global vectorstore, bm25, chunk_list
    if not vectorstore:
        return {"error": "Please upload a PDF first"}

    question = state["question"]

    # Hybrid search: combine dense (meaning) search with BM25 (keyword) search.
    # Dense search alone missed questions like "what hardware was used?", because
    # MiniLM didn't match them to "8 NVIDIA P100 GPUs". Keywords catch those.
    CANDIDATES = 10   # results taken from each search
    TOP_K = 5         # chunks sent to the LLM
    RRF_K = 60        # standard constant for Reciprocal Rank Fusion
    MIN_COSINE = 0.3  # loose junk filter for dense search (see below)

    # 1. Dense search. FAISS returns squared L2 distance; for normalised
    #    embeddings, cosine similarity = 1 - distance / 2.
    dense = vectorstore.similarity_search_with_score(question, k=CANDIDATES)
    dense_ids = [doc.metadata["chunk_id"] for doc, _ in dense]
    best_cosine = 1 - float(dense[0][1]) / 2 if dense else 0.0

    # 2. Keyword search (only chunks sharing at least one keyword count)
    bm25_scores = bm25.get_scores(tokenize(question))
    ranked = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)
    bm25_ids = [i for i in ranked[:CANDIDATES] if bm25_scores[i] > 0]

    print(f"[dense] best cosine={best_cosine:.3f}, top ids={dense_ids[:5]}")  # temporary, for testing
    print(f"[bm25] top ids={bm25_ids[:5]}, top score={max(bm25_scores, default=0):.2f}")  # temporary, for testing

    # Early refusal: no shared keywords AND weak meaning match -> clearly off-topic.
    # Everything else goes to the LLM, which refuses if the chunks lack the answer.
    if not bm25_ids and best_cosine < MIN_COSINE:
        return {"answer": REFUSAL_MESSAGE, "sources": []}

    # 3. Reciprocal Rank Fusion: a chunk ranked high in either list scores high
    fused = {}
    for ranking in (dense_ids, bm25_ids):
        for rank, chunk_id in enumerate(ranking):
            fused[chunk_id] = fused.get(chunk_id, 0) + 1 / (RRF_K + rank + 1)
    top_ids = sorted(fused, key=fused.get, reverse=True)[:TOP_K]
    relevant_docs = [chunk_list[i] for i in top_ids]
    print(f"[fused] ids={top_ids}, top chunk={relevant_docs[0].page_content[:100]!r}")  # temporary, for testing

    # Note: 'page' is the 0-indexed physical page position in the PDF file,
    # not the printed page number — they differ when a PDF has a cover, ToC,
    # or Roman-numeral front matter before the main content.
    context = "\n".join([d.page_content for d in relevant_docs])
    sources = sorted(list(set([
        d.metadata["page"] + 1
        for d in relevant_docs
        if "page" in d.metadata
    ])))
    sources = [f"PDF Page {p}" for p in sources]

    # Send to Groq LLM
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": (
                "Answer the question using ONLY the context below. "
                "If the context does not contain the answer, reply exactly: "
                f"\"{REFUSAL_MESSAGE}\" {FORMAT_RULES}\n\n"
                f"Context: {context}\n\nQuestion: {question}"
            )
        }]
    )

    answer = response.choices[0].message.content
    if REFUSAL_MESSAGE.lower() in answer.lower():
        sources = []  # don't cite pages for an answer we didn't give
    return {"answer": answer, "sources": sources}

graph = StateGraph(AskState)
graph.add_node("classify_intent", classify_intent)
graph.add_node("direct_answer", direct_answer)
graph.add_node("retrieve_and_answer", retrieve_and_answer)
graph.add_node("overview_answer", overview_answer)
graph.set_entry_point("classify_intent")
graph.add_conditional_edges("classify_intent", lambda state: state["intent"], {
    "casual": "direct_answer",
    "overview": "overview_answer",
    "document_question": "retrieve_and_answer"
})
graph.add_edge("direct_answer", END)
graph.add_edge("retrieve_and_answer", END)
graph.add_edge("overview_answer", END)
ask_graph = graph.compile()

@app.route("/ask", methods=["POST"])
def ask():
    question = request.json.get("question")
    result = ask_graph.invoke({"question": question})

    if "error" in result:
        return jsonify({"error": result["error"]}), 400

    return jsonify({"answer": result["answer"], "sources": result["sources"]})

if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False)