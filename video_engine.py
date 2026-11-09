import json
import random
import re
import requests
import urllib.parse
import os
from pathlib import Path

ARCHIVO_GUION = Path("guion.json")
ARCHIVO_HISTORIAL = Path("historial_creativo.json")

# --- COMBINADOR ALEATORIO (Para que NUNCA se repita si la IA falla) ---
PERSONAJES = ["un detective cansado", "una niña perdida", "un científico loco", "un anciano ciego", "una madre desesperada", "un hacker adolescente", "un policía corrupto", "un médico del turno nocturno"]
ESCENARIOS = ["una estación de tren abandonada", "un hospital psiquiátrico", "un bosque bajo la lluvia", "un edificio sin ascensor", "una casa inteligente", "un laboratorio subterráneo", "una biblioteca antigua", "un crucero en el medio del océano"]
OBJETOS = ["un reloj que va hacia atrás", "un espejo que muestra el futuro", "una carta escrita con sangre", "un teléfono que solo recibe llamadas", "una llave que no abre nada", "un diario con páginas en blanco", "una muñeca rota", "una grabación de voz"]

GENEROS = ["Terror psicológico", "Misterio histórico", "Ciencia ficción distópica", "Drama familiar", "Leyenda urbana"]
VOCES = ["es-MX-DaliaNeural", "es-MX-JorgeNeural"]

def cargar_historial():
    if ARCHIVO_HISTORIAL.exists():
        try:
            with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def guardar_historial(titulo):
    historial = cargar_historial()
    historial.append(titulo)
    with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(historial[-30:], f, ensure_ascii=False, indent=4)

def generar_con_groq(prompt):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key: return None
    headers = {"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"}
    for modelo in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
        payload = {"model": modelo, "messages": [{"role": "system", "content": "Eres un director de cine de élite. Creas guiones estructurados."}, {"role": "user", "content": prompt}], "temperature": 0.8, "response_format": {"type": "json_object"}}
        try:
            resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60)
            if resp.status_code == 200: return json.loads(resp.json()["choices"][0]["message"]["content"])
        except: pass
    return None

def generar_con_pollinations(prompt):
    try:
        url = f"https://text.pollinations.ai/{urllib.parse.quote(prompt)}?model=openai&json=true"
        resp = requests.get(url, timeout=90)
        if resp.status_code == 200: return json.loads(resp.text)
    except: pass
    return None

def crear_plan_de_produccion():
    genero = random.choice(GENEROS)
    voz = random.choice(VOCES)
    historial = cargar_historial()
    temas_prohibidos = ", ".join(historial) if historial else "Ninguno"

    # Prompt Maestro para que genere Video Largo + 3 Shorts
    prompt = f"""
    Actúa como un director de cine. Crea una historia del género '{genero}'.
    NO USES estos temas anteriores: {temas_prohibidos}.
    
    DEVUELVE EXCLUSIVAMENTE UN JSON CON ESTA ESTRUCTURA:
    {{
        "titulo": "Título impactante",
        "guion_largo": "Historia completa de 3000 palabras dividida en 5 capítulos.",
        "shorts": [
            {{
                "parte": 1,
                "gancho": "Texto de 40 segundos que enganche y diga 'Parte 1'."
            }},
            {{
                "parte": 2,
                "gancho": "Texto de 40 segundos que enganche y diga 'Parte 2'."
            }},
            {{
                "parte": 3,
                "gancho": "Texto de 40 segundos que diga 'Parte 3' y llame a ver el video completo."
            }}
        ]
    }}
    """

    plan = generar_con_groq(prompt) or generar_con_pollinations(prompt)

    # --- PLAN DE RESPALDO ANTI-REPETICIÓN ---
    if not plan or "shorts" not in plan:
        print("[AVISO] IAs fallaron. Generando historia única con Combinador Aleatorio.")
        p = random.choice(PERSONAJES)
        e = random.choice(ESCENARIOS)
        o = random.choice(OBJETOS)
        
        titulo = f"El secreto de {o} en {e}"
        plan = {
            "titulo": titulo,
            "guion_largo": f"{p.capitalize()} entró a {e} y encontró {o}. A partir de ese momento, nada volvió a ser igual. La historia completa te dejará sin aliento.",
            "shorts": [
                {"parte": 1, "gancho": f"Parte 1: {p.capitalize()} estaba en {e}. Encontró {o}. Pero había un problema..."},
                {"parte": 2, "gancho": f"Parte 2: Lo que {p} descubrió sobre {o} cambió las reglas. Nada era lo que parecía."},
                {"parte": 3, "gancho": f"Parte 3: El final de esta historia te dejará helado. Mira el video completo en mi canal."}
            ]
        }

    guardar_historial(plan["titulo"])

    return {
        "titulo": plan["titulo"],
        "voz": voz,
        "guion_largo": [{"narracion": plan["guion_largo"]}], # Lo dividimos internamente en render_long
        "shorts": plan["shorts"]
    }

def guardar_guion():
    guion = crear_plan_de_produccion()
    with open(ARCHIVO_GUION, "w", encoding="utf-8") as f:
        json.dump(guion, f, ensure_ascii=False, indent=4)
    print(f"GUION INFINITO GUARDADO: {guion['titulo']}")

if __name__ == "__main__":
    guardar_guion()