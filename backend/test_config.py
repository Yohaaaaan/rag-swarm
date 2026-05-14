"""
RAG Swarm Performance Test Script
Tests different configurations to find optimal speed/accuracy balance
Usage: python test_config.py --hyde false --top-k 10 --temp 0.3
"""
import asyncio
import argparse
import os
import sys
import time
from dataclasses import dataclass
from typing import Optional

import httpx

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

TEST_QUERIES = [
    "What agent manages the RAG pipeline?",
    "What chunk size is used for text splitting?",
    "How does hybrid retrieval work?",
    "What is the semantic weight in retrieval?",
    "What embedding model is used?",
    "How many agents are in the swarm?",
    "What is the purpose of the reranker?",
    "How is citation accuracy verified?",
    "What temperature is used for synthesis?",
    "What is the max history for conversation?",
]

@dataclass
class TestResult:
    query: str
    answer: str
    latency_ms: int
    sources_count: int
    can_answer: bool
    config: dict


def load_env_config() -> dict:
    """Load current configuration from environment"""
    return {
        "hyde": os.getenv("HYDE_ENABLED", "true").lower() == "true",
        "top_k": 5,  # default, would need orchestrator change
        "temperature": 0.5,
    }


async def test_query(client: httpx.AsyncClient, query: str, config: dict) -> TestResult:
    """Test a single query with given config"""
    start = time.time()

    try:
        response = await client.post(
            f"{BACKEND_URL}/chat",
            json={"query": query, "history": []},
            timeout=60.0,
        )
        response.raise_for_status()
        result = response.json()

        latency = int((time.time() - start) * 1000)

        return TestResult(
            query=query,
            answer=result.get("answer", ""),
            latency_ms=latency,
            sources_count=len(result.get("sources", [])),
            can_answer=True,
            config=config,
        )
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        return TestResult(
            query=query,
            answer=f"ERROR: {e}",
            latency_ms=latency,
            sources_count=0,
            can_answer=False,
            config=config,
        )


async def run_test_suite(config: dict, queries: list[str]) -> list[TestResult]:
    """Run all test queries with a configuration"""
    results = []
    async with httpx.AsyncClient() as client:
        for query in queries:
            print(f"  Query: {query[:50]}...")
            result = await test_query(client, query, config)
            results.append(result)
            print(f"    Latency: {result.latency_ms}ms, Answer length: {len(result.answer)} chars")
    return results


def print_results_table(results: list[TestResult]):
    """Print formatted results table"""
    print("\n" + "=" * 80)
    print(f"{'Query':<40} {'Latency':>10} {'Sources':>8} {'Status':>10}")
    print("=" * 80)

    total_latency = 0
    answered = 0

    for r in results:
        status = "OK" if r.can_answer else "FAIL"
        query_short = r.query[:37] + "..." if len(r.query) > 40 else r.query
        print(f"{query_short:<40} {r.latency_ms:>10}ms {r.sources_count:>8} {status:>10}")
        total_latency += r.latency_ms
        if r.can_answer:
            answered += 1

    print("=" * 80)
    avg_latency = total_latency / len(results) if results else 0
    print(f"Average latency: {avg_latency:.0f}ms | Answered: {answered}/{len(results)}")


async def main():
    parser = argparse.ArgumentParser(description="Test RAG configurations")
    parser.add_argument("--hyde", type=str, choices=["true", "false"], default=None,
                        help="Enable HyDE (overrides .env)")
    parser.add_argument("--top-k", type=int, default=None,
                        help="TOP_K for retrieval")
    parser.add_argument("--temp", type=float, default=None,
                        help="Temperature for synthesis")
    parser.add_argument("--config-name", type=str, default="default",
                        help="Name for this config test")

    args = parser.parse_args()

    # Build config dict
    config = load_env_config()
    if args.hyde is not None:
        config["hyde"] = args.hyde == "true"
    if args.top_k is not None:
        config["top_k"] = args.top_k
    if args.temp is not None:
        config["temperature"] = args.temp

    print(f"\n{'='*60}")
    print(f"TEST CONFIGURATION: {args.config_name}")
    print(f"{'='*60}")
    print(f"HyDE: {config['hyde']}")
    print(f"TOP_K: {config.get('top_k', 5)}")
    print(f"Temperature: {config['temperature']}")
    print(f"Backend: {BACKEND_URL}")
    print(f"Queries: {len(TEST_QUERIES)}")
    print(f"{'='*60}\n")

    print("Running test suite...")
    results = await run_test_suite(config, TEST_QUERIES)

    print_results_table(results)

    # Save results
    import json
    results_file = f"test_results_{args.config_name}_{int(time.time())}.json"
    with open(results_file, "w") as f:
        json.dump({
            "config": config,
            "config_name": args.config_name,
            "results": [
                {"query": r.query, "latency_ms": r.latency_ms, "can_answer": r.can_answer,
                 "answer_length": len(r.answer), "sources_count": r.sources_count}
                for r in results
            ]
        }, f, indent=2)

    print(f"\nResults saved to: {results_file}")


if __name__ == "__main__":
    asyncio.run(main())