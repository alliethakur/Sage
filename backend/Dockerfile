# Sage backend: image for Hugging Face Spaces (Docker SDK)
FROM python:3.11-slim

# Hugging Face Spaces run containers as a non-root user with id 1000
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1

WORKDIR /app

# CPU-only PyTorch (much smaller than the default GPU build), then the rest
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt gunicorn

COPY --chown=user . .
RUN mkdir -p /app/data && chown -R user /app
USER user

# Download the embedding model during the build, so the first request isn't slow
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

EXPOSE 7860
# Gunicorn: a production web server. One worker keeps the in-memory document cache
# consistent; threads let several requests run at once.
CMD ["gunicorn", "--workers", "1", "--threads", "4", "--timeout", "180", "--bind", "0.0.0.0:7860", "app:app"]
