# -*- coding: utf-8 -*-
"""
asistente.py — El Adoptador
Lógica completa (catálogo, RAG, clasificador con LoRA, prompt y pipeline)
sin ninguna dependencia de Google Colab. Pensado para correr en tu compu
o en un servidor, y ser importado desde app.py (Streamlit).
"""

import os
import re
import time

import pandas as pd
import torch
from datasets import Dataset
from sentence_transformers import SentenceTransformer, util
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    logging,
)
from huggingface_hub import InferenceClient

logging.set_verbosity_error()

# ──────────────────────────────────────────────────────────────────────────
# Paso 2 · Cliente de Hugging Face (redacción)
# ──────────────────────────────────────────────────────────────────────────
# En Colab usabas: from google.colab import userdata; userdata.get("HF_TOKEN")
# Aquí lo leemos de una variable de entorno normal.
HF_TOKEN = os.environ.get("HF_TOKEN")
if not HF_TOKEN:
    raise RuntimeError(
        "No encontré la variable de entorno HF_TOKEN. "
        "Expórtala antes de correr la app, por ejemplo:\n"
        "  export HF_TOKEN='tu_token_aqui'   (Mac/Linux)\n"
        "  set HF_TOKEN=tu_token_aqui        (Windows CMD)"
    )

hf_client = InferenceClient(token=HF_TOKEN)
HF_MODEL = "meta-llama/Llama-3.1-8B-Instruct"


def preguntar_a_hf(prompt, temperatura=0.4):
    """Manda un prompt a Hugging Face y regresa el texto. Si el modelo está
    'dormido' o te frena, espera y reintenta una vez."""
    for intento in (1, 2):
        try:
            r = hf_client.chat.completions.create(
                model=HF_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperatura,
            )
            return r.choices[0].message.content.strip()
        except Exception as e:
            if intento == 1:
                print("⏳ Hugging Face se tardó o te frenó; espero 5 seg y reintento…")
                time.sleep(5)
            else:
                return f"(No pude contestar: {type(e).__name__}. Revisa tu llave o espera un minuto.)"


# ──────────────────────────────────────────────────────────────────────────
# Paso 3 · Catálogo de mascotas (ahora desde SQLite, con foto por mascota)
# ──────────────────────────────────────────────────────────────────────────
import sqlite3

RUTA_DB = os.environ.get("RUTA_BASE_DATOS", "refugio.db")

if not os.path.exists(RUTA_DB):
    raise RuntimeError(
        f"No encontré la base de datos '{RUTA_DB}'. "
        "Corre primero:  python crear_base_datos.py"
    )

_conexion = sqlite3.connect(RUTA_DB)
catalogo = pd.read_sql("SELECT * FROM mascotas", _conexion)
_conexion.close()

print(f"Catálogo cargado desde '{RUTA_DB}' ✅ · {len(catalogo)} mascotas")


def foto_de(nombre_mascota):
    """Regresa la foto_url de una mascota por su nombre, o None si no existe."""
    fila = catalogo[catalogo["nombre"].str.lower() == nombre_mascota.lower()]
    if fila.empty:
        return None
    return fila.iloc[0]["foto_url"]


# ──────────────────────────────────────────────────────────────────────────
# Paso 4 · RAG — hacer el catálogo buscable
# ──────────────────────────────────────────────────────────────────────────
def fila_a_texto(row):
    texto = (f"Mascota: {row['nombre']} ({row['especie']}, raza {row['raza']}). "
             f"Edad: {row['edad']}. Tamaño: {row['tamano']}. Sexo: {row['sexo']}. "
             f"Esterilizado: {row['esterilizado']}. Vacunado: {row['vacunado']}. "
             f"Temperamento: {row['temperamento']}. Descripción: {row['descripcion']}. "
             f"Requisitos de adopción: {row['requisitos']}. "
             f"Cuota de adopción: {row['cuota_adopcion']}. Refugio: {row['refugio']}.")

    urgente = row.get('urgente', '')
    if urgente and str(urgente).strip():
        texto += f" ADOPCIÓN PRIORITARIA: {urgente}."

    return texto


mascotas_texto = [fila_a_texto(r) for _, r in catalogo.iterrows()]

print("Cargando modelo de embeddings (RAG)…")
buscador = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
emb_mascotas = buscador.encode(mascotas_texto, convert_to_tensor=True, show_progress_bar=False)


def buscar(pregunta, k=3):
    """Regresa las k mascotas del catálogo más parecidas a la pregunta,
    dando prioridad extra si el NOMBRE o la ESPECIE comparten palabras con la pregunta."""
    emb_q = buscador.encode(pregunta, convert_to_tensor=True)
    hits = util.semantic_search(emb_q, emb_mascotas, top_k=max(k * 3, 10))[0]

    palabras_pregunta = set(re.findall(r"\w+", pregunta.lower()))

    resultados = []
    for h in hits:
        idx = h["corpus_id"]
        clave = (catalogo.iloc[idx]["nombre"] + " " + catalogo.iloc[idx]["especie"]).lower()
        palabras_clave = set(re.findall(r"\w+", clave))
        coincidencias = len(palabras_pregunta & palabras_clave)
        score_final = h["score"] + coincidencias * 0.15
        resultados.append((score_final, mascotas_texto[idx]))

    resultados.sort(key=lambda x: x[0], reverse=True)
    return [texto for _, texto in resultados[:k]]


PALABRAS_URGENTE = ["urgente", "urgentes", "prioridad", "prioritaria", "prioritarias",
                     "necesitan hogar", "adopción urgente", "adopcion urgente"]


def es_pregunta_de_urgentes(mensaje):
    """Detecta si preguntan por mascotas de adopción urgente en general (no por una mascota puntual)."""
    m = mensaje.lower()
    return any(p in m for p in PALABRAS_URGENTE)


def listar_urgentes():
    """Regresa el texto de TODAS las mascotas marcadas como adopción prioritaria/urgente."""
    filas_urgentes = catalogo[catalogo["urgente"].astype(str).str.strip() != ""]
    return [fila_a_texto(r) for _, r in filas_urgentes.iterrows()]


print(len(mascotas_texto), "mascotas listas para buscar ✅")


# ──────────────────────────────────────────────────────────────────────────
# Paso 5 · Dataset de mensajes (4 clases)
# ──────────────────────────────────────────────────────────────────────────
CLASES = ['SOLICITUD', 'PREGUNTA', 'QUEJA', 'OTRO']
clase2id = {c: i for i, c in enumerate(CLASES)}
id2clase = {i: c for i, c in enumerate(CLASES)}

mensajes = [
    # ── SOLICITUD ──────────────────────────────────────────────────────
    ('Quiero adoptar a Rocky, ¿cómo le hago?', 'SOLICITUD'),
    ('Me interesa Mia, ¿puedo ir a conocerla este fin de semana?', 'SOLICITUD'),
    ('Ya decidí, quiero adoptar a Toby', 'SOLICITUD'),
    ('¿Me pueden agendar una visita para conocer a Coco?', 'SOLICITUD'),
    ('Quiero apartar a Luna antes de que alguien más la adopte', 'SOLICITUD'),
    ('Ya me decidí, ¿cómo aparto a Bruno antes de que alguien más lo adopte?', 'SOLICITUD'),
    ('Quiero llevarme a Simba a mi casa', 'SOLICITUD'),
    ('Me gustaría adoptar a Nube, ¿qué necesito?', 'SOLICITUD'),
    ('Ya elegí a Maple, quiero iniciar el proceso', 'SOLICITUD'),
 
    # ── PREGUNTA (con signo de interrogación) ─────────────────────────
    ('¿Qué temperamento tiene Bruno?', 'PREGUNTA'),
    ('¿Tienen gatos que se lleven bien con niños?', 'PREGUNTA'),
    ('¿Cuál es la cuota de adopción de Tango?', 'PREGUNTA'),
    ('¿Nube ya está esterilizada?', 'PREGUNTA'),
    ('¿Qué requisitos piden para adoptar un perro grande?', 'PREGUNTA'),
    ('¿Tienen alguna mascota que necesite adopción urgente?', 'PREGUNTA'),
    ('¿Cuánto cuesta adoptar a Bruno?', 'PREGUNTA'),
    ('¿Cuál es el costo de adoptar a Simba?', 'PREGUNTA'),
    ('¿Qué cuota tengo que pagar para adoptar a Luna?', 'PREGUNTA'),
    ('¿Cuántos años tiene Toby?', 'PREGUNTA'),
    ('¿Qué edad tiene Rocky?', 'PREGUNTA'),
    ('¿Cuántos años tiene Simba?', 'PREGUNTA'),
    ('¿Tienen perros pequeños para departamento?', 'PREGUNTA'),
    ('¿Tienen gatos jóvenes disponibles?', 'PREGUNTA'),
    ('¿Coco ya tiene todas sus vacunas?', 'PREGUNTA'),
    ('¿De qué tamaño es Bruno?', 'PREGUNTA'),
    ('¿Mia es macho o hembra?', 'PREGUNTA'),
    ('¿En qué refugio está Toby?', 'PREGUNTA'),
 
    # ── PREGUNTA (sin signo de interrogación / afirmaciones que piden info) ──
    ('Necesito un gato de poca edad', 'PREGUNTA'),
    ('Busco un perro tranquilo para departamento', 'PREGUNTA'),
    ('Quiero saber si tienen cachorros disponibles', 'PREGUNTA'),
    ('Me interesa saber cuánto cuesta adoptar a Maple', 'PREGUNTA'),
    ('Necesito información sobre los requisitos de adopción', 'PREGUNTA'),
    ('Busco una mascota pequeña que no necesite mucho espacio', 'PREGUNTA'),
    ('Quisiera saber si Luna convive bien con otros gatos', 'PREGUNTA'),
    ('Cuéntame más sobre Maple', 'PREGUNTA'),
    ('Platícame de Rocky', 'PREGUNTA'),
    ('Cuéntame sobre Simba', 'PREGUNTA'),
    ('Dame más información de Bruno', 'PREGUNTA'),
 
    # ── QUEJA ──────────────────────────────────────────────────────────
    ('Fui al refugio y nadie me atendió bien, muy mala organización', 'QUEJA'),
    ('Llevo dos semanas esperando respuesta sobre mi solicitud', 'QUEJA'),
    ('Me dijeron que Maple estaba disponible y ya no', 'QUEJA'),
    ('El proceso de adopción es confuso y nadie explica nada', 'QUEJA'),
    ('Adopté hace un mes y el seguimiento veterinario prometido nunca llegó', 'QUEJA'),
    ('Llevo dos semanas esperando respuesta sobre mi solicitud 😤', 'QUEJA'),
    ('Nadie me contestó en tres días, pésima atención', 'QUEJA'),
    ('Me prometieron una visita y la cancelaron sin avisar', 'QUEJA'),
    ('Muy mal servicio, no vuelvo a recomendar este refugio', 'QUEJA'),
    ('Estoy inconforme con cómo se manejó mi caso', 'QUEJA'),
    ('Fui a conocer a una mascota y me trataron muy mal, no pienso volver', 'QUEJA'),
 
    # ── OTRO ───────────────────────────────────────────────────────────
    ('Hola, buenas tardes 👋', 'OTRO'),
    ('¡Gracias por todo lo que hacen por los animalitos! 🐾', 'OTRO'),
    ('Qué bonitas las fotos que subieron hoy 📸', 'OTRO'),
    ('Solo estaba viendo, gracias', 'OTRO'),
    ('Feliz día del refugio a todo el equipo 🎉', 'OTRO'),
    ('Buenos días', 'OTRO'),
    ('Qué buen trabajo hacen', 'OTRO'),
]
 
# Mensajes de PRUEBA (held-out): NO están en el entrenamiento
PRUEBA = [
    ('Quiero adoptar a Bruno, ¿qué sigue?', 'SOLICITUD'),
    ('Me interesa Simba, ¿puedo pasar por él mañana?', 'SOLICITUD'),
    ('¿Cuánto cuesta adoptar a Coco?', 'PREGUNTA'),
    ('Busco un gato tranquilo para departamento chico', 'PREGUNTA'),
    ('Necesito un gato de pequeña edad', 'PREGUNTA'),
    ('¿Cuántos años tiene Maple?', 'PREGUNTA'),
    ('Llevo días esperando y nadie del refugio me responde', 'QUEJA'),
    ('Cancelaron mi cita sin ni siquiera avisarme', 'QUEJA'),
    ('¡Buenos días! 😊', 'OTRO'),
    ('Todo bien, solo estaba curioseando', 'OTRO'),
]

train_ds = Dataset.from_dict({
    "text":   [t for t, c in mensajes],
    "labels": [clase2id[c] for t, c in mensajes],
})


# ──────────────────────────────────────────────────────────────────────────
# Paso 6-7-8 · Clasificador (DistilBERT + LoRA)
# ──────────────────────────────────────────────────────────────────────────
# Carpeta donde se guarda/carga el modelo ya afinado, para NO reentrenar
# cada vez que arranca la app.
RUTA_MODELO = os.environ.get("RUTA_MODELO_CLASIFICADOR", "modelo_final")

print("Cargando tokenizer y modelo base…")
nombre_base = "distilbert-base-multilingual-cased"
tokenizer = AutoTokenizer.from_pretrained(nombre_base)


def tok(b):
    return tokenizer(b["text"], truncation=True, padding="max_length", max_length=64)


train_tok = train_ds.map(tok, batched=True)


def clasificar(texto):
    inputs = tokenizer(texto, return_tensors="pt", truncation=True, max_length=64).to(modelo.device)
    modelo.eval()
    with torch.no_grad():
        logits = modelo(**inputs).logits
    return id2clase[int(logits.argmax(dim=-1))]


def aciertos():
    return round(100 * sum(clasificar(t) == c for t, c in PRUEBA) / len(PRUEBA))


if os.path.isdir(RUTA_MODELO):
    # Ya existe un modelo afinado guardado -> lo cargamos directo, sin reentrenar
    print(f"Cargando clasificador ya afinado desde '{RUTA_MODELO}' …")
    modelo = AutoModelForSequenceClassification.from_pretrained(
        RUTA_MODELO, num_labels=4, id2label=id2clase, label2id=clase2id
    )
    print("Clasificador cargado ✅  · Aciertos en PRUEBA:", aciertos(), "%")
else:
    # Primera vez -> entrenamos igual que en el notebook y lo guardamos
    print("No encontré un modelo afinado guardado. Entrenando desde cero (una sola vez)…")
    modelo = AutoModelForSequenceClassification.from_pretrained(
        nombre_base, num_labels=4, id2label=id2clase, label2id=clase2id
    )

    antes_acc = aciertos()
    print("Aciertos ANTES de LoRA:", antes_acc, "%")

    from peft import LoraConfig, get_peft_model

    config_lora = LoraConfig(
        task_type="SEQ_CLS", r=8, lora_alpha=16,
        target_modules=["q_lin", "v_lin"], lora_dropout=0.05,
        modules_to_save=["pre_classifier", "classifier"],
    )
    modelo = get_peft_model(modelo, config_lora)
    modelo.print_trainable_parameters()

    args = TrainingArguments(
        output_dir="./resultados_entrenamiento",
        num_train_epochs=40,
        per_device_train_batch_size=4,
        learning_rate=5e-4,
        logging_steps=10,
        report_to="none",
    )
    trainer = Trainer(model=modelo, args=args, train_dataset=train_tok)
    trainer.train()

    despues_acc = aciertos()
    print(f"🏁 De {antes_acc}% a {despues_acc}% de aciertos con solo afinar. ✅")

    # Guardamos para que la próxima vez que arranque la app NO se reentrene
    modelo.save_pretrained(RUTA_MODELO)
    tokenizer.save_pretrained(RUTA_MODELO)
    print(f"Modelo guardado en '{RUTA_MODELO}' ✅")


# ──────────────────────────────────────────────────────────────────────────
# Paso 9 · Voz de marca (prompt) + pipeline completo
# ──────────────────────────────────────────────────────────────────────────
SYSTEM_RESPUESTA = """Eres "El Adoptador", el asistente virtual de una red de refugios de adopción de mascotas. Tu trabajo es responderle a la persona interesada de forma clara, cálida y honesta, priorizando siempre el bienestar del animal por encima de "cerrar la adopción" rápido.

REGLA DE ORO — SOLO EL CONTEXTO:
- Responde ÚNICAMENTE con la información del CONTEXTO del catálogo que se te entrega abajo. Es tu única fuente de verdad.
- NUNCA inventes mascotas, requisitos, cuotas ni características que no aparezcan en el contexto.
- Si la persona pregunta algo que NO viene en el contexto, dilo con honestidad y ofrécete a checarlo con el equipo del refugio. Ejemplo: "Ese dato no lo tengo a la mano, pero con gusto lo confirmo con el refugio 😊".
- Si la persona hace una SOLICITUD de adopción, confírmala con el nombre EXACTO de la mascota y menciona los requisitos y la cuota de adopción tal como aparecen en el contexto — nunca omitas los requisitos para "no espantar" al adoptante.
- Si el CONTEXTO marca a la mascota como ADOPCIÓN PRIORITARIA/URGENTE, menciónalo con cuidado y honestidad (por qué necesita hogar con prioridad), sin presionar ni generar culpa en la persona.

VOZ DE MARCA (cómo hablas):
- Cálido y empático, como alguien que ama a los animales y quiere el mejor hogar para ellos — no como un vendedor.
- Breve: 1 a 3 frases. Nada de choro.
- 1 o 2 emojis por mensaje (🐾 ❤️ 😊), sin exagerar.
- Cierra SIEMPRE ofreciendo ayuda o invitando a conocer más mascotas ("¿Te comparto otra opción? 😊").

Usa exactamente los nombres, requisitos y cuotas que trae el CONTEXTO. No agregues información de fuera. Responde solo con el mensaje para la persona, sin explicar tu razonamiento.

CONTEXTO DEL CATÁLOGO:
{contexto}

MENSAJE DE LA PERSONA:
{mensaje}"""


def responder_asesor(mensaje, contexto):
    """Hugging Face redacta la respuesta usando SOLO el contexto del catálogo."""
    prompt = SYSTEM_RESPUESTA.replace("{contexto}", contexto).replace("{mensaje}", mensaje)
    return preguntar_a_hf(prompt, temperatura=0.4)


def extraer_fotos_del_contexto(contexto):
    """Busca 'Mascota: Nombre (' en el texto del contexto y regresa
    [{"nombre": ..., "foto_url": ...}, ...] para las mascotas mencionadas."""
    nombres = re.findall(r"Mascota: (\S+)", contexto)
    fotos = []
    vistos = set()
    for nombre in nombres:
        if nombre in vistos:
            continue
        vistos.add(nombre)
        url = foto_de(nombre)
        if url:
            fotos.append({"nombre": nombre, "foto_url": url})
    return fotos


def atender(mensaje):
    """Pipeline completo. Regresa un dict con todo lo que pasó."""
    clase = clasificar(mensaje)
    if clase in ("QUEJA", "OTRO"):
        return {"clase": clase, "a_humano": True, "respuesta": None, "contexto": None, "fotos": []}

    if es_pregunta_de_urgentes(mensaje):
        contexto = "\n\n".join(listar_urgentes())       # lista completa de mascotas prioritarias
    else:
        contexto = "\n\n".join(buscar(mensaje, k=3))     # RAG normal: top-3 mascotas

    respuesta = responder_asesor(mensaje, contexto)
    fotos = extraer_fotos_del_contexto(contexto)
    return {"clase": clase, "a_humano": False, "respuesta": respuesta, "contexto": contexto, "fotos": fotos}


if __name__ == "__main__":
    # Para probar el módulo solo (sin Streamlit): python asistente.py
    for m in ["Quiero adoptar a Rocky", "¿Cuánto cuesta adoptar a Coco?", "Pésimo servicio"]:
        r = atender(m)
        print("💬", m, "→", r["clase"], "·", r["respuesta"] if not r["a_humano"] else "🙋 a humano")
