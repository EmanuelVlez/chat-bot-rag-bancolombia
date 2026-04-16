"""
API HTTP para el agente Bancolombia.
FastAPI envuelve BancolombiaAgent y expone un endpoint /chat
que el contenedor frontend consume via HTTP.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agent import BancolombiaAgent

app = FastAPI(title="Bancolombia Agent API", version="1.0.0")

# Una sola instancia del agente para toda la vida del proceso
_agent = BancolombiaAgent()


class ChatRequest(BaseModel):
    message: str
    session_id: str


class ChatResponse(BaseModel):
    response: str
    sources: list[str]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stats")
def stats():
    """Estadísticas de la base de conocimiento (lee el resource knowledge-base://stats del MCP server)."""
    try:
        return {"stats": _agent.get_stats()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")
    try:
        result = _agent.chat(message=req.message, session_id=req.session_id)
        return ChatResponse(
            response=result["response"],
            sources=result.get("sources", []),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
