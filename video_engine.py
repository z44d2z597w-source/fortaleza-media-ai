import json
import random
import re
import requests
import urllib.parse

from datetime import datetime, timedelta, timezone
from pathlib import Path

# ==========================================================
# FORTALEZA MEDIA AI 7.0
# MOTOR EDITORIAL: DOCUMENTALES + HISTORIAS DE DRAMA (REDDIT)
# ==========================================================

VERSION = "7.0"
IDIOMA = "es-MX"

ARCHIVO_GUION = Path("guion.json")
ARCHIVO_HISTORIAL = Path("historial_temas.json")

URL_PAGEVIEWS = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/es.wikipedia/all-access/user"
URL_WIKIPEDIA = "https://es.wikipedia.org/w/api.php"

CABECERAS = {"User-Agent": "FORTALEZA-MEDIA-AI/7.0"}
MAX_HISTORIAL = 300
MAX_CARACTERES_INVESTIGACION = 12000

TEMAS_RESPALDO = [
    "Fosa de las Marianas", "Bioluminiscencia", "Tiburón de Groenlandia",
    "Aurora polar", "Agujeros negros", "Volcanes submarinos", "Antártida",
    "Planeta Marte", "Cerebro humano", "Bosques tropicales", "Océanos",
    "Evolución humana", "Inteligencia artificial", "ADN", "Abejas",
    "Pirámides de Egipto", "Machu Picchu", "Imperio romano", "Antiguo Egipto",
    "Civilización maya", "Vikingos", "Titanic", "Pompeya", "Selva amazónica",
]

# ==========================================================
# HISTORIAL DE TEMAS
# ==========================================================

def cargar_historial():
    if not ARCHIVO_HISTORIAL.exists(): return []
    try:
        with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
            return datos if isinstance(datos, list) else []
    except Exception:
        return []

def guardar_historial(historial):
    historial = historial[-MAX_HISTORIAL:]
    temporal = ARCHIVO_HISTORIAL.with_suffix(".tmp")
    with open(temporal, "w", encoding="utf-8") as archivo:
        json.dump(historial, archivo, ensure_ascii=False, indent=4)
    temporal.replace(ARCHIVO_HISTORIAL)

def tema_ya_utilizado(titulo, historial):
    normalizado = titulo.strip().lower()
    for elemento in historial:
        anterior = str(elemento.get("titulo", "") if isinstance(elemento, dict) else elemento).strip().lower()
        if anterior == normalizado: return True
    return False

# ==========================================================
# INVESTIGACIÓN (DOCUMENTALES)
# ==========================================================

def limpiar_texto(texto):
    return re.sub(r"\s+", " ", re.sub(r"\[\d+\]", "", str(texto))).strip()

def investigar_tema(titulo):
    parametros = {"action": "query", "format": "json", "prop": "extracts", "titles": titulo, "explaintext": 1, "redirects": 1}
    try:
        respuesta = requests.get(URL_WIKIPEDIA, params=parametros, headers=CABECERAS, timeout=25)
        paginas = respuesta.json().get("query", {}).get("pages", {})
        for pagina in paginas.values():
            extracto = limpiar_texto(pagina.get("extract", ""))
            if len(extracto) < 600: return None
            return {"titulo": pagina.get("title", titulo), "texto": extracto[:MAX_CARACTERES_INVESTIGACION]}
    except Exception:
        return None

# ==========================================================
# GENERACIÓN DE DRAMA (REDDIT STYLE CON IA GRATIS)
# ==========================================================

def generar_historia_drama():
    print("[DRAMA] Generando historia de drama con IA...")
    
    # Prompts para forzar a la IA a escribir una historia de Reddit
    prompts = [
        "Escribe una historia corta de drama estilo Reddit (AITA) en español. Alguien tiene un conflicto familiar o de pareja. Gancho fuerte, desarrollo tenso y final impactante.",
        "Escribe una historia de misterio y suspenso en español. Una persona encuentra algo extraño en su casa. Tono dramático y enganchador.",
        "Escribe una historia de traición y venganza en español. Un compañero de trabajo o amigo hace algo terrible. Narración en primera persona, muy dramática."
    ]
    
    prompt = random.choice(prompts)
    prompt_encoded = urllib.parse.quote(prompt)
    
    # Pollinations text API (gratis, sin API key)
    url = f"https://text.pollinations.ai/{prompt_encoded}?model=openai"
    
    try:
        respuesta = requests.get(url, timeout=60)
        respuesta.raise_for_status()
        texto = respuesta.text.strip()
        
        # Limpiar el texto de posibles introducciones de la IA
        texto = re.sub(r"^(Aquí tienes|Claro|Por supuesto).*?:", "", texto, flags=re.IGNORECASE).strip()
        
        # Dividir en oraciones para estructurar las escenas
        oraciones = [o.strip() for o in re.split(r"(?<=[.!?])\s+", texto) if len(o.strip()) > 20]
        
        if len(oraciones) < 4:
            return None

        # Crear 4 escenas dramáticas
        tercio = len(oraciones) // 4
        escenas = [
            {"numero": 1, "duracion": 10, "tipo": "gancho", "titulo": "El problema", "narracion": " ".join(oraciones[:tercio])},
            {"numero": 2, "duracion": 15, "tipo": "desarrollo", "titulo": "Lo que pasó después", "narracion": " ".join(oraciones[tercio:tercio*2])},
            {"numero": 3, "duracion": 15, "tipo": "revelacion", "titulo": "La verdad sale a la luz", "narracion": " ".join(oraciones[tercio*2:tercio*3])},
            {"numero": 4, "duracion": 10, "tipo": "cierre", "titulo": "El desenlace", "narracion": " ".join(oraciones[tercio*3:]) + " ¿Tú qué harías en su lugar? Comenta."}
        ]
        
        # Generar título de la historia
        titulo_prompt = urllib.parse.quote(f"Genera un título corto y dramático en español para esta historia: {texto[:200]}. Devuelve solo el título.")
        titulo = requests.get(f"https://text.pollinations.ai/{titulo_prompt}?model=openai", timeout=30).text.strip()
        titulo = titulo.replace('"', '').replace('.', '')
        
        return {
            "titulo": titulo[:60],
            "formato": "vertical",
            "formato_legible": "YouTube Shorts (Drama)",
            "duracion": 50,
            "escenas": escenas
        }
    except Exception as e:
        print(f"[DRAMA] Error generando historia: {e}")
        return None

# ==========================================================
# CONSTRUCCIÓN DE GUIONES DOCUMENTALES
# ==========================================================

def seleccionar_tema():
    # Selección simplificada para documentales
    historial = cargar_historial()
    respaldo = [t for t in TEMAS_RESPALDO if not tema_ya_utilizado(t, historial)]
    random.shuffle(respaldo)
    for t in respaldo:
        inv = investigar_tema(t)
        if inv: return inv
    return investigar_tema("Misterio")

def crear_guion_documental(investigacion):
    oraciones = [o.strip() for o in re.split(r"(?<=[.!?])\s+", investigacion["texto"]) if len(o.strip()) > 35]
    tercio = len(oraciones) // 3
    escenas = [
        {"numero": 1, "duracion": 15, "tipo": "gancho", "titulo": investigacion["titulo"], "narracion": " ".join(oraciones[:tercio])},
        {"numero": 2, "duracion": 25, "tipo": "desarrollo", "titulo": "El contexto", "narracion": " ".join(oraciones[tercio:tercio*2])},
        {"numero": 3, "duracion": 20, "tipo": "cierre", "titulo": "Conclusión", "narracion": " ".join(oraciones[tercio*2:])}
    ]
    return {"titulo": investigacion["titulo"], "formato": "vertical", "formato_legible": "YouTube Shorts (Documental)", "duracion": 60, "escenas": escenas}

# ==========================================================
# DECISIÓN EDITORIAL PRINCIPAL
# ==========================================================

def crear_guion():
    # 50% de probabilidad de hacer Drama, 50% Documental
    es_drama = random.choice([True, False])

    if es_drama:
        print("[EDITORIAL] Turno de DRAMA (Reddit Style)")
        guion = generar_historia_drama()
        if guion:
            return guion
        print("[EDITORIAL] Falló el drama, cambiando a documental...")

    print("[EDITORIAL] Turno de DOCUMENTAL")
    inv = seleccionar_tema()
    if not inv:
        raise RuntimeError("No se pudo generar contenido.")
    return crear_guion_documental(inv)

# ==========================================================
# GUARDAR Y REGISTRAR
# ==========================================================

def guardar_guion():
    guion = crear_guion()
    
    # Agregar metadatos finales
    guion["idioma"] = IDIOMA
    guion["creado"] = datetime.now().astimezone().isoformat()
    guion["hashtags"] = ["#Shorts", "#Drama", "#Reddit", "#Historias", "#FORTALEZAMEDIA"]
    guion["descripcion"] = f"{guion['titulo']}\n\n" + " ".join(guion["hashtags"])

    temporal = ARCHIVO_GUION.with_suffix(".tmp")
    with open(temporal, "w", encoding="utf-8") as archivo:
        json.dump(guion, archivo, ensure_ascii=False, indent=4)
    temporal.replace(ARCHIVO_GUION)

    historial = cargar_historial()
    historial.append({"titulo": guion["titulo"], "formato": guion["formato_legible"], "creado": guion["creado"]})
    guardar_historial(historial)

    print("=" * 55)
    print("GUION GENERADO")
    print("Título:", guion["titulo"])
    print("Tipo:", guion["formato_legible"])
    print("Escenas:", len(guion["escenas"]))
    print("=" * 55)

    return guion

if __name__ == "__main__":
    guardar_guion()