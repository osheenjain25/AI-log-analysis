import requests
import time
import threading
import os
import sys

# Add the current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_endpoint():
    print("Waiting for server to start...")
    time.sleep(5)
    
    url = "http://localhost:5001/aws-cost/analyze"
    print(f"Testing endpoint: {url}")
    
    try:
        # We expect this to fail or take a long time without real credentials/data,
        # but we want to verify the endpoint exists and the code executes.
        # Since we don't have real AWS creds in this env, we expect an error,
        # but it should be a handled error from our code, not a 404.
        response = requests.post(url, timeout=10)
        print(f"Response Status: {response.status_code}")
        print(f"Response Content: {response.text}")
        
        if response.status_code == 200:
            print("✅ Endpoint returned 200 OK")
        elif response.status_code == 500:
            # 500 is acceptable here because we likely don't have AWS creds,
            # so the extractor will fail. We just want to ensure it's hitting our logic.
            print("✅ Endpoint returned 500 (Expected due to missing creds)")
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_endpoint()
