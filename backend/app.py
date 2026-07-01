from dotenv import load_dotenv
load_dotenv()  
from flask import Flask, request, jsonify
from flask_cors import CORS
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from groq import Groq
import os
import tempfile

app = Flask(__name__)
CORS(app)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vectorstore = None
doc_text = None

@app.route("/upload", methods=["POST"])
def upload():
    global vectorstore, doc_text
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

        # Store as vectors
        vectorstore = FAISS.from_documents(chunks, embeddings)
        doc_text = extracted_text

    return jsonify({"message": "PDF uploaded and processed successfully"})

@app.route("/summarize", methods=["POST"])
def summarize():
    global doc_text
    if not doc_text:
        return jsonify({"error": "Please upload a PDF first"}), 400

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{
            "role": "user",
            "content": f"Summarize the following document in 3-4 sentences. Be concise and focus on the main topic and key points.\n\nDocument:\n{doc_text[:4000]}"
        }]
    )

    return jsonify({"summary": response.choices[0].message.content})

@app.route("/ask", methods=["POST"])
def ask():
    global vectorstore
    if not vectorstore:
        return jsonify({"error": "Please upload a PDF first"}), 400
    
    question = request.json.get("question")
    
    # Find relevant chunks — fetch k=5 candidates then drop anything below the
    # relevance threshold (0 = no match, 1 = perfect). Scores are normalised
    # from FAISS L2 distance via 1/(1+distance), so 0.5 already means the
    # vectors are roughly orthogonal. Raise RELEVANCE_THRESHOLD to tighten.
    # Note: 'page' is the 0-indexed physical page position in the PDF file,
    # not the printed page number — they differ when a PDF has a cover, ToC,
    # or Roman-numeral front matter before the main content.
    RELEVANCE_THRESHOLD = 0.3
    scored_docs = vectorstore.similarity_search_with_relevance_scores(question, k=5)
    relevant_docs = [doc for doc, score in scored_docs if score >= RELEVANCE_THRESHOLD]
    if not relevant_docs:
        relevant_docs = vectorstore.similarity_search(question, k=2)
    context = "\n".join([d.page_content for d in relevant_docs])
    sources = sorted(list(set([
        d.metadata["page"] + 1
        for d in relevant_docs
        if "page" in d.metadata
    ])))
    sources = [f"PDF Page {p}" for p in sources]
    
    # Send to Groq LLM
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{
            "role": "user",
            "content": f"Answer the question based on this context only.\n\nContext: {context}\n\nQuestion: {question}"
        }]
    )
    
    return jsonify({
    "answer": response.choices[0].message.content,
    "sources": sources
})

if __name__ == "__main__":
    app.run(debug=True, port=5000)