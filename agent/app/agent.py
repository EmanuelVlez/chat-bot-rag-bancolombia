"""
BancolombiaAgent: cliente MCP + LangGraph + memoria.

Expone una interfaz síncrona (chat) compatible con Streamlit,
internamente usa un event loop dedicado para manejar async MCP.
"""

import asyncio
import re
import threading
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

from graph import build_graph
from memory import UserProfileStore

MCP_SERVER_SCRIPT = str(
    Path(__file__).parent.parent.parent / "mcp_server" / "app" / "main.py"
)


class BancolombiaAgent:
    """
    Agente conversacional que actúa como cliente MCP.

    Memoria:
    - Corto plazo:   historial de mensajes en LangGraph MemorySaver (por session_id).
    - Mediano plazo: resumen automático cuando el historial supera 12 mensajes.
    - Largo plazo:   perfil de usuario en SQLite (intereses, frecuencia de uso).
    """

    def __init__(self):
        self.profile_store = UserProfileStore()

        # Event loop dedicado en hilo separado para async MCP
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

        # Inicializar MCP + grafo de forma síncrona (bloquea hasta que carga)
        future = asyncio.run_coroutine_threadsafe(self._async_init(), self._loop)
        future.result(timeout=120)

    async def _async_init(self):
        self._mcp_client = MultiServerMCPClient(
            {
                "bancolombia": {
                    "command": "python",
                    "args": [MCP_SERVER_SCRIPT],
                    "transport": "stdio",
                }
            }
        )
        # v0.1.0+: ya no se usa como context manager
        tools = await self._mcp_client.get_tools()
        self._graph = build_graph(tools)
        print(f"Agente listo con {len(tools)} tools MCP.")

    def chat(self, message: str, session_id: str) -> dict:
        """
        Interfaz síncrona para Streamlit.

        Args:
            message:    Mensaje del usuario.
            session_id: ID único de sesión (thread de memoria).

        Returns:
            dict con 'response' (str) y 'sources' (list[str]).
        """
        # Cargar contexto de largo plazo del usuario
        user_context = self.profile_store.context_for_prompt(session_id)

        future = asyncio.run_coroutine_threadsafe(
            self._async_chat(message, session_id, user_context),
            self._loop,
        )
        result = future.result(timeout=120)

        # Registrar consulta en perfil (largo plazo)
        category = result.get("category")
        self.profile_store.record_query(session_id, category)

        return result

    async def _async_chat(
        self, message: str, session_id: str, user_context: str
    ) -> dict:
        config = {"configurable": {"thread_id": session_id}}

        result = await self._graph.ainvoke(
            {
                "messages": [HumanMessage(content=message)],
                "user_context": user_context,
            },
            config=config,
        )

        last_msg = result["messages"][-1]
        response_text = last_msg.content if isinstance(last_msg.content, str) else str(last_msg.content)

        sources = self._extract_sources(response_text)
        category = self._extract_category(result["messages"])

        return {
            "response": response_text,
            "sources": sources,
            "category": category,
        }

    @staticmethod
    def _extract_sources(text: str) -> list[str]:
        """Extrae URLs de bancolombia.com mencionadas en la respuesta."""
        pattern = r"https://www\.bancolombia\.com[^\s\)\]\,\"\']*"
        return list(dict.fromkeys(re.findall(pattern, text)))

    @staticmethod
    def _extract_category(messages: list) -> str | None:
        """Infiere la categoría de la consulta desde los tool results."""
        for msg in reversed(messages):
            content = getattr(msg, "content", "")
            if isinstance(content, str) and '"category"' in content:
                match = re.search(r'"category":\s*"([^"]+)"', content)
                if match:
                    return match.group(1)
        return None

    def close(self):
        """Limpia recursos al cerrar la aplicación."""
        self._loop.call_soon_threadsafe(self._loop.stop)
