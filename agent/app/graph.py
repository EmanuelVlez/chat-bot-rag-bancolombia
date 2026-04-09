"""
Grafo LangGraph del agente Bancolombia.

Nodos:
- agent:     LLM local (Ollama) decide si responder o llamar tools MCP.
- tools:     Ejecuta las tools MCP seleccionadas por el agente.
- summarize: Cuando el historial supera MAX_MSGS, comprime los mensajes
             antiguos en un resumen (memoria mediano plazo).
"""

import os
import sys
from pathlib import Path
from typing import Annotated, TypedDict

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "vector_db" / "app"))

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, RemoveMessage, AIMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from embedder import Embedder
from vector_store import VectorStore
from prompts import SYSTEM_PROMPT

# Instancias compartidas para búsqueda directa (sin overhead de subprocess MCP)
_embedder = Embedder()
_vector_store = VectorStore()

# Saludos y frases que no requieren búsqueda
_GREETINGS = {"hola", "buenos días", "buenas tardes", "buenas noches",
              "gracias", "adiós", "hasta luego", "ok", "okay", "bye"}

MAX_MSGS_BEFORE_SUMMARY = 12
# Configurable via variable de entorno — permite cambiar modelo sin tocar código
LLM_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    summary: str        # mediano plazo: resumen de mensajes anteriores
    user_context: str   # largo plazo: contexto del perfil del usuario
    sources: list[str]  # URLs de los chunks recuperados en esta vuelta


def build_graph(tools: list):
    import json
    llm = ChatOllama(model=LLM_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)
    llm_with_tools = llm.bind_tools(tools)

    def _is_greeting(text: str) -> bool:
        return text.strip().lower() in _GREETINGS

    # ── Nodo: agente ────────────────────────────────────────────────
    async def agent_node(state: AgentState) -> dict:
        summary = state.get("summary", "")
        user_ctx = state.get("user_context", "")
        messages = state["messages"]

        last_human = next(
            (m for m in reversed(messages) if getattr(m, "type", "") == "human"),
            None,
        )
        last_text = last_human.content if last_human else ""

        # Si el último mensaje ya es un ToolMessage (venimos del nodo tools),
        # dejar que el LLM sintetice la respuesta final directamente.
        last_msg = messages[-1]
        already_searched = isinstance(last_msg, ToolMessage)

        # Búsqueda directa en ChromaDB para garantizar contexto relevante.
        sources: list[str] = []
        if not already_searched and not _is_greeting(last_text):
            embedding = _embedder.embed_query(last_text)
            results = _vector_store.search(embedding, n_results=5)

            # Extraer URLs únicas de los resultados (fuentes garantizadas)
            seen = set()
            for r in results:
                url = r.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    sources.append(url)

            tool_result = {
                "query": last_text,
                "total_found": len(results),
                "results": results,
            }
            tool_result_str = json.dumps(tool_result, ensure_ascii=False)

            fake_id = "forced_search_001"
            ai_with_call = AIMessage(
                content="",
                tool_calls=[{
                    "id": fake_id,
                    "name": "search_knowledge_base",
                    "args": {"query": last_text, "n_results": 5},
                }],
            )
            tool_msg = ToolMessage(content=tool_result_str, tool_call_id=fake_id)
            messages = messages + [ai_with_call, tool_msg]

        system = SYSTEM_PROMPT
        if user_ctx:
            system += f"\n\nContexto del usuario: {user_ctx}"
        if summary:
            system += f"\n\nResumen de la conversación anterior:\n{summary}"

        response = await llm_with_tools.ainvoke([SystemMessage(system)] + messages)
        return {"messages": [response], "sources": sources}

    # ── Nodo: resumen (memoria mediano plazo) ────────────────────────
    def summarize_node(state: AgentState) -> dict:
        msgs = state["messages"]
        older = msgs[:-4]  # conserva solo los últimos 4 mensajes

        existing = state.get("summary", "")
        if existing:
            prompt = (
                f"Resumen previo:\n{existing}\n\n"
                f"Amplía el resumen con esta nueva parte de la conversación "
                f"(máximo 4 oraciones):\n"
            )
        else:
            prompt = (
                "Resume esta conversación sobre Bancolombia en máximo 4 oraciones, "
                "conservando los puntos clave que el usuario mencionó:\n"
            )

        for m in older:
            prompt += f"\n{m.type}: {str(m.content)[:300]}"

        new_summary = llm.invoke(prompt).content

        # Elimina mensajes viejos del estado
        remove = [RemoveMessage(id=m.id) for m in older]
        return {"messages": remove, "summary": new_summary}

    # ── Enrutamiento ─────────────────────────────────────────────────
    def route_after_agent(state: AgentState) -> str:
        last = state["messages"][-1]
        # Si el agente quiere llamar tools
        if getattr(last, "tool_calls", None):
            return "tools"
        # Si el historial es largo, comprimir
        if len(state["messages"]) > MAX_MSGS_BEFORE_SUMMARY:
            return "summarize"
        return END

    # ── Construcción del grafo ───────────────────────────────────────
    tool_node = ToolNode(tools)

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("summarize", summarize_node)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "summarize": "summarize", END: END},
    )
    graph.add_edge("tools", "agent")
    graph.add_edge("summarize", END)

    return graph.compile(checkpointer=MemorySaver())
