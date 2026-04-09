FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# ── Instalar dependencias de todos los módulos que corren en este contenedor ──
# (frontend + agent + mcp_server + vector_db)
COPY frontend/requirements.txt    /tmp/req_frontend.txt
COPY agent/requirements.txt       /tmp/req_agent.txt
COPY mcp_server/requirements.txt  /tmp/req_mcp.txt
COPY vector_db/requirements.txt   /tmp/req_vector.txt

RUN pip install --no-cache-dir \
    -r /tmp/req_frontend.txt \
    -r /tmp/req_agent.txt \
    -r /tmp/req_mcp.txt \
    -r /tmp/req_vector.txt

# ── Copiar código fuente manteniendo la estructura de carpetas ──
# Necesaria para que los sys.path.insert relativos funcionen igual que en local
COPY frontend/   /app/frontend/
COPY agent/      /app/agent/
COPY mcp_server/ /app/mcp_server/
COPY vector_db/  /app/vector_db/

EXPOSE 8501

# fileWatcherType none evita los warnings de torchvision en Streamlit
CMD ["streamlit", "run", "/app/frontend/app/app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.fileWatcherType=none"]
