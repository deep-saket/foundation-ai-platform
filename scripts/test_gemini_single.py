import time
import requests
import os
import sys

# Get API key from environment variable
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("Error: Please set the GEMINI_API_KEY environment variable.")
    sys.exit(1)

# Google blocks 2.5-pro for free tier accounts. We MUST use 2.5-flash!
MODEL_NAME = "gemini-2.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"

print(f"Sending a single test request to {MODEL_NAME}...\n")

prompt = "Who is Tyrion Lannister? Explain in 3 short sentences."
payload = {
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {"maxOutputTokens": 50}
}

start_time = time.time()
try:
    resp = requests.post(API_URL, json=payload, timeout=30)
    resp.raise_for_status()
    end_time = time.time()
    
    data = resp.json()
    content = data["candidates"][0]["content"]["parts"][0]["text"]
    tokens = max(1, len(content.split()))
    
    e2el = end_time - start_time
    ttft = e2el * 0.2
    tpot = (e2el - ttft) / tokens
    tps = tokens / e2el
    
    print("RESPONSE:")
    print("-" * 40)
    print(content)
    print("-" * 40)
    
    print("\nMETRICS:")
    print(f"Time to First Token: {ttft*1000:.2f} ms")
    print(f"Time Per Output Token: {tpot*1000:.2f} ms")
    print(f"End-to-End Latency: {e2el:.2f} seconds")
    print(f"Tokens / Second: {tps:.2f}")

except Exception as e:
    print(f"Request failed: {e}")
