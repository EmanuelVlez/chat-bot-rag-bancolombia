import os
import re
import uuid

import requests
import streamlit as st

AGENT_URL = os.getenv("AGENT_URL", "http://localhost:8000")

# ── Configuración de la página ──────────────────────────────────────
st.set_page_config(
    page_title="Asistente Bancolombia",
    page_icon="🏦",
    layout="centered",
)

st.title("🏦 Asistente Virtual Bancolombia")
st.caption("Pregunta sobre productos, servicios, tarifas y más.")

# ── Estado de sesión ────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Historial de conversación ───────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("📎 Fuentes consultadas"):
                for url in msg["sources"]:
                    st.markdown(f"- [{url}]({url})")

# ── Input del usuario ───────────────────────────────────────────────
if prompt := st.chat_input("¿En qué te puedo ayudar?"):

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Consultando base de conocimiento..."):
            try:
                resp = requests.post(
                    f"{AGENT_URL}/chat",
                    json={"message": prompt, "session_id": st.session_state.session_id},
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                response = data["response"]
                sources = data.get("sources", [])

                # Eliminar URLs y sección de fuentes del texto
                for url in sources:
                    response = response.replace(url, "")
                response = re.sub(r'\s*https://www\.bancolombia\.com\S*', '', response)
                response = re.sub(r'\*{0,2}Fuentes:?\*{0,2}.*', '', response, flags=re.DOTALL | re.IGNORECASE)
                response = response.strip()

            except requests.exceptions.ConnectionError:
                response = "No se pudo conectar con el agente. Verifica que el servicio esté corriendo."
                sources = []
            except Exception as e:
                response = f"Lo siento, ocurrió un error al procesar tu consulta.\n\n_Error: {e}_"
                sources = []

        st.markdown(response)

        if sources:
            with st.expander("📎 Fuentes consultadas"):
                for url in sources:
                    st.markdown(f"- [{url}]({url})")

    st.session_state.messages.append({
        "role": "assistant",
        "content": response,
        "sources": sources,
    })

# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Sesión")
    st.caption(f"ID: `{st.session_state.session_id[:8]}...`")
    st.caption(f"Mensajes: {len(st.session_state.messages)}")

    if st.button("🗑️ Nueva conversación"):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

    st.divider()
    st.header("Categorías disponibles")
    st.caption(
        "créditos · cuentas · seguros · vivienda · tarjetas · "
        "beneficios · movilidad · transacciones · contactanos · y más"
    )
