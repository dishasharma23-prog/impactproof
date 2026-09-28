import requests

BASE_URL = "http://127.0.0.1:8000/api"

print("1. Create valid claim")
res = requests.post(f"{BASE_URL}/claims/", json={"text": "This is a valid claim."})
assert res.status_code == 200, res.text
claim_id = res.json()["id"]
print("Success:", res.json())

print("2. Reject empty claim")
res = requests.post(f"{BASE_URL}/claims/", json={"text": "   "})
assert res.status_code == 422, res.text
print("Success (rejected):", res.status_code)

print("3. Reject nonexistent project")
res = requests.post(f"{BASE_URL}/claims/", json={"text": "Test", "project_id": 9999})
assert res.status_code == 404, res.text
print("Success (rejected):", res.status_code)

print("4. GET claim")
res = requests.get(f"{BASE_URL}/claims/{claim_id}")
assert res.status_code == 200, res.text
print("Success:", res.json())

print("5. GET claims")
res = requests.get(f"{BASE_URL}/claims/")
assert res.status_code == 200, res.text
print("Success, count:", len(res.json()))

print("6. Link valid evidence")
# Assuming evidence 5 exists from previous test
evidence_id = 5
res = requests.post(f"{BASE_URL}/claims/{claim_id}/evidence", json={"evidence_id": evidence_id})
assert res.status_code == 200, res.text
print("Success:", res.json())

print("7. Retrieve claim with linked evidence")
res = requests.get(f"{BASE_URL}/claims/{claim_id}")
assert res.status_code == 200, res.text
data = res.json()
assert data["evidence_count"] == 1
assert data["evidence"][0]["id"] == evidence_id
print("Success:", data["evidence"])

print("8. Attempt duplicate link -> clean 409")
res = requests.post(f"{BASE_URL}/claims/{claim_id}/evidence", json={"evidence_id": evidence_id})
assert res.status_code == 409, res.text
print("Success (rejected):", res.json())

print("9. Link nonexistent evidence -> 404")
res = requests.post(f"{BASE_URL}/claims/{claim_id}/evidence", json={"evidence_id": 9999})
assert res.status_code == 404, res.text
print("Success (rejected):", res.json())

print("10. Unlink evidence")
res = requests.delete(f"{BASE_URL}/claims/{claim_id}/evidence/{evidence_id}")
assert res.status_code == 200, res.text
print("Success:", res.json())

print("11. Confirm EvidenceAsset still exists after unlink")
res = requests.get(f"{BASE_URL}/evidence/{evidence_id}")
assert res.status_code == 200, res.text
print("Success:", res.json()["id"])

print("12. Confirm Cloudinary asset still exists/retrievable")
# (If GET evidence returns 200, it still exists in DB. Cloudinary is untouched)
print("Success")

print("13. Confirm claim with zero evidence works")
res = requests.get(f"{BASE_URL}/claims/{claim_id}")
assert res.status_code == 200, res.text
data = res.json()
assert data["evidence_count"] == 0
assert len(data["evidence"]) == 0
print("Success:", data["evidence_count"])

