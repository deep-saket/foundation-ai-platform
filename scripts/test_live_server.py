import requests
import time
import sys

BASE_URL = "http://localhost:8000"

def test_chat(run_name: str, expected_description: str):
    print(f"\n--- {run_name} ---")
    print(f"Expectation: {expected_description}")
    
    payload = {
        "model": "Qwen/Qwen2.5-1.5B-Instruct",
        "messages": [
            {"role": "user", "content": "Write a 2 sentence poem about a server."}
        ],
        "password": "dhruv"
    }
    
    start_time = time.time()
    try:
        response = requests.post(f"{BASE_URL}/chat/completions", json=payload, timeout=300)
        end_time = time.time()
        
        if response.status_code == 200:
            data = response.json()
            print(f"Success! (Took {end_time - start_time:.2f} seconds)")
            print(f"Routed to Model: {data.get('route', {}).get('model_id')}")
            print(f"Message: {data.get('message')}")
        else:
            print(f"Error ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    # Test 1: Initial download and deploy
    test_chat(
        run_name="Run 1: Initial Request", 
        expected_description="Should download weights from HuggingFace, spin up Docker, and generate. (Slowest)"
    )
    
    print("\nWaiting 35 seconds for the model to go COLD and be unloaded...")
    for i in range(35, 0, -1):
        sys.stdout.write(f"\rTime remaining: {i}s   ")
        sys.stdout.flush()
        time.sleep(1)
    print("\nModel should now be unloaded!")
    
    # Test 2: Cold start from SSD
    test_chat(
        run_name="Run 2: Cold Start from SSD", 
        expected_description="No downloading needed. Should just spin up Docker with mounted SSD cache. (Faster)"
    )
