# -*- coding: utf-8 -*-
"""
app.py — Interfaz de Streamlit para El Adoptador.
Corre con:  streamlit run app.py
"""

import streamlit as st

st.set_page_config(page_title="El Adoptador 🐾", page_icon="🐾", layout="centered")

# La primera vez que se importa asistente.py puede tardar (carga modelos,
# y si no hay un modelo guardado, entrena LoRA una sola vez).
with st.spinner("Cargando El Adoptador (la primera vez puede tardar un par de minutos)…"):
    from asistente import atender

EMOJI = {"SOLICITUD": "📝", "PREGUNTA": "❓", "QUEJA": "😕", "OTRO": "💬"}

st.title("🐾 El Adoptador")
st.caption("El asistente de adopción de mascotas — clasifica, busca la mascota real y contesta con calidez.")

with st.sidebar:
    st.subheader("Ejemplos rápidos")
    ejemplos = [
        "Hola! Quiero adoptar a Rocky, ¿cómo le hago? 🙏",
        "¿Qué temperamento tiene Bruno? ¿Se lleva bien con niños?",
        "¿Cuál es la cuota de adopción de Mia?",
        "¿Tienen alguna mascota que necesite adopción urgente?",
        "Llevo dos semanas esperando respuesta sobre mi solicitud 😤",
    ]
    for ej in ejemplos:
        if st.button(ej, use_container_width=True):
            st.session_state["mensaje_prefijado"] = ej

    st.divider()
    st.subheader("🐾 Catálogo completo")
    from asistente import catalogo
    for _, mascota in catalogo.iterrows():
        with st.container(border=True):
            st.image(mascota["foto_url"], use_container_width=True)
            st.markdown(f"**{mascota['nombre']}** · {mascota['especie']}, {mascota['edad']}")
            if str(mascota["urgente"]).strip():
                st.caption("🔴 Adopción prioritaria")

if "historial" not in st.session_state:
    st.session_state.historial = []

# Mostrar el historial de la conversación
for msg in st.session_state.historial:
    with st.chat_message(msg["rol"]):
        st.markdown(msg["contenido"])
        if msg.get("fotos"):
            cols = st.columns(len(msg["fotos"]))
            for col, foto in zip(cols, msg["fotos"]):
                with col:
                    st.image(foto["foto_url"], caption=foto["nombre"], use_container_width=True)
        if msg.get("clase"):
            st.caption(f"{EMOJI.get(msg['clase'], '')} Clasificado como: {msg['clase']}")

# Si el usuario picó un ejemplo en la barra lateral, lo usamos como input
mensaje_prefijado = st.session_state.pop("mensaje_prefijado", None)
mensaje = st.chat_input("Escribe tu mensaje...") or mensaje_prefijado

if mensaje:
    st.session_state.historial.append({"rol": "user", "contenido": mensaje})
    with st.chat_message("user"):
        st.markdown(mensaje)

    with st.chat_message("assistant"):
        with st.spinner("Pensando…"):
            resultado = atender(mensaje)

        if resultado["a_humano"]:
            respuesta_mostrada = "🙋 Esto se lo paso a un humano del refugio — alguien del equipo te contesta en un momento. 🤎"
            with st.expander("¿Por qué se pasó a un humano?", expanded=False):
                st.write(f"Se clasificó como **{resultado['clase']}**, y esas categorías siempre las atiende una persona del equipo, no el asistente automático.")
        else:
            respuesta_mostrada = resultado["respuesta"]
            with st.expander("🔎 Detrás del mostrador (el dato que consultó)", expanded=False):
                st.text(resultado["contexto"])

        st.markdown(respuesta_mostrada)

        fotos = resultado.get("fotos", [])
        if fotos:
            cols = st.columns(len(fotos))
            for col, foto in zip(cols, fotos):
                with col:
                    st.image(foto["foto_url"], caption=foto["nombre"], use_container_width=True)

        st.caption(f"{EMOJI.get(resultado['clase'], '')} Clasificado como: {resultado['clase']}")

    st.session_state.historial.append({
        "rol": "assistant",
        "contenido": respuesta_mostrada,
        "clase": resultado["clase"],
        "fotos": resultado.get("fotos", []),
    })
