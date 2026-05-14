"""
LANGGRAPH ORCHESTRATION
Self-RAG / Corrective-RAG using LangGraph StateGraph
Replaces the simple OrchestratorAgent with graph-based pipeline
Supports: retrieval -> rerank -> synthesize -> reflect -> (retry if needed)
"""
import logging
import os
import time
from typing import Annotated, Literal, TypedDict
from dataclasses import dataclass, field

logger = logging.getLogger("rag-swarm.graph")

# Import LangGraph components
try:
    from langgraph.graph import StateGraph, END
    from langgraph.prebuilt import ToolNode
    from langgraph.checkpoint.memory import MemorySaver
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logger.warning("langgraph not available, falling back to simple orchestrator")


@dataclass
class AgentState(TypedDict):
    """Shared state across graph nodes"""
    query: str
    history: list[dict]
    retrieved_chunks: list[dict]
    reranked_chunks: list[dict]
    answer: str
    sources: list[dict]
    confidence: float | None
    latency_ms: dict
    reflection_result: str | None
    attempts: int
    error: str | None


MAX_RETRIES = 3


class LangGraphOrchestrator:
    """
    LangGraph-based orchestrator with Self-RAG pattern:
    - retrieve: Hybrid search (cosine + BM25)
    - rerank: Cross-encoder reranking
    - synthesize: Generate answer with Instructor validation
    - reflect: Check if answer is adequate (retry if not)
    """

    def __init__(self, vectorstore_path: str = "./vectorstore"):
        self.vectorstore_path = vectorstore_path
        self._orchestrator = None  # Lazy-load the underlying agent

        if not LANGGRAPH_AVAILABLE:
            logger.warning("LangGraph not available, using fallback orchestrator")
            return

        self.graph = self._build_graph()
        self.checkpointer = MemorySaver()

    def _lazy_init(self):
        """Lazy initialization of underlying agents"""
        if self._orchestrator is None:
            from .orchestrator import OrchestratorAgent
            self._orchestrator = OrchestratorAgent(vectorstore_path=self.vectorstore_path)
            # Import additional agents
            from .reranker import RerankerAgent
            from .hyde import HyDEAgent
            from .memory_agent import MemoryAgent
            from .instructor_synthesis import InstructorSynthesisAgent

            self.reranker = RerankerAgent()
            self.hyde = HyDEAgent()
            self.memory = MemoryAgent()
            self.synthesis = InstructorSynthesisAgent()

    async def node_retrieve(self, state: AgentState) -> AgentState:
        """Retrieve chunks using HyDE-enhanced hybrid search"""
        self._lazy_init()
        query = state["query"]
        logger.info(f"[GRAPH] Retrieve node: {query[:50]}...")

        t0 = time.time()

        # Optional HyDE query expansion
        hyde_result = await self.hyde.process(query)
        hypothetical_doc = hyde_result.get("hypothetical_doc")
        hypothetical_embedding = hyde_result.get("hypothetical_embedding")

        if hypothetical_embedding:
            logger.info("Using HyDE embedding for retrieval")
            # TODO: pass hypothetical_embedding to retrieval when supported
            retrieved = await self._orchestrator.retrieval.process(query)
        else:
            retrieved = await self._orchestrator.retrieval.process(query)

        retrieval_time = (time.time() - t0) * 1000

        return {
            "retrieved_chunks": retrieved,
            "latency_ms": {**state.get("latency_ms", {}), "retrieval": round(retrieval_time)},
        }

    async def node_rerank(self, state: AgentState) -> AgentState:
        """Rerank retrieved chunks using cross-encoder"""
        self._lazy_init()
        chunks = state.get("retrieved_chunks", [])
        query = state["query"]
        logger.info(f"[GRAPH] Rerank node: {len(chunks)} chunks")

        t0 = time.time()
        if self.reranker and self.reranker.reranker:
            reranked = await self.reranker.process(query, chunks, top_k=5)
        else:
            reranked = chunks[:5]
        rerank_time = (time.time() - t0) * 1000

        return {
            "reranked_chunks": reranked,
            "latency_ms": {**state.get("latency_ms", {}), "rerank": round(rerank_time)},
        }

    async def node_synthesize(self, state: AgentState) -> AgentState:
        """Synthesize answer from reranked chunks"""
        self._lazy_init()
        query = state["query"]
        chunks = state.get("reranked_chunks", state.get("retrieved_chunks", []))
        history = state.get("history", [])

        logger.info(f"[GRAPH] Synthesize node: {query[:50]}...")

        t0 = time.time()

        # Use Instructor-validated synthesis
        try:
            result = await self.synthesis.process(query, chunks, history)
            answer = result.get("answer", "")
            sources = result.get("sources", [])
            confidence = result.get("confidence", 0.5)
        except Exception as e:
            logger.error(f"Instructor synthesis failed: {e}, falling back to basic")
            basic_result = await self._orchestrator.synthesis.process(query, chunks, history)
            answer = basic_result.get("answer", "")
            sources = basic_result.get("sources", [])
            confidence = 0.5

        synthesis_time = (time.time() - t0) * 1000

        # Add to memory
        await self.memory.add_interaction(query, answer)

        return {
            "answer": answer,
            "sources": sources,
            "confidence": confidence,
            "latency_ms": {**state.get("latency_ms", {}), "synthesis": round(synthesis_time)},
        }

    async def node_reflect(self, state: AgentState) -> AgentState:
        """
        Self-RAG reflection: evaluate answer quality
        Returns 'adequate' or 'inadequate' to route next steps
        """
        self._lazy_init()
        query = state["query"]
        answer = state.get("answer", "")
        chunks = state.get("reranked_chunks", state.get("retrieved_chunks", []))

        logger.info(f"[GRAPH] Reflect node: evaluating answer quality")

        # Simple heuristic reflection (in production, use LLM-based evaluation)
        confidence = state.get("confidence", 0.5)

        if not answer or len(answer.strip()) < 10:
            reflection = "inadequate"
        elif confidence < 0.3:
            reflection = "inadequate"
        elif "i don't know" in answer.lower() or "couldn't find" in answer.lower():
            reflection = "inadequate"
        else:
            reflection = "adequate"

        logger.info(f"[GRAPH] Reflection result: {reflection} (confidence={confidence:.2f})")

        return {
            "reflection_result": reflection,
            "attempts": state.get("attempts", 0) + 1,
        }

    def _should_retry(self, state: AgentState) -> Literal["synthesize", "END"]:
        """Conditional edge: retry synthesis if inadequate and attempts < max"""
        if state.get("reflection_result") == "inadequate" and state.get("attempts", 0) < MAX_RETRIES:
            logger.info(f"[GRAPH] Retrying synthesis (attempt {state['attempts']}/{MAX_RETRIES})")
            return "synthesize"
        return END

    def _build_graph(self):
        """Build the LangGraph StateGraph"""
        if not LANGGRAPH_AVAILABLE:
            return None

        from .retrieval import RetrievalAgent
        from .reranker import RerankerAgent
        from .hyde import HyDEAgent
        from .memory_agent import MemoryAgent
        from .instructor_synthesis import InstructorSynthesisAgent

        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("retrieve", self.node_retrieve)
        workflow.add_node("rerank", self.node_rerank)
        workflow.add_node("synthesize", self.node_synthesize)
        workflow.add_node("reflect", self.node_reflect)

        # Edges
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "rerank")
        workflow.add_edge("rerank", "synthesize")
        workflow.add_edge("synthesize", "reflect")

        # Conditional edge: reflect -> retry synthesize or END
        workflow.add_conditional_edges(
            "reflect",
            self._should_retry,
            {
                "synthesize": "synthesize",
                END: END,
            }
        )

        return workflow.compile(checkpointer=MemorySaver())

    async def chat(self, query: str, history: list[dict]) -> dict:
        """Process chat through the graph pipeline"""
        if not LANGGRAPH_AVAILABLE or self.graph is None:
            # Fallback to simple orchestrator
            self._lazy_init()
            logger.warning("LangGraph unavailable, using fallback orchestrator")
            return await self._orchestrator.chat(query, history)

        from .hyde import HyDEAgent
        from .memory_agent import MemoryAgent
        from .reranker import RerankerAgent
        from .instructor_synthesis import InstructorSynthesisAgent

        # Initialize additional agents
        self.reranker = RerankerAgent()
        self.hyde = HyDEAgent()
        self.memory = MemoryAgent()
        self.synthesis = InstructorSynthesisAgent()

        initial_state = AgentState(
            query=query,
            history=history,
            retrieved_chunks=[],
            reranked_chunks=[],
            answer="",
            sources=[],
            confidence=None,
            latency_ms={},
            reflection_result=None,
            attempts=0,
            error=None,
        )

        config = {"configurable": {"thread_id": f"rag-{hash(query) % 10000}"}}

        try:
            result = await self.graph.ainvoke(initial_state, config)
            return {
                "answer": result.get("answer", ""),
                "sources": result.get("sources", []),
                "latency_ms": result.get("latency_ms", {}),
            }
        except Exception as e:
            logger.error(f"Graph execution failed: {e}")
            # Fallback
            self._lazy_init()
            return await self._orchestrator.chat(query, history)