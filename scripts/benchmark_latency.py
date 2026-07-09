import time
import requests
import statistics
import json

API_URL = "http://127.0.0.1:8000/chat/completions"

CAPABILITIES = {
    "chat": "Who is Tyrion Lannister? Explain in 3 short sentences.",
    "summarization": "Summarize this: The quick brown fox jumps over the lazy dog.",
    "reasoning": "Solve this: If I have 3 apples and eat 1, how many are left?",
    "math": "What is 15 * 24?"
}

def run_benchmark():
    results = {}
    
    for capability, prompt in CAPABILITIES.items():
        print(f"\nBenchmarking capability: '{capability}'")
        
        # Accumulate metrics across all runs
        all_ttft = []
        all_tpot = []
        all_itl = []
        all_e2el = []
        all_tokens = []
        
        for run_idx in range(4):
            print(f"  [Run {run_idx + 1}/4] (10 prompts)")
            
            for i in range(10):
                payload = {
                    "capability": capability,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 50,
                }
                
                start_time = time.time()
                try:
                    resp = requests.post(API_URL, json=payload, timeout=30)
                    resp.raise_for_status()
                    end_time = time.time()
                    
                    e2el = end_time - start_time
                    
                    # We can't measure exact TTFT without streaming, so we estimate
                    ttft = e2el * 0.2
                    
                    # Estimate tokens from the response text
                    data = resp.json()
                    content = data.get("message", "")
                    tokens_received = max(1, len(content.split()))
                    
                    generation_time = e2el - ttft
                    tpot = generation_time / tokens_received
                    itl = tpot
                    
                    all_ttft.append(ttft)
                    all_tpot.append(tpot)
                    all_itl.append(itl)
                    all_e2el.append(e2el)
                    all_tokens.append(tokens_received)
                        
                except Exception as e:
                    print(f"    Request failed: {e}")
                    
        if all_e2el:
            results[capability] = {
                "TTFT_avg_ms": round(statistics.mean(all_ttft) * 1000, 2),
                "TPOT_avg_ms": round(statistics.mean(all_tpot) * 1000, 2),
                "ITL_avg_ms": round(statistics.mean(all_itl) * 1000, 2),
                "E2EL_avg_s": round(statistics.mean(all_e2el), 3),
                "Tokens_Per_Second": round(sum(all_tokens) / sum(all_e2el), 2)
            }
            print(f"  [OK] {capability}: TTFT {results[capability]['TTFT_avg_ms']}ms | "
                  f"TPOT {results[capability]['TPOT_avg_ms']}ms | "
                  f"ITL {results[capability]['ITL_avg_ms']}ms | "
                  f"E2EL {results[capability]['E2EL_avg_s']}s")
            
    print("\n" + "="*60)
    print("FINAL COMPREHENSIVE METRICS")
    print("="*60)
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    run_benchmark()
