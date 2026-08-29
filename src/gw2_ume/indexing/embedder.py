"""Dense Text Embedder and Resilient Fallback Vectorizer for GW2-UME."""

from __future__ import annotations

import logging
import math
import os
import re
from abc import ABC, abstractmethod
from typing import Optional, Sequence, Union

import numpy as np

logger = logging.getLogger(__name__)


def detect_optimal_device() -> str:
    """Auto-detect optimal PyTorch compute device: Apple Silicon MPS, CUDA, or CPU."""
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except Exception as exc:
        logger.debug("PyTorch device detection encountered: %s", exc)
    return "cpu"


class BaseEmbedder(ABC):
    """Abstract base class for dense text embedders."""

    @abstractmethod
    def encode(
        self,
        texts: Union[str, Sequence[str]],
        batch_size: int = 32,
        normalize: bool = True,
        show_progress_bar: bool = False,
    ) -> np.ndarray:
        """Encode a sequence of texts into 2D float32 numpy array of shape (N, D)."""
        pass

    @abstractmethod
    def encode_single(self, text: str, normalize: bool = True) -> np.ndarray:
        """Encode a single text string into 1D float32 numpy array of shape (D,)."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding vector dimensionality."""
        pass


class LightweightFallbackEmbedder(BaseEmbedder):
    """Resilient, deterministic subword & character n-gram hashing embedder.

    Used when sentence-transformers or network weights are unavailable.
    Outputs unit-normalized L2 dense float32 vectors suitable for cosine similarity.
    """

    def __init__(self, dimension: int = 384, ngram_range: tuple[int, int] = (3, 5)) -> None:
        self._dimension = dimension
        self._ngram_min, self._ngram_max = ngram_range
        self._word_dim = dimension // 2
        self._char_dim = dimension - self._word_dim

    @property
    def dimension(self) -> int:
        return self._dimension

    def _tokenize_words(self, text: str) -> list[str]:
        return re.findall(r"\b\w+\b", text.lower())

    def _extract_char_ngrams(self, text: str) -> list[str]:
        s = f"^{text.lower().strip()}$"
        ngrams: list[str] = []
        for n in range(self._ngram_min, self._ngram_max + 1):
            if len(s) >= n:
                for i in range(len(s) - n + 1):
                    ngrams.append(s[i : i + n])
            else:
                ngrams.append(s)
        return ngrams

    def _embed_single_raw(self, text: str) -> np.ndarray:
        vec = np.zeros(self._dimension, dtype=np.float32)
        if not text or not text.strip():
            return vec

        cleaned = text.lower().strip()
        words = self._tokenize_words(cleaned)
        char_ngs = self._extract_char_ngrams(cleaned)

        # 1. Word hash into first half
        if words:
            w_weight = 1.0 / math.sqrt(len(words))
            for w in words:
                h = hash(w) % self._word_dim
                vec[h] += 2.0 * w_weight
            # Bigrams
            for i in range(len(words) - 1):
                bi = f"{words[i]}_{words[i+1]}"
                h = hash(bi) % self._word_dim
                vec[h] += 1.5 * w_weight

        # 2. Char n-gram hash into second half
        if char_ngs:
            c_weight = 1.0 / math.sqrt(len(char_ngs))
            for ng in char_ngs:
                h = self._word_dim + (hash(ng) % self._char_dim)
                vec[h] += 1.0 * c_weight

        # 3. Positional prefix hash
        for idx, ch in enumerate(cleaned[:32]):
            h = (hash(ch) + idx * 31) % self._dimension
            vec[h] += 0.25

        return vec

    def encode(
        self,
        texts: Union[str, Sequence[str]],
        batch_size: int = 32,
        normalize: bool = True,
        show_progress_bar: bool = False,
    ) -> np.ndarray:
        """Batch encode texts deterministically."""
        if isinstance(texts, str):
            text_list = [texts]
        else:
            text_list = list(texts)

        if not text_list:
            return np.empty((0, self._dimension), dtype=np.float32)

        vectors = np.zeros((len(text_list), self._dimension), dtype=np.float32)
        for i, t in enumerate(text_list):
            vectors[i] = self._embed_single_raw(t)

        if normalize:
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            vectors = np.where(norms > 1e-12, vectors / norms, vectors)

        return vectors.astype(np.float32)

    def encode_single(self, text: str, normalize: bool = True) -> np.ndarray:
        """Encode a single text string."""
        vec = self._embed_single_raw(text)
        if normalize:
            norm = np.linalg.norm(vec)
            if norm > 1e-12:
                vec = vec / norm
        return vec.astype(np.float32)


class TextEmbedder(BaseEmbedder):
    """Dense bi-encoder wrapper using `sentence-transformers` with device auto-selection and fallback."""

    def __init__(
        self,
        model_name_or_path: str = "all-MiniLM-L6-v2",
        device: Optional[str] = None,
        use_fallback: bool = False,
        fallback_dimension: int = 384,
        local_files_only: Optional[bool] = None,
    ) -> None:
        self.model_name = model_name_or_path
        self._requested_device = device
        self._device = device or detect_optimal_device()
        self._fallback_dimension = fallback_dimension
        self._is_fallback = use_fallback
        self._local_files_only = local_files_only
        self._model = None
        self._fallback = LightweightFallbackEmbedder(dimension=fallback_dimension)

        if not use_fallback:
            self._init_sentence_transformer()

    def _init_sentence_transformer(self) -> None:
        """Attempt to load sentence-transformers model (trying local cache first); falls back gracefully on error."""
        try:
            os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
            from sentence_transformers import SentenceTransformer

            # Try local files first for instant startup if cached
            if self._local_files_only is not False:
                try:
                    logger.debug("Attempting local cache load for '%s'...", self.model_name)
                    self._model = SentenceTransformer(
                        self.model_name,
                        device=self._device,
                        local_files_only=True,
                    )
                    self._is_fallback = False
                    logger.info("Loaded SentenceTransformer '%s' from local cache on '%s'.", self.model_name, self._device)
                    return
                except Exception as local_err:
                    if self._local_files_only is True:
                        raise local_err
                    logger.debug("Local cache miss for '%s': %s", self.model_name, local_err)

            # Try online/standard load
            logger.info("Loading SentenceTransformer '%s' on device '%s'...", self.model_name, self._device)
            self._model = SentenceTransformer(self.model_name, device=self._device)
            self._is_fallback = False
            logger.info("Successfully loaded SentenceTransformer '%s'", self.model_name)
        except Exception as exc:
            logger.warning(
                "Could not load SentenceTransformer model '%s' (%s). "
                "Falling back to LightweightFallbackEmbedder (dim=%d).",
                self.model_name,
                exc,
                self._fallback_dimension,
            )
            self._model = None
            self._is_fallback = True

    @property
    def is_fallback(self) -> bool:
        """Whether the embedder is operating in fallback mode."""
        return self._is_fallback

    @property
    def device(self) -> str:
        """Active compute device (e.g. 'mps', 'cuda', 'cpu')."""
        return self._device if not self._is_fallback else "cpu"

    @property
    def dimension(self) -> int:
        """Embedding dimension."""
        if not self._is_fallback and self._model is not None:
            try:
                dim = self._model.get_sentence_embedding_dimension()
                if dim is not None:
                    return int(dim)
            except Exception:
                pass
        return self._fallback.dimension

    def encode(
        self,
        texts: Union[str, Sequence[str]],
        batch_size: int = 32,
        normalize: bool = True,
        show_progress_bar: bool = False,
    ) -> np.ndarray:
        """Encode texts into 2D float32 numpy array with unit norm."""
        if isinstance(texts, str):
            text_list = [texts]
        else:
            text_list = list(texts)

        if not text_list:
            return np.empty((0, self.dimension), dtype=np.float32)

        if self._is_fallback or self._model is None:
            return self._fallback.encode(
                text_list,
                batch_size=batch_size,
                normalize=normalize,
                show_progress_bar=show_progress_bar,
            )

        try:
            embeddings = self._model.encode(
                text_list,
                batch_size=batch_size,
                normalize_embeddings=normalize,
                convert_to_numpy=True,
                show_progress_bar=show_progress_bar,
            )
            if isinstance(embeddings, np.ndarray):
                res = embeddings.astype(np.float32)
            else:
                res = np.array(embeddings, dtype=np.float32)

            if normalize and res.ndim == 2:
                norms = np.linalg.norm(res, axis=1, keepdims=True)
                res = np.where(norms > 1e-12, res / norms, res)
            return res
        except Exception as exc:
            logger.warning("Error during SentenceTransformer encoding (%s), falling back to fallback embedder.", exc)
            return self._fallback.encode(
                text_list,
                batch_size=batch_size,
                normalize=normalize,
                show_progress_bar=show_progress_bar,
            )

    def encode_single(self, text: str, normalize: bool = True) -> np.ndarray:
        """Encode a single text into 1D float32 numpy array."""
        arr = self.encode([text], batch_size=1, normalize=normalize, show_progress_bar=False)
        return arr[0] if len(arr) > 0 else np.zeros(self.dimension, dtype=np.float32)
