import asyncio
import httpx
import time
import json
import argparse

async def make_request(client, capability, index):
    url = "http://localhost:8000/v1/chat/completions"
    payload = {
        "capability": capability,
        "messages": [{"role": "user", "content": f"Tell me a short joke number {index}"}]
    }
    
    start = time.perf_counter()
    try:
        response = await client.post(url, json=payload, timeout=None)
        response.raise_for_status()
        end = time.perf_counter()
        print(f"[Req {index:02d}] Finished in {end - start:.2f}s")
        return True
    except Exception as e:
        print(f"[Req {index:02d}] Failed: {e}")
        return False

async def main():
    parser = argparse.ArgumentParser(description="Simulate concurrent load on the platform")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent requests")
    parser.add_argument("--capability", type=str, default="chat", help="Capability to request")
    args = parser.parse_args()

    print(f"Starting load test with {args.concurrency} concurrent requests for capability: '{args.capability}'...")
    print("This will trigger a barrage of requests at the exact same time!\n")
    
    start_time = time.perf_counter()
    async with httpx.AsyncClient() as client:
        tasks = [make_request(client, args.capability, i) for i in range(args.concurrency)]
        await asyncio.gather(*tasks)
    
    total_time = time.perf_counter() - start_time
    print(f"\nLoad test complete! Total wall-clock time: {total_time:.2f}s")
    
    print("\nFetching latest inference metrics...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8000/v1/inference/metrics?limit={args.concurrency}")
        if response.status_code == 200:
            data = response.json()
            print(json.dumps(data.get("summary", {}), indent=2))
            print("\nRecent Requests (notice the model_name field if load balancing occurred):")
            for req in data.get("recent_requests", []):
                print(f"- {req.get('model_name')}: {req.get('e2e_latency_ms', 0):.1f}ms latency")
        else:
            print(f"Failed to fetch metrics: {response.text}")

if __name__ == "__main__":
    asyncio.run(main())
