import json
import random
import re
import requests
import urllib.parse
import os
from pathlib import Path

# ==========================================================
# FORTALEZA MEDIA AI 35.0 — CEREBRO DUAL (LARGO + CORTO)
# ==========================================================

ARCHIVO_GUION = Path("guion.json")
GENEROS = ["Terror psicológico", "Misterio histórico", "Ciencia ficción distópica", "Drama familiar", "Leyenda urbana", "Conspiración tecnológica", "Suspenso policial", "Fantasía oscura"]
VOCES = ["es-MX-DaliaNeural", "es-MX-JorgeNeural"]

def generar_con_groq(prompt):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("[GROQ] No hay clave configurada.")
        return None

    headers = {"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": "Eres un guionista y director de cine de élite. Creas contenido altamente adictivo para YouTube y TikTok."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.8,
        "response_format": {"type": "json_object"}
    }
    
    try:
        respuesta = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=90)
        respuesta.raise_for_status()
        return json.loads(respuesta.json()["choices"][0]["message"]["content"])
    except Exception as e:
        print(f"[GROQ] Error: {e}")
        return None

def crear_guion_dual():
    genero = random.choice(GENEROS)
    voz = random.choice(VOCES)
    print(f"[DIRECTOR] Creando obra maestra del género: {genero} | Voz: {voz}")

    # El prompt exige un guion largo por capítulos y un gancho corto
    prompt = f"""
    Escribe una historia original, dramática y altamente adictiva del género '{genero}'.
    
    DEBES DEVOLVER UN OBJETO JSON CON EXACTAMENTE ESTA ESTRUCTURA:
    {{
        "titulo": "Título impactante y único",
        "gancho_corto": "Un texto de 100 a 150 palabras (para durar 40-60 segundos en TikTok). Debe ser lo más intrigante de la historia. Termina con una pregunta o llamado a la acción para que vean el video completo.",
        "guion_largo": [
            {{
                "capitulo": 1,
                "titulo_capitulo": "Nombre del capítulo",
                "narracion": "Texto largo de 800 a 1000 palabras para este capítulo."
            }},
            {{
                "capitulo": 2,
                "titulo_capitulo": "Nombre del capítulo 2",
                "narracion": "Texto largo de 800 a 1000 palabras..."
            }}
            // ... Genera 5 capítulos en total para alcanzar los 40-60 minutos de duración total.
        ]
    }}
    
    REGLAS ESTRICTAS:
    1. La historia debe ser un misterio o drama fascinante.
    2. NO repitas temas de otros videos.
    3. Escribe en español mexicano.
    4. Asegúrate de que el JSON sea válido.
    """

    plan = generar_con_groq(prompt)
    
    if not plan or "guion_largo" not in plan:
        print("[AVISO] Groq falló. Usando plan de respaldo.")
        plan = {
            "titulo": "El Enigma de la Estación Abandonada",
            "gancho_corto": "Hay algo que no cuadra en esta estación. Los relojes marcan la misma hora desde hace años. Pero hoy, uno de ellos se movió. Y el mensaje que dejó no era para él. Alguien más está jugando con el tiempo. ¿Te atreves a descubrir la verdad? Ve al video completo en mi canal.",
            "guion_largo": [
                {"capitulo": 1, "titulo_capitulo": "El Reloj Roto", "narracion": "Era una noche fría y lluviosa cuando el detective..."},
                {"capitulo": 2, "titulo_capitulo": "Las Sombras", "narracion": "Los susurros en el andén no venían de ninguna persona viva..."},
                {"capitulo": 3, "titulo_capitulo": "El Mensaje", "narracion": "El papel estaba firmado con su propio nombre, pero la letra no era suya..."},
                {"capitulo": 4, "titulo_capitulo": "El Túnel", "narracion": "Al fondo del túnel, una luz parpadeaba en código morse..."},
                {"capitulo": 5, "titulo_capitulo": "La Verdad", "narracion": "Todo era una simulación creada para atrapar a su mente..."}
            ]
        }

    return {
        "titulo": plan["titulo"],
        "formato": "vertical",
        "voz": voz,
        "gancho_corto": plan["gancho_corto"],
        "guion_largo": plan["guion_largo"]
    }

def guardar_guion():
    guion = crear_guion_dual()
    with open(ARCHIVO_GUION, "w", encoding="utf-8") as f:
        json.dump(guion, f, ensure_ascii=False, indent=4)
    print(f"PLAN DUAL GUARDADO: {guion['titulo']}")
    print(f"  -> Gancho Corto generado (para TikTok/Shorts).")
    print(f"  -> Guion Largo generado con {len(guion['guion_largo'])} capítulos.")

if __name__ == "__main__":
    guardar_guion()