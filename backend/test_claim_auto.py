import os
import sys
import json
import urllib.request
import uuid

backend_dir = os.path.dirname(os.path.abspath(__file__))
uploads_dir = os.path.join(backend_dir, 'uploads')

# 1. Find and load target PDF bytes first
pdf_files = [f for f in os.listdir(uploads_dir) if f.endswith('.pdf')]
if not pdf_files:
    print("❌ Error: No PDF found in uploads folder.")
    sys.exit(1)

target_pdf_path = os.path.join(uploads_dir, pdf_files[0])
target_pdf_name = os.path.basename(target_pdf_path)
with open(target_pdf_path, "rb") as f:
    file_data = f.read()

print(f"📄 Loaded target PDF ({len(file_data)} bytes): {target_pdf_name}")

# 2. Clear all records
print("\n🧹 Step 1: Clearing all past records...")
try:
    del_req = urllib.request.Request("http://localhost:5000/api/claims", method="DELETE")
    with urllib.request.urlopen(del_req, timeout=10) as del_resp:
        print("   ✅ Server database reset.")
except Exception as e:
    print(f"   ⚠️ Reset error: {e}")

claims_index_file = os.path.join(backend_dir, 'data', 'claims_index.json')
try:
    with open(claims_index_file, 'w', encoding='utf-8') as f:
        json.dump({"claims": []}, f, indent=2)
    print("   ✅ Claims index ledger reset to empty.")
except Exception as e:
    print(f"   ⚠️ Reset error: {e}")

# 3. Submit clean claim
fields = {
    'claimedAmountINR': '1200',
    'category': 'cellphone',
    'startDate': '2023-01-21',
    'endDate': '2023-02-20',
    'validityPeriod': '1 Month (31 Days)',
}

boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
body_bytes = bytearray()

for key, val in fields.items():
    body_bytes.extend(f"--{boundary}\r\n".encode("utf-8"))
    body_bytes.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
    body_bytes.extend(f"{val}\r\n".encode("utf-8"))

body_bytes.extend(f"--{boundary}\r\n".encode("utf-8"))
body_bytes.extend(f'Content-Disposition: form-data; name="invoices"; filename="{target_pdf_name}"\r\n'.encode("utf-8"))
body_bytes.extend(b"Content-Type: application/pdf\r\n\r\n")
body_bytes.extend(file_data)
body_bytes.extend(b"\r\n")
body_bytes.extend(f"--{boundary}--\r\n".encode("utf-8"))

req = urllib.request.Request(
    "http://localhost:5000/api/claims",
    data=bytes(body_bytes),
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    method="POST",
)

print("\n🚀 Step 2: Submitting clean claim request to http://localhost:5000/api/claims ...")
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        print(f"✅ HTTP Status Code: {resp.status}")
        raw = resp.read().decode("utf-8")
        parsed = json.loads(raw)
        print("\n📦 Response Result:")
        print(json.dumps(parsed, indent=2))
except urllib.error.HTTPError as e:
    print(f"❌ HTTP Error {e.code}: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"❌ Error: {e}")
