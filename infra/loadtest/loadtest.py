#!/usr/bin/env python3
"""Capacity load test for CollaBrains (Phase 6d, ADR 0015).

Fires N concurrent requests against /chat (LLM-bound) and /search
(DB-only, baseline) at increasing concurrency, reporting latency
percentiles and error rates. Uses distinct pre-provisioned users per
request so the per-user rate limiter (30/min) never interferes -- this
measures the AI Gateway/Ollama ceiling, not the rate limiter's.

Usage: python3 loadtest.py
"""
import asyncio
import statistics
import sys
import time

import httpx

BASE_URL = "http://localhost:8000"
USERS = [(f"loadtest{i}", "LoadTest123!") for i in range(1, 9)]
CONCURRENCY_LEVELS = [1, 2, 4, 8]


async def get_token(client: httpx.AsyncClient, username: str, password: str) -> str:
    resp = await client.post(
        "/auth/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def timed_request(client: httpx.AsyncClient, method: str, path: str, token: str, **kwargs) -> tuple[float, int]:
    start = time.monotonic()
    try:
        resp = await client.request(method, path, headers={"Authorization": f"Bearer {token}"}, **kwargs)
        elapsed = time.monotonic() - start
        return elapsed, resp.status_code
    except Exception:
        elapsed = time.monotonic() - start
        return elapsed, -1


def percentile(data: list[float], pct: float) -> float:
    if not data:
        return 0.0
    data = sorted(data)
    idx = min(int(len(data) * pct), len(data) - 1)
    return data[idx]


async def run_level(client: httpx.AsyncClient, tokens: list[str], concurrency: int, method: str, path: str, body_fn) -> dict:
    selected = tokens[:concurrency]
    tasks = [
        timed_request(client, method, path, tok, **body_fn(i))
        for i, tok in enumerate(selected)
    ]
    results = await asyncio.gather(*tasks)
    latencies = [r[0] for r in results]
    statuses = [r[1] for r in results]
    errors = sum(1 for s in statuses if s < 200 or s >= 300)
    return {
        "concurrency": concurrency,
        "n": len(results),
        "errors": errors,
        "min": min(latencies),
        "p50": percentile(latencies, 0.5),
        "p95": percentile(latencies, 0.95),
        "max": max(latencies),
    }


def print_row(label: str, r: dict) -> None:
    print(
        f"  {label:8s} concurrency={r['concurrency']:2d}  "
        f"n={r['n']}  errors={r['errors']}  "
        f"min={r['min']:.2f}s  p50={r['p50']:.2f}s  p95={r['p95']:.2f}s  max={r['max']:.2f}s"
    )


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=300.0) as client:
        print("Authenticating load-test users...")
        tokens = [await get_token(client, u, p) for u, p in USERS]
        print(f"  {len(tokens)} tokens acquired\n")

        print("=== /search (DB-only baseline) ===")
        for level in CONCURRENCY_LEVELS:
            r = await run_level(
                client, tokens, level, "GET", "/search",
                lambda i: {"params": {"q": "werkstraf"}},
            )
            print_row("search", r)

        print("\n=== /chat (LLM-bound, retrieval + generation) ===")
        for level in CONCURRENCY_LEVELS:
            r = await run_level(
                client, tokens, level, "POST", "/chat",
                lambda i: {"json": {"message": "What is the appointment date mentioned in the documents?", "history": []}},
            )
            print_row("chat", r)


if __name__ == "__main__":
    asyncio.run(main())
