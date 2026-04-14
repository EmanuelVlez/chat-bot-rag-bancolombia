"""
Grafo LangGraph del agente Bancolombia.

Nodos:
- agent:     LLM local (Ollama) decide si responder o llamar tools MCP.
- tools:     Ejecuta las tools MCP seleccionadas por el agente.
- summarize: Cuando el historial supera MAX_MSGS, comprime los mensajes
             antiguos en un resumen (memoria mediano plazo).

Todo acceso a ChromaDB pasa exclusivamente por el MCP server.
"""

import os
import re
from typing import Annotated, TypedDict

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, RemoveMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from prompts import SYSTEM_PROMPT

MAX_MSGS_BEFORE_SUMMARY = 12
LLM_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    summary: str        # mediano plazo: resumen de mensajes anteriores
    user_context: str   # largo plazo: contexto del perfil del usuario
    sources: list[str]  # URLs extraídas de los tool results MCP


def build_graph(tools: list):
    llm = ChatOllama(model=LLM_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)
    llm_with_tools = llm.bind_tools(tools)

    # ── Nodo: agente ────────────────────────────────────────────────
    async def agent_node(state: AgentState) -> dict:
        summary = state.get("summary", "")
        user_ctx = state.get("user_context", "")
        messages = state["messages"]

        # Extraer URLs solo de los ToolMessages del turno actual
        # (los que aparecen después del último HumanMessage)
        last_human_idx = 0
        for i, msg in enumerate(messages):
            if getattr(msg, "type", "") == "human":
                last_human_idx = i

        sources: list[str] = []
        url_pattern = r"https://www\.bancolombia\.com[^\s\)\]\,\"\']*"
        for msg in messages[last_human_idx:]:
            if isinstance(msg, ToolMessage):
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                found = re.findall(url_pattern, content)
                for url in found:
                    if url not in sources:
                        sources.append(url)

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
