"""Download the on-device models once, while online. After this the field app needs no network."""
from field.config import ROOT
from field.embed import FastEmbedder

if __name__ == "__main__":
    print("Downloading on-device models (about 450 MB, once)…")
    e = FastEmbedder(cache_dir=str(ROOT / "models"))
    print("text", len(e.text("hello")), "clip", len(e.clip_text("hello")))
    print("Done. The field app can now run fully offline.")
