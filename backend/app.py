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

@app.route("/upload", methods=["POST"])
def upload():
    global vectorstore
    file = request.files["file"]
    
    # Save PDF temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)
        
        # Load and split PDF
        loader = PyPDFLoader(tmp.name)
        docs = loader.load()
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = splitter.split_documents(docs)
        
        # Store as vectors
        vectorstore = FAISS.from_documents(chunks, embeddings)
    
    return jsonify({"message": "PDF uploaded and processed successfully"})

@app.route("/ask", methods=["POST"])
def ask():
    global vectorstore
    if not vectorstore:
        return jsonify({"error": "Please upload a PDF first"}), 400
    
    question = request.json.get("question")
    
    # Find relevant chunks
    relevant_docs = vectorstore.similarity_search(question, k=3)
    context = "\n".join([d.page_content for d in relevant_docs])
    sources = sorted(list(set([
    d.metadata.get('page', 0) + 1
    for d in relevant_docs
])))
    sources = [f"Page {p}" for p in sources]
    
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