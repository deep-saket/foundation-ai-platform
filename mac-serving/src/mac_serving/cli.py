"""Operator CLI for planning, diagnosis, serving, and lightweight benchmarking."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import statistics
import sys
import time

from .config import default_config_path, load_config
from .footprint import estimate_footprint, model_path_status
from .hardware import detect_hardware


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mac-serve")
    parser.add_argument("--config", type=Path, default=default_config_path())
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("plan", help="show host and unified-memory footprint")
    subcommands.add_parser("doctor", help="validate hardware, binary, model, and sizing")
    subcommands.add_parser("command", help="print the llama-server argv")
    subcommands.add_parser("serve", help="start the control plane and managed backend")
    benchmark = subcommands.add_parser("benchmark", help="measure request latency and throughput")
    benchmark.add_argument("--requests", type=int, default=8)
    benchmark.add_argument("--concurrency", type=int, default=2)
    benchmark.add_argument("--max-tokens", type=int, default=64)
    benchmark.add_argument("--prompt", default="Explain unified memory in one concise paragraph.")
    return parser


def _plan(config_path: Path) -> int:
    config = load_config(config_path)
    hardware = detect_hardware()
    estimate = estimate_footprint(config, hardware)
    print(json.dumps({"hardware": hardware.as_dict(), "footprint": estimate.as_dict()}, indent=2))
    return 0 if estimate.fits_safely else 2


def _doctor(config_path: Path) -> int:
    from .backend import resolve_binary

    config = load_config(config_path)
    hardware = detect_hardware()
    estimate = estimate_footprint(config, hardware)
    binary = resolve_binary(config)
    checks = {
        "apple_silicon": hardware.metal,
        "llama_server": str(binary) if binary else "missing",
        "model": model_path_status(config.model.path),
        "safe_memory_footprint": estimate.fits_safely,
        "backend_loopback": config.server.backend_host in {"127.0.0.1", "localhost", "::1"},
    }
    print(json.dumps(checks, indent=2))
    return 0 if all(value not in {False, "missing"} for value in checks.values()) else 2


async def _benchmark(args: argparse.Namespace, config_path: Path) -> int:
    import httpx

    config = load_config(config_path)
    endpoint = "chat/completions" if config.model.chat else "completions"
    url = f"http://{config.server.host}:{config.server.port}/v1/{endpoint}"
    semaphore = asyncio.Semaphore(args.concurrency)
    latencies: list[float] = []
    tokens = 0
    token_lock = asyncio.Lock()

    async def one(client: httpx.AsyncClient) -> None:
        nonlocal tokens
        async with semaphore:
            started = time.perf_counter()
            payload: dict[str, object] = {
                "model": config.model.alias,
                "max_tokens": args.max_tokens,
                "temperature": 0,
            }
            if config.model.chat:
                payload["messages"] = [{"role": "user", "content": args.prompt}]
            else:
                payload["prompt"] = args.prompt
            response = await client.post(url, json=payload)
            response.raise_for_status()
            elapsed = time.perf_counter() - started
            body = response.json()
            completion_tokens = int(body.get("usage", {}).get("completion_tokens", 0))
            latencies.append(elapsed)
            async with token_lock:
                tokens += completion_tokens

    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=None) as client:
        await asyncio.gather(*(one(client) for _ in range(args.requests)))
    wall = time.perf_counter() - started
    ordered = sorted(latencies)
    p95_index = max(0, min(len(ordered) - 1, int(len(ordered) * 0.95) - 1))
    print(json.dumps({
        "requests": len(latencies),
        "concurrency": args.concurrency,
        "wall_seconds": round(wall, 3),
        "requests_per_second": round(len(latencies) / wall, 3),
        "completion_tokens_per_second": round(tokens / wall, 3),
        "latency_p50_seconds": round(statistics.median(latencies), 3),
        "latency_p95_seconds": round(ordered[p95_index], 3),
    }, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config_path = args.config.resolve()
    if args.command == "plan":
        return _plan(config_path)
    if args.command == "doctor":
        return _doctor(config_path)
    if args.command == "command":
        from .backend import BackendConfigurationError, build_command, redacted_command

        try:
            print(redacted_command(build_command(load_config(config_path))))
            return 0
        except BackendConfigurationError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if args.command == "serve":
        import uvicorn

        from .app import create_app

        config = load_config(config_path)
        uvicorn.run(create_app(config), host=config.server.host, port=config.server.port)
        return 0
    if args.command == "benchmark":
        return asyncio.run(_benchmark(args, config_path))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
