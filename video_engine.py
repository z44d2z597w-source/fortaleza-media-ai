import json
import random
import re
import requests
import urllib.parse
import os
from pathlib import Path

ARCHIVO_GUION = Path("guion.json")
ARCHIVO_HISTORIAL = Path("historial_creativo.json")

GENEROS = ["Terror psicológico", "Misterio histórico", "Ciencia ficción distópica", "Drama familiar", "Leyenda urbana", "Conspiración tecnológica", "Suspenso policial", "Fantasía oscura"]
GIROS = ["Un giro argumental que lo cambia todo", "Un final que conecta con el inicio", "Una revelación escalofriante", "Un secreto oculto en el objeto", "Una traición inesperada"]
VOCES = ["es-MX-DaliaNeural", "es-MX-JorgeNeural"]

def cargar_historial():
    if ARCHIVO_HISTORIAL.exists():
        try:
            with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return []
    return []

def guardar_historial(titulo):
    historial = cargar_historial()
    historial.append(titulo)
    historial = historial[-20:]
    with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=4)

def generar_con_groq(prompt):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key: return None

    headers = {"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": "Eres un director de cine de élite. Planificas videos verticales para TikTok y YouTube Shorts."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.9,
        "response_format": {"type": "json_object"}
    }
    
    try:
        respuesta = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60)
        respuesta.raise_for_status()
        return json.loads(respuesta.json()["choices"][0]["message"]["content"])
    except Exception as e:
        print(f"[GROQ] Error: {e}")
        return None

def crear_plan_de_produccion():
    genero = random.choice(GENEROS)
    giro = random.choice(GIROS)
    voz = random.choice(VOCES)
    
    # --- LÓGICA DE DURACIÓN VARIABLE ---
    # 1 = Corto (TikTok rápido), 2 = Medio (Short estándar), 3 = Largo (Historia profunda)
    duracion_tipo = random.choice([1, 2, 3])
    
    if duracion_tipo == 1:
        duracion_objetivo = "15 a 25 segundos"
        beats_objetivo = "3 a 4"
    elif duracion_tipo == 2:
        duracion_objetivo = "40 a 60 segundos"
        beats_objetivo = "6 a 8"
    else:
        duracion_objetivo = "90 a 120 segundos"
        beats_objetivo = "12 a 16"

    historial = cargar_historial()
    temas_prohibidos = ", ".join(historial) if historial else "Ninguno"

    print(f"[DIRECTOR] Género: {genero} | Duración: {duracion_objetivo} | Voz: {voz}")

    prompt = f"""
    Actúa como un director de cine. Crea un plan de producción para un video vertical (9:16) del género '{genero}'.
    El video debe durar aproximadamente {duracion_objetivo}.
    
    REGLAS DE CREATIVIDAD:
    1. NO uses ninguno de estos temas anteriores: {temas_prohibidos}.
    2. DEBES incluir este giro argumental: {giro}.
    3. La historia debe ser 100% original y sorprendente.
    4. Genera entre {beats_objetivo} beats (momentos) para el storyboard.

    DEVUELVE EXCLUSIVAMENTE UN OBJETO JSON CON ESTA ESTRUCTURA:
    {{
        "titulo": "Título atractivo y único",
        "storyboard": [
            {{
                "id": 1,
                "duracion": 3,
                "narracion": "Texto exacto que dirá la voz en off.",
                "prompt_visual": "Prompt en inglés para la IA. Debe incluir la descripción del personaje y el escenario."
            }}
        ]
    }}
    """

    plan = generar_con_groq(prompt)
    
    if not plan or "storyboard" not in plan:
        print("[AVISO] Groq falló. Usando plan de respaldo.")
        # Plan de respaldo con duración media
        plan = {
            "titulo": f"El enigma de {genero.lower()} #{random.randint(100,999)}",
            "storyboard": [
                {"id": 1, "duracion": 5, "narracion": "Hay algo que no cuadra en esta estación.", "prompt_visual": "Cinematic 8k, vertical 9:16, a tired detective in a brown coat, abandoned train station, fog."},
                {"id": 2, "duracion": 5, "narracion": "Los relojes marcan la misma hora desde hace años.", "prompt_visual": "Cinematic 8k, vertical 9:16, close-up of a broken clock, dust particles."},
                {"id": 3, "duracion": 5, "narracion": "Pero hoy, uno de ellos se movió.", "prompt_visual": "Cinematic 8k, vertical 9:16, detective's hand touching a clock, dramatic lighting."},
                {"id": 4, "duracion": 5, "narracion": "Y el mensaje que dejó no era para él.", "prompt_visual": "Cinematic 8k, vertical 9:16, close-up of a mysterious note in hand."},
                {"id": 5, "duracion": 5, "narracion": "Alguien más está jugando con el tiempo.", "prompt_visual": "Cinematic 8k, vertical 9:16, detective looking at a shadowy figure in the fog."},
                {"id": 6, "duracion": 5, "narracion": "Y esta vez, el reloj corre en su contra.", "prompt_visual": "Cinematic 8k, vertical 9:16, detective running through the abandoned station."}
            ]
        }

    guardar_historial(plan["titulo"])

    return {
        "titulo": plan["titulo"],
        "formato": "vertical",
        "voz": voz,
        "director_notes": {
            "storyboard": plan["storyboard"]
        }
    }

def guardar_guion():
    guion = crear_plan_de_produccion()
    with open(ARCHIVO_GUION, "w", encoding="utf-8") as f:
        json.dump(guion, f, ensure_ascii=False, indent=4)
    print(f"PLAN DE PRODUCCIÓN GUARDADO: {guion['titulo']}")

if __name__ == "__main__":
    guardar_guion()