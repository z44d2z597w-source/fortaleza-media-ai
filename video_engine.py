import json
import random
import re
import requests
import urllib.parse
import os
from pathlib import Path

# ==========================================================
# FORTALEZA MEDIA AI 34.0 — DIRECTOR DE ESCENA ANTI-REPETICIÓN
# ==========================================================

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
    historial = historial[-20:] # Solo guardamos los últimos 20 para no saturar el prompt
    with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=4)

def generar_con_groq(prompt):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key: return None

    headers = {"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": "Eres un director de cine de élite. Planificas videos verticales de YouTube Shorts con una coherencia visual impecable."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.9, # Más creatividad
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
    
    historial = cargar_historial()
    temas_prohibidos = ", ".join(historial) if historial else "Ninguno"

    print(f"[DIRECTOR] Género: {genero} | Giro: {giro} | Voz: {voz}")
    print(f"[DIRECTOR] Temas prohibidos (ya usados): {temas_prohibidos}")

    prompt = f"""
    Actúa como un director de cine. Crea un plan de producción para un video vertical (9:16) del género '{genero}'.
    El video debe durar entre 45 y 60 segundos.
    
    REGLAS DE CREATIVIDAD:
    1. NO uses ninguno de estos temas anteriores: {temas_prohibidos}.
    2. DEBES incluir este giro argumental: {giro}.
    3. La historia debe ser 100% original y sorprendente.

    DEVUELVE EXCLUSIVAMENTE UN OBJETO JSON CON ESTA ESTRUCTURA:
    {{
        "titulo": "Título atractivo y único",
        "personajes": "Descripción física detallada y fija del personaje principal.",
        "escenario": "Descripción del lugar y la iluminación.",
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
        print("[AVISO] Groq falló o repitió tema. Usando plan de respaldo único.")
        # Plan de respaldo con giro aleatorio para no repetir
        plan = {
            "titulo": f"El enigma de {genero.lower()} #{random.randint(100,999)}",
            "personajes": "un detective cansado, abrigo marrón, sombrero de fieltro",
            "escenario": "una estación de tren abandonada, niebla densa, luces tenues",
            "storyboard": [
                {"id": 1, "duracion": 5, "narracion": "Hay algo que no cuadra en esta estación.", "prompt_visual": "Cinematic 8k, vertical 9:16, a tired detective in a brown coat and fedora, standing in an abandoned train station, thick fog, dim lights, slow pan."},
                {"id": 2, "duracion": 5, "narracion": "Los relojes marcan la misma hora desde hace años.", "prompt_visual": "Cinematic 8k, vertical 9:16, close-up of the detective's face, looking at a broken clock, fog in the background."},
                {"id": 3, "duracion": 5, "narracion": "Pero hoy, uno de ellos se movió.", "prompt_visual": "Cinematic 8k, vertical 9:16, the detective's hand touching a clock, dust particles in the air, dramatic lighting."},
                {"id": 4, "duracion": 5, "narracion": "Y el mensaje que dejó no era para él.", "prompt_visual": "Cinematic 8k, vertical 9:16, close-up of a mysterious note in the detective's hand, blurry background."}
            ]
        }

    # Guardamos el título para que no se repita en el futuro
    guardar_historial(plan["titulo"])

    return {
        "titulo": plan["titulo"],
        "formato": "vertical",
        "voz": voz,
        "director_notes": {
            "personajes": plan["personajes"],
            "escenario": plan["escenario"],
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