import sys
import uuid
from pathlib import Path

import streamlit as st

# ── Path al agente ──────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agent" / "app"))
from agent import BancolombiaAgent

# ── Configuración de la página ──────────────────────────────────────
st.set_page_config(
    page_title="Asistente Bancolombia",
    page_icon="🏦",
    layout="centered",
)

st.title("🏦 Asistente Virtual Bancolombia")
st.caption("Pregunta sobre productos, servicios, tarifas y más.")

# ── Inicialización del agente (una sola vez por sesión del servidor) ─
@st.cache_resource(show_spinner="Cargando base de conocimiento...")
def get_agent() -> BancolombiaAgent:
    return BancolombiaAgent()

agent = get_agent()

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

    # Mostrar mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Obtener respuesta del agente
    with st.chat_message("assistant"):
        with st.spinner("Consultando base de conocimiento..."):
            try:
                result = agent.chat(
                    message=prompt,
                    session_id=st.session_state.session_id,
                )
                response = result["response"]
                sources = result.get("sources", [])
            except Exception as e:
                response = f"Lo siento, ocurrió un error al procesar tu consulta. Por favor intenta de nuevo.\n\n_Error: {e}_"
                sources = []

        st.markdown(response)

        if sources:
            with st.expander("📎 Fuentes consultadas"):
                for url in sources:
                    st.markdown(f"- [{url}]({url})")

    # Guardar en historial
    st.session_state.messages.append({
        "role": "assistant",
        "content": response,
        "sources": sources,
    })

# ── Sidebar con info de sesión ──────────────────────────────────────
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
