
import sys
import os
import logging

# Setup path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from app.main import app

def debug_endpoint():
    client = TestClient(app)
    print("Testing /signals/analyze/GODREJCP.NS ...")
    try:
        response = client.get("/signals/analyze/GODREJCP.NS")
        print(f"Status: {response.status_code}")
        if response.status_code != 200:
            print("Error content:", response.content)
        else:
            print("Success:", response.json())
    except Exception as e:
        print("Exception during request:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_endpoint()
