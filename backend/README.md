# Sage backend

Flask API for [Sage](https://github.com/alliethakur/Sage): a document chatbot (PDF / TXT / CSV)
with hybrid retrieval, LangGraph routing, an exact table-query route and chunk-level citations.

## Run locally
```bash
pip install -r requirements.txt
python app.py            # http://127.0.0.1:5000
```
Needs a `.env` file with `GROQ_API_KEY=...`.

## Deploy (Docker)
The `Dockerfile` builds a slim image (no PyTorch: the MiniLM embedding model runs on
ONNX Runtime) that fits in 512 MB of RAM. Set these environment variables on the host:

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | Groq API key (keep it secret) |
| `ALLOWED_ORIGINS` | Frontend URL(s) allowed to call the API, e.g. `https://sage.vercel.app` |
