"""
MEMORY AGENT
Intelligent conversation memory using Mem0
Semantic + keyword + entity fusion for context condensation
Replaces simple list-based history
"""
import logging
import os

logger = logging.getLogger("rag-swarm.memory")

DEFAULT_USER_ID = "rag-swarm-default"


class MemoryAgent:
    """Mem0-backed intelligent memory for conversation context"""

    def __init__(self, user_id: str = DEFAULT_USER_ID):
        self.user_id = user_id
        try:
            from mem0 import Memory
        except ImportError:
            logger.warning("mem0 not installed, falling back to simple history")
            self.memory = None
            return

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set, memory will be disabled")
            self.memory = None
            return

        try:
            from mem0.configs.base import MemoryConfig, LlmConfig, EmbedderConfig, VectorStoreConfig
            vector_store_config = VectorStoreConfig(provider="chroma", config={})
            llm_config = LlmConfig(provider="openai", config={"api_key": api_key})
            embedder_config = EmbedderConfig(provider="openai", config={"api_key": api_key})
            memory_config = MemoryConfig(
                vector_store=vector_store_config,
                llm=llm_config,
                embedder=embedder_config,
            )
            self.memory = Memory(memory_config)
            logger.info(f"Memory agent initialized for user: {user_id}")
        except Exception as e:
            logger.error(f"Failed to initialize memory: {e}")
            self.memory = None

    async def add_interaction(self, query: str, answer: str | None = None, metadata: dict | None = None):
        """Add a user query and optional assistant answer to memory"""
        if not self.memory:
            return

        try:
            messages = [{"role": "user", "content": query}]
            if answer:
                messages.append({"role": "assistant", "content": answer})

            self.memory.add(messages, user_id=self.user_id, metadata=metadata or {})
            logger.info("Added interaction to memory")
        except Exception as e:
            logger.error(f"Failed to add to memory: {e}")

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search memory for relevant past interactions"""
        if not self.memory:
            return []

        try:
            results = self.memory.search(query, top_k=top_k, user_id=self.user_id)
            logger.info(f"Memory search found {len(results)} relevant interactions")
            return results
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []

    def get_recent_context(self, query: str, history: list[dict], max_turns: int = 5) -> str:
        """
        Build a context string from:
        1. Semantic memory search results
        2. Recent conversation history

        This replaces simple history list concatenation with intelligent retrieval.
        """
        if not history and not self.memory:
            return "No previous conversation."

        context_parts = []

        # Add memory search results if available
        if self.memory and query:
            memory_results = []
            try:
                memory_results = self.memory.search(query, top_k=3, user_id=self.user_id)
            except Exception:
                pass

            if memory_results:
                context_parts.append("RELEVANT PAST INTERACTIONS:")
                for r in memory_results:
                    role = r.get("role", "user")
                    content = r.get("content", "")
                    context_parts.append(f"- {role.upper()}: {content}")

        # Add recent conversation history
        if history:
            if context_parts:
                context_parts.append("")
            context_parts.append("RECENT CONVERSATION:")
            for turn in history[-max_turns:]:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                context_parts.append(f"- {role.upper()}: {content}")

        return "\n".join(context_parts) if context_parts else "No previous conversation."