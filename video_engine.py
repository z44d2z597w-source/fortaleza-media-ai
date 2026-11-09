import json
import random
import re
import requests
import urllib.parse
from pathlib import Path

# ==========================================================
# FORTALEZA MEDIA AI 32.0 — DIRECTOR DE ESCENA
# ==========================================================

ARCHIVO_GUION = Path("guion.json")
GENEROS = ["Terror psicológico", "Misterio histórico", "Ciencia ficción distópica", "Drama familiar", "Leyenda urbana", "Conspiración tecnológica"]
VOCES = ["es-MX-DaliaNeural", "es-MX-JorgeNeural"]

def generar_con_groq(prompt):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("[GROQ] No hay clave configurada.")
        return None

    headers = {"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile", # Modelo más potente para planificación
        "messages": [
            {"role": "system", "content": "Eres un director de cine de élite. Planificas videos verticales de YouTube Shorts con una coherencia visual impecable."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.6, # Menos creatividad, más precisión
        "response_format": {"type": "json_object"} # Forzamos salida JSON
    }
    
    try:
        respuesta = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60)
        respuesta.raise_for_status()
        print("[GROQ] ¡Plan de producción generado!")
        return json.loads(respuesta.json()["choices"][0]["message"]["content"])
    except Exception as e:
        print(f"[GROQ] Error: {e}")
        return None

def crear_plan_de_produccion():
    genero = random.choice(GENEROS)
    voz = random.choice(VOCES)
    print(f"[DIRECTOR] Género: {genero} | Voz: {voz}")

    # El prompt es clave: pedimos personajes, escenario y storyboard.
    prompt = f"""
    Actúa como un director de cine. Crea un plan de producción para un video vertical (9:16) del género '{genero}'.
    El video debe durar entre 45 y 60 segundos.
    
    DEVUELVE EXCLUSIVAMENTE UN OBJETO JSON CON ESTA ESTRUCTURA:
    {{
        "titulo": "Título atractivo del video",
        "personajes": "Descripción física detallada y fija del personaje principal (ej: 'hombre de 40 años, gabardina gris, barba, ojos cansados').",
        "escenario": "Descripción del lugar y la iluminación (ej: 'habitación de hotel abandonada, luz tenue, polvo en el aire, tonos sepia').",
        "storyboard": [
            {{
                "id": 1,
                "duracion": 3,
                "narracion": "Texto exacto que dirá la voz en off.",
                "prompt_visual": "Prompt en inglés para la IA de video. Debe incluir la descripción del personaje y el escenario. Ej: 'Cinematic 8k, vertical 9:16, a man in a grey trench coat and beard, standing in a dusty abandoned hotel room, looking at a mirror, slow push-in shot.'"
            }},
            {{
                "id": 2,
                "duracion": 4,
                "narracion": "Siguiente frase de la narración.",
                "prompt_visual": "Siguiente prompt en inglés. Mantiene al mismo personaje y escenario. Ej: 'Cinematic 8k, vertical 9:16, close-up of the same man's face, reflection in the mirror, dramatic lighting, slow zoom.'"
            }}
        ]
    }}
    
    REGLAS ESTRICTAS:
    1. La narración debe ser dramática y en español mexicano.
    2. Cada 'prompt_visual' DEBE empezar con el estilo visual y la relación de aspecto ('Cinematic 8k, vertical 9:16,').
    3. Cada 'prompt_visual' DEBE repetir la descripción del personaje y del escenario para forzar la coherencia.
    4. La suma de las duraciones debe ser entre 45 y 60 segundos.
    5. El número de beats (storyboard) debe ser entre 8 y 12.
    6. El JSON debe ser válido y no contener texto adicional fuera de él.
    """

    plan = generar_con_groq(prompt)
    
    if not plan or "storyboard" not in plan:
        print("[AVISO] Groq falló. Usando plan de respaldo.")
        # Plan de respaldo si Groq falla
        plan = {
            "titulo": "El secreto de la habitación 404",
            "personajes": "un hombre joven, chaqueta de cuero negra, mirada nerviosa",
            "escenario": "un pasillo de hotel antiguo, luces parpadeantes, alfombra roja desgastada",
            "storyboard": [
                {"id": 1, "duracion": 5, "narracion": "Imagina entrar a un hotel y que la habitación 404 no exista.", "prompt_visual": "Cinematic 8k, vertical 9:16, a young man in a black leather jacket, nervous look, walking down an old hotel corridor, flickering lights, worn red carpet, slow tracking shot."},
                {"id": 2, "duracion": 5, "narracion": "El recepcionista le dio la llave sin mirarlo a los ojos.", "prompt_visual": "Cinematic 8k, vertical 9:16, close-up of the same young man's face, holding a key, dim lighting, tense atmosphere, shallow depth of field."},
                {"id": 3, "duracion": 5, "narracion": "Al abrir la puerta, solo había un espejo gigante.", "prompt_visual": "Cinematic 8k, vertical 9:16, the same man opening a door, revealing a room with only a giant mirror, dust particles in the air, dramatic reveal, slow zoom."},
                {"id": 4, "duracion": 5, "narracion": "Cuando tocó el espejo, su mano atravesó el vidrio.", "prompt_visual": "Cinematic 8k, vertical 9:16, close-up of the man's hand touching the mirror surface, ripples forming, surreal effect, suspenseful mood."},
                {"id": 5, "duracion": 5, "narracion": "Del otro lado, alguien igual a él lo esperaba con una sonrisa.", "prompt_visual": "Cinematic 8k, vertical 9:16, the same man looking into the mirror, his reflection smiling back at him, eerie lighting, slow push-in."},
                {"id": 6, "duracion": 5, "narracion": "Y por eso te pregunto: ¿qué harías si entraras a una habitación 404?", "prompt_visual": "Cinematic 8k, vertical 9:16, the young man in the black leather jacket, standing in the old hotel corridor, looking directly at the camera, dramatic lighting, freeze frame."}
            ]
        }

    return {
        "titulo": plan["titulo"],
        "formato": "vertical",
        "estilo_visual": "Cinematic 8k",
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