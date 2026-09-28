"""On-device embeddings. Models run locally, so search works with no network at all.

fastembed downloads each model once (about 450 MB in total) and caches it on the device:
  text  BAAI/bge-small-en-v1.5        384 dims, for notes, captions and facts
  clip  Qdrant/clip-ViT-B-32-vision   512 dims, for photos
        Qdrant/clip-ViT-B-32-text     512 dims, so words can find photos ("garbage bags")
A tiny hash embedder is used for tests and as a fallback before the models are downloaded.
"""
import os
import hashlib
import math
import re

TEXT_DIM, CLIP_DIM = 384, 512


def _norm(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class HashEmbedder:
    name = "hash"
    text_floor = 0.01  # minimum text similarity for a meaning match (no shared words = no match)

    def _bag(self, text: str, dim: int, salt: str):
        v = [0.0] * dim
        words = re.findall(r"[a-z0-9]+", (text or "").lower())
        for w in words + [a + "_" + b for a, b in zip(words, words[1:])]:
            h = int(hashlib.md5((salt + w).encode()).hexdigest(), 16)
            v[h % dim] += 1.0 if (h >> 64) % 2 else -1.0
        return _norm(v)

    def text(self, text: str):
        return self._bag(text, TEXT_DIM, "t:")

    def clip_text(self, text: str):
        return self._bag(text, CLIP_DIM, "c:")

    def image(self, path: str):
        from PIL import Image
        with Image.open(path) as im:
            small = im.convert("RGB").resize((16, 16))
            px = list(small.getdata())
        feats = [c / 255.0 for p in px for c in p]  # 768 values
        v = [0.0] * CLIP_DIM
        for i, f in enumerate(feats):
            v[i % CLIP_DIM] += f * (1 if (i * 2654435761) % 7 < 4 else -1)
        return _norm(v)


class FastEmbedder:
    name = "fastembed"
    text_floor = float(os.getenv("FIELD_TEXT_FLOOR", "0.6"))  # bge-small scores unrelated sentences around 0.4 to 0.55

    def __init__(self, cache_dir=None):
        from fastembed import ImageEmbedding, TextEmbedding
        self._text = TextEmbedding("BAAI/bge-small-en-v1.5", cache_dir=cache_dir)
        self._clip_text = TextEmbedding("Qdrant/clip-ViT-B-32-text", cache_dir=cache_dir)
        self._image = ImageEmbedding("Qdrant/clip-ViT-B-32-vision", cache_dir=cache_dir)

    def text(self, text: str):
        return [float(x) for x in next(iter(self._text.embed([text or " "])))]

    def clip_text(self, text: str):
        return [float(x) for x in next(iter(self._clip_text.embed([text or " "])))]

    def image(self, path: str):
        return [float(x) for x in next(iter(self._image.embed([str(path)])))]


def make_embedder(kind: str, cache_dir=None):
    if kind == "hash":
        return HashEmbedder()
    try:
        return FastEmbedder(cache_dir)
    except Exception as e:  # models not downloaded yet and no network
        print(f"On-device models unavailable ({e}). Using the simple hash embedder; run "
              f"`python -m field.setup_models` once while online for real semantic search.")
        return HashEmbedder()
