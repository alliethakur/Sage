# Sage backend: slim image (no PyTorch). The embedding model runs on ONNX Runtime.
FROM python:3.11-slim

RUN useradd -m -u 1000 user
# MALLOC_ARENA_MAX / OMP_NUM_THREADS keep memory use low on the 512 MB free plan
ENV HOME=/home/user \
    PYTHONUNBUFFERED=1 \
    MALLOC_ARENA_MAX=2 \
    OMP_NUM_THREADS=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY --chown=user . .
RUN mkdir -p /app/data && chown -R user /app
USER user

# Download the ONNX embedding model during the build, so the first request isn't slow
RUN python -c "from embeddings import MiniLMEmbeddings; MiniLMEmbeddings().embed_query('warm up')"

# Hosts like Render pass the port in $PORT. One worker keeps the in-memory document
# cache consistent; threads let several requests run at once.
CMD gunicorn --workers 1 --threads 2 --timeout 180 --bind 0.0.0.0:${PORT:-7860} app:app
