import requests

BASE_URL = "http://127.0.0.1:8089"

print("1. Testing Login as Admin...")
resp = requests.post(f"{BASE_URL}/api/v1/auth/login", json={"email": "admin@demo.com", "password": "password"})
print(resp.status_code, resp.text)
token = resp.json()["token"]

print("\n2. Testing Admin API Key Generation...")
headers = {"Authorization": f"Bearer {token}"}
resp = requests.post(f"{BASE_URL}/api/v1/platform/keys", headers=headers)
print(resp.status_code, resp.text)

print("\n3. Testing Metrics Endpoint...")
resp = requests.get(f"{BASE_URL}/metrics/")
print(resp.status_code)
print("\n".join(resp.text.split("\n")[:10]))
