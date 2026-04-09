FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY agent/requirements.txt      /tmp/req_agent.txt
COPY mcp_server/requirements.txt /tmp/req_mcp.txt
COPY vector_db/requirements.txt  /tmp/req_vector.txt

RUN pip install --no-cache-dir \
    -r /tmp/req_agent.txt \
    -r /tmp/req_mcp.txt \
    -r /tmp/req_vector.txt

COPY agent/      /app/agent/
COPY mcp_server/ /app/mcp_server/
COPY vector_db/  /app/vector_db/

# Con PYTHONPATH, los módulos de cada capa se importan por nombre sin conflictos
ENV PYTHONPATH="/app/agent/app:/app/mcp_server/app:/app/vector_db/app"

EXPOSE 8000

# "api:app" encuentra /app/agent/app/api.py gracias al PYTHONPATH
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
