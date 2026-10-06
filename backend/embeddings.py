"""MiniLM embeddings without PyTorch, tuned for a 512 MB server.

Sage uses the all-MiniLM-L6-v2 embedding model. ChromaDB ships the same model
exported to ONNX; we download it through ChromaDB but run it ourselves so we can
keep memory low:
  - small batches (8 texts at a time instead of 32)
  - pad each batch only to its longest text (not always to 256 tokens)
  - ONNX Runtime's memory arena switched off, so memory is given back after each batch
The maths (mean pooling + normalising) is the same, so the vectors are the same.
"""
import os

import numpy as np
import onnxruntime as ort
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
from langchain_core.embeddings import Embeddings
from tokenizers import Tokenizer

BATCH_SIZE = 8
MAX_TOKENS = 256  # same limit sentence-transformers uses for this model

_session = None
_batch_tokenizer = None
_count_tokenizer = None


def _model_dir():
    """Download the model once (about 90 MB, cached) and return its folder."""
    model = ONNXMiniLM_L6_V2()
    model._download_model_if_not_exists()
    return os.path.join(model.DOWNLOAD_PATH, model.EXTRACTED_FOLDER_NAME)


def _onnx_session():
    global _session
    if _session is None:
        options = ort.SessionOptions()
        options.log_severity_level = 3
        options.enable_cpu_mem_arena = False  # don't keep a big memory pool around
        options.enable_mem_pattern = False
        options.intra_op_num_threads = 1      # Render's free plan has a small CPU share anyway
        options.inter_op_num_threads = 1
        _session = ort.InferenceSession(
            os.path.join(_model_dir(), "model.onnx"),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
    return _session


def _tokenizer_for_batches():
    global _batch_tokenizer
    if _batch_tokenizer is None:
        _batch_tokenizer = Tokenizer.from_file(os.path.join(_model_dir(), "tokenizer.json"))
        _batch_tokenizer.enable_truncation(max_length=MAX_TOKENS)
        _batch_tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")  # pad to longest in batch
    return _batch_tokenizer


def _embed(texts):
    session = _onnx_session()
    tok = _tokenizer_for_batches()
    vectors = []
    for i in range(0, len(texts), BATCH_SIZE):
        encoded = tok.encode_batch(texts[i:i + BATCH_SIZE])
        ids = np.array([e.ids for e in encoded], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
        hidden = session.run(None, {
            "input_ids": ids,
            "attention_mask": mask,
            "token_type_ids": np.zeros_like(ids),
        })[0]
        # mean pooling over real tokens only, then normalise to length 1
        m = mask[..., None].astype(np.float32)
        pooled = (hidden * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)
        pooled /= np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None)
        vectors.extend(pooled.astype(np.float32).tolist())
    return vectors


class MiniLMEmbeddings(Embeddings):
    """LangChain-compatible wrapper so ChromaDB / LangChain can use the ONNX model."""

    def embed_documents(self, texts):
        return _embed(list(texts))

    def embed_query(self, text):
        return _embed([text])[0]


def tokenizer():
    """The model's own tokenizer, used to measure chunk sizes in tokens.
    Truncation is switched off so long texts are counted fully."""
    global _count_tokenizer
    if _count_tokenizer is None:
        _count_tokenizer = Tokenizer.from_file(os.path.join(_model_dir(), "tokenizer.json"))
        _count_tokenizer.no_truncation()
        _count_tokenizer.no_padding()
    return _count_tokenizer


def count_tokens(text):
    return len(tokenizer().encode(text, add_special_tokens=False).ids)
