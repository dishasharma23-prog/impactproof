import requests
import sys
import subprocess

print("--- Testing Phase 6 ---")

print("1. Running index_existing_evidence.py twice (idempotency)...")
subprocess.run([sys.executable, "index_existing_evidence.py"], check=True)
subprocess.run([sys.executable, "index_existing_evidence.py"], check=True)

print("2. Searching for newly installed water infrastructure...")
res = requests.post("http://127.0.0.1:8000/api/evidence/search", json={"query": "newly installed water infrastructure", "limit": 2})
print(res.json())

print("3. Getting candidates for Claim 2...")
res = requests.get("http://127.0.0.1:8000/api/claims/2/candidates")
print(res.json())

