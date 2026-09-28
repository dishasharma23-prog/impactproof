import requests
import json
import os
from time import sleep

BASE_URL = "http://127.0.0.1:8000/api"
MEDIA_DIR = r"C:\Users\disha\.gemini\antigravity\brain\d80a8edd-ed1c-4c40-bda6-5ebe752c0a62\.user_uploaded"

print("1. Uploading distinct image A (Original)")
files = {"file": ("media_1.png", open(os.path.join(MEDIA_DIR, "media_1790357381580.png"), "rb"), "image/png")}
r = requests.post(f"{BASE_URL}/evidence/upload", files=files)
ev1 = r.json()["evidence_id"]
print(ev1)

sleep(1)

print("2. Uploading distinct image B (Original)")
files = {"file": ("media_2.png", open(os.path.join(MEDIA_DIR, "media_1790357393345.png"), "rb"), "image/png")}
r = requests.post(f"{BASE_URL}/evidence/upload", files=files)
ev2 = r.json()["evidence_id"]
print(ev2)

sleep(1)

print("3. Uploading exact copy of A (Potential Reuse)")
files = {"file": ("media_1_copy.png", open(os.path.join(MEDIA_DIR, "media_1790357381580.png"), "rb"), "image/png")}
r = requests.post(f"{BASE_URL}/evidence/upload", files=files)
ev3 = r.json()["evidence_id"]
print(ev3)

sleep(1)

print("4. Uploading distinct image C (test_image.jpg)")
files = {"file": ("test_image.jpg", open("test_image.jpg", "rb"), "image/jpeg")}
r = requests.post(f"{BASE_URL}/evidence/upload", files=files)
ev4 = r.json()["evidence_id"]
print(ev4)

print("5. Creating the Demo Claim")
claim_text = "2,400 households in the Rajasthan Water Initiative gained access to clean water infrastructure."
r = requests.post(f"{BASE_URL}/claims/", json={"text": claim_text})
claim_id = r.json()["id"]

print("6. Linking Evidence")
requests.post(f"{BASE_URL}/claims/{claim_id}/evidence", json={"evidence_id": ev1})
requests.post(f"{BASE_URL}/claims/{claim_id}/evidence", json={"evidence_id": ev2})
requests.post(f"{BASE_URL}/claims/{claim_id}/evidence", json={"evidence_id": ev3})
requests.post(f"{BASE_URL}/claims/{claim_id}/evidence", json={"evidence_id": ev4})

print("Demo seed complete! Claim ID:", claim_id)

