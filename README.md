# Sage
Chat with any PDF — semantic search, page citations, and agentic intent routing.

![Sage Demo](demo.gif)

## Features
- Upload any PDF and instantly get an animated document summary
- LangGraph routes intent — casual chat vs document questions
- FAISS vector search with relevance threshold filtering retrieves only genuinely relevant chunks
- Answers include PDF page citations so you know exactly where they came from
- Copy answer button with confirmation
- Error handling for scanned PDFs, corrupted files, and oversized documents
- Per-document thread history with the ability to switch between conversations

## Tech Stack
React · Flask · LangChain · LangGraph · FAISS · HuggingFace Sentence Transformers · Groq (Llama 3.3 70B)

## Getting Started

**Backend**
```bash
cd backend
pip install -r requirements.txt
python app.py
```
Add a `.env` file with `GROQ_API_KEY=your_key`

**Frontend**
```bash
cd frontend/pdf-chat
npm install
npm start
```