"""MiniLM embeddings without PyTorch.

Sage uses the all-MiniLM-L6-v2 embedding model. Running it through PyTorch
(sentence-transformers) needs ~1.5 GB of RAM, which is too much for free hosting.
ChromaDB ships the *same model* exported to ONNX and runs it with ONNX Runtime
(same tokenizer, mean pooling and normalisation), using a fraction of the memory.
"""
import os

from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
from langchain_core.embeddings import Embeddings
from tokenizers import Tokenizer

_model = None
_tokenizer = None


def _onnx_model():
    """Load the ONNX model once (downloads ~90 MB on first use, then cached)."""
    global _model
    if _model is None:
        _model = ONNXMiniLM_L6_V2()
        _model._download_model_if_not_exists()
    return _model


class MiniLMEmbeddings(Embeddings):
    """LangChain-compatible wrapper so ChromaDB / LangChain can use the ONNX model."""

    def embed_documents(self, texts):
        return [[float(x) for x in vector] for vector in _onnx_model()(list(texts))]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


def tokenizer():
    """The model's own tokenizer, used to measure chunk sizes in tokens.
    Truncation is switched off so long texts are counted fully."""
    global _tokenizer
    if _tokenizer is None:
        model = _onnx_model()
        path = os.path.join(model.DOWNLOAD_PATH, model.EXTRACTED_FOLDER_NAME, "tokenizer.json")
        _tokenizer = Tokenizer.from_file(path)
        _tokenizer.no_truncation()
        _tokenizer.no_padding()
    return _tokenizer


def count_tokens(text):
    return len(tokenizer().encode(text, add_special_tokens=False).ids)
