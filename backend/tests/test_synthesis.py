import pytest
import asyncio
from agents.synthesis import SynthesisAgent

class TestSynthesisAsync:
    def test_synthesis_agent_initializes(self):
        """SynthesisAgent should initialize without openai client"""
        # Note: requires DEEPINFRA_API_KEY env var - will skip if not set
        import os
        if not os.getenv("DEEPINFRA_API_KEY"):
            pytest.skip("DEEPINFRA_API_KEY not set")

        agent = SynthesisAgent()
        assert hasattr(agent, 'api_key')
        assert hasattr(agent, 'base_url')
        assert agent.base_url == "https://api.deepinfra.com/v1/openai"

    def test_format_context_uses_chunk_index(self):
        """Context should format as [filename:chunk_index], not page_number"""
        import os
        if not os.getenv("DEEPINFRA_API_KEY"):
            pytest.skip("DEEPINFRA_API_KEY not set")

        agent = SynthesisAgent()
        chunks = [
            {"metadata": {"filename": "test.txt", "chunk_index": 0}, "content": "First chunk"},
            {"metadata": {"filename": "test.txt", "chunk_index": 1}, "content": "Second chunk"},
        ]
        ctx = agent._format_context(chunks)
        assert "[test.txt:0]" in ctx
        assert "[test.txt:1]" in ctx
        assert "test.txt:page" not in ctx.lower()

    def test_format_context_page_fallback(self):
        """When chunk_index missing, should fallback to page_number"""
        import os
        if not os.getenv("DEEPINFRA_API_KEY"):
            pytest.skip("DEEPINFRA_API_KEY not set")

        agent = SynthesisAgent()
        chunks = [
            {"metadata": {"filename": "doc.pdf", "page_number": 3}, "content": "Page 3"},
        ]
        ctx = agent._format_context(chunks)
        assert "[doc.pdf:3]" in ctx

    @pytest.mark.asyncio
    async def test_concurrent_synthesis_no_block(self):
        """Fire 2 concurrent synthesis calls - both should complete without blocking"""
        import os
        if not os.getenv("DEEPINFRA_API_KEY"):
            pytest.skip("DEEPINFRA_API_KEY not set")

        agent = SynthesisAgent()
        chunks = [{"metadata": {"filename": "t.txt", "chunk_index": 0}, "content": "test"}]

        async def call_synthesis():
            return await agent.process("hello", chunks, [])

        # Both should start nearly simultaneously, not sequentially
        results = await asyncio.gather(call_synthesis(), call_synthesis())
        assert len(results) == 2
        assert all("answer" in r for r in results)
