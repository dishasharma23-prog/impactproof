import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_tmp}/test.db", "STORAGE_DIR": f"{_tmp}/storage", "QDRANT_URL": "",
    "GEMINI_API_KEY": "", "CLOUDINARY_CLOUD_NAME": "", "CLOUDINARY_API_KEY": "", "CLOUDINARY_API_SECRET": "",
    "CLOUDINARY_URL": "", "WEATHER_ENABLED": "false",
})
