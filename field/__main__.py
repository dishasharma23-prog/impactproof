"""Run a field device:  python -m field --device alpha --port 8101"""
import argparse
from pathlib import Path

import uvicorn

from field.api import create_app
from field.config import Config

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="ImpactProof Field device")
    ap.add_argument("--device", default="alpha", help="device id, e.g. alpha or beta")
    ap.add_argument("--name", default="", help="display name, e.g. 'Asha's phone'")
    ap.add_argument("--port", type=int, default=8101)
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--qdrant", default=None, help="Qdrant Server URL (default http://localhost:6333)")
    ap.add_argument("--qdrant-key", default=None, help="Qdrant Cloud API key")
    ap.add_argument("--https", action="store_true", help="serve over https so phones on the same Wi-Fi/hotspot can use camera and GPS")
    ap.add_argument("--hq", default=None, help="ImpactProof backend URL, e.g. http://127.0.0.1:8000")
    ap.add_argument("--project", type=int, default=None, help="ImpactProof project id for uploads")
    ap.add_argument("--budget", type=int, default=None, help="max items synced in from elsewhere to keep")
    ap.add_argument("--embedder", default=None, choices=["fastembed", "hash"])
    a = ap.parse_args()
    cfg = Config(device_id=a.device, device_name=a.name)
    if a.data_dir:
        cfg.data_dir = Path(a.data_dir)
    if a.qdrant:
        cfg.qdrant_url = a.qdrant
    if a.qdrant_key:
        cfg.qdrant_api_key = a.qdrant_key
    if a.hq is not None:
        cfg.hq_url = a.hq
    if a.project:
        cfg.hq_project_id = a.project
    if a.budget:
        cfg.memory_budget = a.budget
    if a.embedder:
        cfg.embedder = a.embedder
    app = create_app(cfg)
    ssl = {}
    scheme = "http"
    if a.https:
        from field.certs import ensure_cert, lan_ips
        cert, key = ensure_cert(cfg.data_dir / "certs")
        ssl = {"ssl_certfile": str(cert), "ssl_keyfile": str(key)}
        scheme = "https"
    print(f"\n  {cfg.label} is running at {scheme}://localhost:{a.port}")
    if a.https:
        print("  On a phone connected to this laptop's Wi-Fi or hotspot, open:")
        for ip in lan_ips():
            print(f"      https://{ip}:{a.port}")
        print("  (Your phone will warn about the certificate once: choose Show details / Advanced, then visit the site.)")
    print()
    uvicorn.run(app, host="0.0.0.0", port=a.port, log_level="warning", **ssl)
