import json
import random
import re
import requests
import urllib.parse
import os
from pathlib import Path

ARCHIVO_SERIE = Path("guion_serie.json")
ARCHIVO_ESTADO = Path("estado_serie.json")
ARCHIVO_HISTORIAL = Path("historial_creativo.json")

PERSONAJES = ["un detective cansado", "una niña perdida", "un científico loco", "un anciano ciego", "una madre desesperada"]
ESCENARIOS = ["una estación de tren abandonada", "un hospital psiquiátrico", "un bosque bajo la lluvia", "un edificio sin ascensor"]
OBJETOS = ["un reloj que va hacia atrás", "un espejo que muestra el futuro", "una carta escrita con sangre", "una llave que no abre nada"]

# --- FUNCIÓN DE VALIDACIÓN (Evita que el sistema colapse si la IA devuelve texto en vez de JSON) ---
def validar_serie(serie):
    if not serie or not isinstance(serie, dict): return False
    if "titulo_serie" not in serie or "episodios" not in serie: return False
    if not isinstance(serie["episodios"], list) or len(serie["episodios"]) < 5: return False
    for ep in serie["episodios"]:
        if not isinstance(ep, dict): return False
        if not all(k in ep for k in ["parte", "titulo_episodio", "narracion", "prompt_visual"]): return False
    return True

def cargar_estado():
    if ARCHIVO_ESTADO.exists():
        try:
            with open(ARCHIVO_ESTADO, "r") as f: return json.load(f)
        except: pass
    return {"serie_actual": None, "parte_actual": 1, "total_partes": 5}

def guardar_estado(estado):
    with open(ARCHIVO_ESTADO, "w") as f: json.dump(estado, f, indent=4)

def cargar_historial():
    if ARCHIVO_HISTORIAL.exists():
        try:
            with open(ARCHIVO_HISTORIAL, "r") as f: return json.load(f)
        except: return []
    return []

def guardar_historial(titulo):
    hist = cargar_historial()
    hist.append(titulo)
    with open(ARCHIVO_HISTORIAL, "w") as f: json.dump(hist[-30:], f, indent=4)

def generar_con_groq(prompt):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key: return None
    headers = {"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"}
    payload = {"model": "openai/gpt-oss-120b", "messages": [{"role": "system", "content": "Eres un guionista experto en mini-series."}, {"role": "user", "content": prompt}], "temperature": 0.8, "response_format": {"type": "json_object"}}
    try:
        resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60)
        if resp.status_code == 200: return json.loads(resp.json()["choices"][0]["message"]["content"])
    except: pass
    return None

def generar_con_pollinations(prompt):
    try:
        url = "https://gen.pollinations.ai/v1/chat/completions"
        payload = {
            "model": "openai",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"}
        }
        resp = requests.post(url, json=payload, timeout=90)
        if resp.status_code == 200:
            return json.loads(resp.json()["choices"][0]["message"]["content"])
    except: pass
    return None

def crear_nueva_serie():
    historial = cargar_historial()
    temas_prohibidos = ", ".join(historial) if historial else "Ninguno"
    
    prompt = f"""
    Crea una MINI-SERIE de misterio de 5 episodios.
    NO USES estos temas anteriores: {temas_prohibidos}.
    Cada episodio debe durar 1 minuto (aprox 150 palabras). Cada episodio debe terminar en un CLIFFHANGER.
    
    DEVUELVE EXCLUSIVAMENTE UN JSON CON ESTA ESTRUCTURA:
    {{
        "titulo_serie": "Título impactante",
        "episodios": [
            {{"parte": 1, "titulo_episodio": "El inicio", "narracion": "Texto de 1 minuto.", "prompt_visual": "Prompt en inglés para la imagen de fondo del episodio 1."}},
            {{"parte": 2, "titulo_episodio": "...", "narracion": "...", "prompt_visual": "Prompt diferente..."}},
            {{"parte": 3, "titulo_episodio": "...", "narracion": "...", "prompt_visual": "Prompt diferente..."}},
            {{"parte": 4, "titulo_episodio": "...", "narracion": "...", "prompt_visual": "Prompt diferente..."}},
            {{"parte": 5, "titulo_episodio": "...", "narracion": "...", "prompt_visual": "Prompt diferente..."}}
        ]
    }}
    """
    
    plan = generar_con_groq(prompt) or generar_con_pollinations(prompt)
    
    if not validar_serie(plan):
        print("[AVISO] IA falló o generó un formato inválido. Creando serie de respaldo única.")
        p = random.choice(PERSONAJES)
        e = random.choice(ESCENARIOS)
        o = random.choice(OBJETOS)
        plan = {
            "titulo_serie": f"El enigma de {o} en {e}",
            "episodios": [
                {"parte": 1, "titulo_episodio": "El descubrimiento", "narracion": f"{p.capitalize()} llegó a {e} y encontró {o}. Un ruido extraño lo hizo girar.", "prompt_visual": f"Cinematic, vertical, {p} in {e} holding {o}"},
                {"parte": 2, "titulo_episodio": "La primera pista", "narracion": f"Al inspeccionar {o}, {p} notó algo imposible. Una inscripción que no debía estar ahí.", "prompt_visual": f"Cinematic, vertical, close up of {o}"},
                {"parte": 3, "titulo_episodio": "El acecho", "narracion": f"De repente, las luces se apagaron. Alguien más estaba en {e}.", "prompt_visual": f"Cinematic, vertical, {p} looking scared in the dark"},
                {"parte": 4, "titulo_episodio": "La revelación", "narracion": f"{p.capitalize()} descubrió la verdad sobre {o}. Todo era una trampa.", "prompt_visual": f"Cinematic, vertical, mysterious figure revealing the truth"},
                {"parte": 5, "titulo_episodio": "El final", "narracion": f"La huida final. {p.capitalize()} logró escapar, pero algo lo perseguirá.", "prompt_visual": f"Cinematic, vertical, {p} running away at night"}
            ]
        }

    guardar_historial(plan["titulo_serie"])
    return plan

def obtener_guion_hoy():
    estado = cargar_estado()
    crear_nueva = False
    
    # Comprobar si hay que crear una nueva serie o si la existente está dañada
    if estado["serie_actual"] is None or estado["parte_actual"] > estado["total_partes"]:
        crear_nueva = True
    elif not ARCHIVO_SERIE.exists():
        crear_nueva = True
    else:
        try:
            with open(ARCHIVO_SERIE, "r", encoding="utf-8") as f:
                serie_actual = json.load(f)
            if not validar_serie(serie_actual):
                print("[SISTEMA] La serie guardada está corrupta o incompleta. Generando una nueva...")
                crear_nueva = True
        except:
            print("[SISTEMA] No se pudo leer la serie guardada. Generando una nueva...")
            crear_nueva = True

    if crear_nueva:
        print("[SISTEMA] Iniciando nueva mini-serie de 5 partes...")
        nueva_serie = crear_nueva_serie()
        with open(ARCHIVO_SERIE, "w", encoding="utf-8") as f: json.dump(nueva_serie, f, ensure_ascii=False, indent=4)
        estado = {"serie_actual": nueva_serie["titulo_serie"], "parte_actual": 1, "total_partes": 5}
        guardar_estado(estado)
        
    with open(ARCHIVO_SERIE, "r", encoding="utf-8") as f: serie = json.load(f)
    
    parte = estado["parte_actual"]
    print(f"[SISTEMA] Generando Parte {parte} de 5: {serie['titulo_serie']}")
    
    episodio_hoy = serie["episodios"][parte - 1]
    
    guion_hoy = {
        "titulo_serie": serie["titulo_serie"],
        "parte": parte,
        "titulo_episodio": episodio_hoy["titulo_episodio"],
        "narracion": episodio_hoy["narracion"],
        "prompt_visual": episodio_hoy["prompt_visual"],
        "voz": "es-MX-DaliaNeural"
    }
    
    with open("guion.json", "w", encoding="utf-8") as f: json.dump(guion_hoy, f, ensure_ascii=False, indent=4)
    
    estado["parte_actual"] += 1
    guardar_estado(estado)
    
    return guion_hoy