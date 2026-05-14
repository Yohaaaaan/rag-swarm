# RAG Swarm Performance Optimization Plan

## Overview

**Goal**: Test all configuration combinations to find optimal speed/accuracy balance
**Date**: 2026-05-14
**Stack**: FastAPI + ChromaDB + DeepSeek-V4-Flash + OpenAI embeddings

---

## Test Matrix

### Variables to Test

| Variable | Current | Test Values | Impact |
|----------|---------|-------------|--------|
| `HYDE_ENABLED` | true | true / false | ~20s latency per query |
| `TOP_K` | 5 | 5, 10, 15 | retrieval quality |
| `TEMPERATURE` | 0.5 | 0.3, 0.5, 0.7 | response creativity |
| `CHUNK_SIZE` | 300 | 300, 500 | context granularity |
| `SEMANTIC_WEIGHT` | 0.7 | 0.6, 0.7, 0.8 | retrieval balance |

### Test Protocol

**Dataset**: 10 questions from previous test run
**Metrics**: Answer quality (0-10), latency (ms), citation accuracy
**Ground Truth**: Manual evaluation of whether answer matches chunk content

---

## Phase 0: Baseline (Current Config)

**Status**: ⬜ Not Started

Record current performance as baseline:
- HYDE=true, TOP_K=5, TEMP=0.5, CHUNK=300, SEM=0.7

**Expected**: ~6-9s latency, good accuracy

---

## Phase 1: HyDE Impact (Est: 5)

### 1A: HyDE OFF (Est: 2)
```
Config: HYDE=false, TOP_K=5, TEMP=0.5, CHUNK=300, SEM=0.7
```
- Disable HyDE to measure pure retrieval+synthesis latency
- Expected: ~3-5s latency

### 1B: HyDE ON (baseline comparison) (Est: 3)
```
Config: HYDE=true, TOP_K=5, TEMP=0.5, CHUNK=300, SEM=0.7
```
- Measure full pipeline with HyDE
- Expected: ~23s latency (HyDE adds ~20s)

---

## Phase 2: Retrieval Quality (Est: 8)

### 2A: TOP_K=5 vs 10 (Est: 3)
```
Config A: HYDE=false, TOP_K=5, TEMP=0.5, CHUNK=300, SEM=0.7
Config B: HYDE=false, TOP_K=10, TEMP=0.5, CHUNK=300, SEM=0.7
```

### 2B: TOP_K=10 vs 15 (Est: 3)
```
Config A: HYDE=false, TOP_K=10, TEMP=0.5, CHUNK=300, SEM=0.7
Config B: HYDE=false, TOP_K=15, TEMP=0.5, CHUNK=300, SEM=0.7
```

### 2C: SEM_WEIGHT variations (Est: 2)
```
Config A: SEM=0.6, KEYWORD=0.4
Config B: SEM=0.8, KEYWORD=0.2
```

---

## Phase 3: Synthesis Quality (Est: 5)

### 3A: Temperature sweep (Est: 3)
```
Config A: TEMP=0.3 (factual)
Config B: TEMP=0.5 (balanced) ← current
Config C: TEMP=0.7 (creative)
```

### 3B: Chunk size impact (Est: 2)
```
Config A: CHUNK=300 (current)
Config B: CHUNK=500 (larger context)
```

---

## Phase 4: Optimal Config Validation (Est: 5)

Test best configuration from Phases 1-3 with all 10 questions:
- Measure final latency
- Measure answer quality (0-10)
- Measure citation accuracy

---

## Configuration Scripts

### Script: test_config.py

```python
"""
Test different RAG configurations
Usage: python test_config.py --hyde false --top-k 10 --temp 0.3
"""
import asyncio
import argparse
import httpx
import time

CONFIG = {
    "hyde": {"env": "HYDE_ENABLED", "values": ["true", "false"]},
    "top_k": {"current": 5, "test": [5, 10, 15]},
    "temperature": {"current": 0.5, "test": [0.3, 0.5, 0.7]},
    "chunk_size": {"current": 300, "test": [300, 500]},
    "sem_weight": {"current": 0.7, "test": [0.6, 0.7, 0.8]},
}

TEST_QUERIES = [
    "What is the capital of France?",
    # ... 9 more questions
]

async def test_config(hyde: bool, top_k: int, temp: float):
    """Test a specific configuration"""
    # Implementation here
    pass

async def run_all_tests():
    """Run full test matrix"""
    results = []
    # Iterate all combinations
    return results
```

---

## Acceptance Criteria

- [ ] Phase 0: Baseline recorded
- [ ] Phase 1: HyDE impact measured
- [ ] Phase 2: TOP_K optimal found
- [ ] Phase 3: Temperature optimal found
- [ ] Phase 4: Best config validated
- [ ] Document optimal settings in README

---

## Expected Results

| Config | Latency | Accuracy | Best For |
|--------|---------|----------|----------|
| HyDE OFF, TOP_K=5, TEMP=0.5 | ~3-5s | Good | Fast responses |
| HyDE ON, TOP_K=10, TEMP=0.5 | ~25s | Best | High accuracy |
| HyDE OFF, TOP_K=15, TEMP=0.3 | ~5s | Very Good | Balanced |

---

## Next Steps

1. Implement `test_config.py` script
2. Run Phase 0 baseline
3. Run Phase 1 (HyDE comparison)
4. Analyze results
5. Commit optimal config to `.env`
