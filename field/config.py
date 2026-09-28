import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent


@dataclass
class Config:
    device_id: str = "alpha"
    device_name: str = ""
    data_dir: Path = ROOT / "data"
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key: str = os.getenv("QDRANT_API_KEY", "")
    server_collection: str = "field_memory"
    hq_url: str = os.getenv("HQ_URL", "")                 # ImpactProof backend, e.g. http://127.0.0.1:8000
    hq_project_id: int | None = int(os.getenv("HQ_PROJECT_ID")) if os.getenv("HQ_PROJECT_ID") else None
    embedder: str = os.getenv("FIELD_EMBEDDER", "fastembed")   # fastembed | hash (tests)
    memory_budget: int = int(os.getenv("FIELD_MEMORY_BUDGET", "500"))  # max synced-in items kept on device
    auto_sync_seconds: int = 15
    extra: dict = field(default_factory=dict)

    @property
    def device_dir(self) -> Path:
        return self.data_dir / self.device_id

    @property
    def label(self) -> str:
        return self.device_name or f"Field device {self.device_id}"
