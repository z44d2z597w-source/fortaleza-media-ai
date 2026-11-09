import json
import random
import re
import requests
import urllib.parse
import os
from pathlib import Path

ARCHIVO_GUION = Path("guion.json")
GENEROS = ["Terror psicológico", "Misterio histórico", "Ciencia ficción distópica", "Drama familiar", "Leyenda urbana", "Conspiración tecnológica"]
VOCES = ["es-MX-DaliaNeural", "es-MX-JorgeNeural"]

# Lista de modelos en orden de preferencia (por si uno falla)
MODELOS_GROQ = [
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "llama3-70b-8192",
    "mixtral-8x7b-32768",
    "llama-3.1-8b-instant"
]

def generar_con_groq(prompt):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key: 
        print("[GROQ] No hay clave configurada.")
        return None
    
    headers = {"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"}
    
    for modelo in MODELOS_GROQ:
        payload = {
            "model": modelo,
            "messages": [
                {"role": "system", "content": "Eres un director de cine de élite. Creas storyboards con coherencia visual absoluta."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.8,
            "response_format": {"type": "json_object"}
        }
        
        try:
            print(f"[GROQ] Intentando con modelo: {modelo}")
            respuesta = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60)
            if respuesta.status_code == 200:
                print(f"[GROQ] ¡Éxito con {modelo}!")
                return json.loads(respuesta.json()["choices"][0]["message"]["content"])
            else:
                print(f"[GROQ] {modelo} falló con status {respuesta.status_code}")
        except Exception as e:
            print(f"[GROQ] Error con {modelo}: {e}")
            continue
    
    print("[GROQ] Todos los modelos fallaron.")
    return None

def crear_plan_de_produccion():
    genero = random.choice(GENEROS)
    voz = random.choice(VOCES)
    print(f"[DIRECTOR] Creando obra maestra: {genero} | Voz: {voz}")

    prompt = f"""
    Actúa como un director de cine. Crea un plan de producción para un video vertical (9:16) del género '{genero}'.
    
    REGLAS DE COHERENCIA ESTRICTA:
    1. Define un PERSONAJE PRINCIPAL con características físicas inmutables.
    2. Define un ESCENARIO PRINCIPAL inmutable.
    3. Genera un STORYBOARD de 6 a 8 beats. Cada 'prompt_visual' DEBE repetir EXACTAMENTE la descripción del personaje y el escenario.
    4. El primer beat DEBE ser un gancho visual que detenga el scroll (Hook de 1-2 segundos).

    DEVUELVE EXCLUSIVAMENTE UN OBJETO JSON CON ESTA ESTRUCTURA:
    {{
        "titulo": "Título atractivo y único",
        "personaje": "Descripción física detallada y fija.",
        "escenario": "Descripción del lugar y la iluminación.",
        "gancho_corto": "Texto de 100-150 palabras para TikTok/Shorts. Debe ser intrigante.",
        "storyboard": [
            {{
                "id": 1,
                "duracion": 4,
                "narracion": "Texto exacto de la voz en off.",
                "prompt_visual": "Prompt en inglés. DEBE incluir la descripción del personaje y el escenario."
            }}
        ]
    }}
    """

    plan = generar_con_groq(prompt)
    
    if not plan or "storyboard" not in plan:
        print("[AVISO] Groq falló. Usando plan de respaldo coherente.")
        plan = {
            "titulo": "El Enigma de la Estación Abandonada",
            "personaje": "un detective cansado, abrigo marrón, sombrero de fieltro",
            "escenario": "una estación de tren abandonada, niebla densa, luces tenues",
            "gancho_corto": "Los relojes de esta estación no han funcionado en 40 años. Pero hoy, uno de ellos se movió. El detective a cargo descubrió que no era una coincidencia, sino una trampa. ¿Quién está jugando con el tiempo? Descubre la verdad completa en el video largo.",
            "storyboard": [
                {"id": 1, "duracion": 4, "narracion": "Los relojes de esta estación no han funcionado en 40 años.", "prompt_visual": "Cinematic 8k, vertical 9:16, a tired detective in a brown coat and fedora, standing in an abandoned train station, thick fog, broken clocks, slow pan."},
                {"id": 2, "duracion": 4, "narracion": "Pero hoy, uno de ellos se movió.", "prompt_visual": "Cinematic 8k, vertical 9:16, close-up of the detective's face, looking at a clock that is ticking, dust in the air."},
                {"id": 3, "duracion": 4, "narracion": "Y el mensaje que dejó no era para él.", "prompt_visual": "Cinematic 8k, vertical 9:16, the detective's hand holding a mysterious note, blurry background of the station."},
                {"id": 4, "duracion": 4, "narracion": "Alguien más está jugando con el tiempo.", "prompt_visual": "Cinematic 8k, vertical 9:16, the detective looking at a shadowy figure disappearing into the fog."},
                {"id": 5, "duracion": 4, "narracion": "Y esta vez, el reloj corre en su contra.", "prompt_visual": "Cinematic 8k, vertical 9:16, the detective running through the abandoned station, clock hands spinning rapidly."},
                {"id": 6, "duracion": 4, "narracion": "¿Quién está jugando con el tiempo?", "prompt_visual": "Cinematic 8k, vertical 9:16, the detective looking directly at the camera, dramatic lighting."}
            ]
        }

    # Guardar historial
    historial_path = Path("historial_creativo.json")
    historial = []
    if historial_path.exists():
        try:
            with open(historial_path, "r") as f: historial = json.load(f)
        except: pass
    historial.append(plan["titulo"])
    with open(historial_path, "w") as f: json.dump(historial[-20:], f, indent=4)

    return {
        "titulo": plan["titulo"],
        "formato": "vertical",
        "voz": voz,
        "gancho_corto": plan["gancho_corto"],
        "director_notes": {
            "personaje": plan.get("personaje", "personaje principal"),
            "escenario": plan.get("escenario", "escenario principal"),
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