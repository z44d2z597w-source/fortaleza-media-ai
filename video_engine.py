import json
import random
import re
import requests
import urllib.parse

from datetime import datetime, timedelta, timezone
from pathlib import Path

# Intentar importar pytrends para buscar tendencias
try:
    from pytrends.request import TrendReq
    TIENE_PYTRENDS = True
except ImportError:
    TIENE_PYTRENDS = False

# ==========================================================
# FORTALEZA MEDIA AI 8.0
# MOTOR EDITORIAL: TENDENCIAS + DRAMA + DOCUMENTAL
# ==========================================================

VERSION = "8.0"
IDIOMA = "es-MX"

ARCHIVO_GUION = Path("guion.json")
ARCHIVO_HISTORIAL = Path("historial_temas.json")

URL_WIKIPEDIA = "https://es.wikipedia.org/w/api.php"
CABECERAS = {"User-Agent": "FORTALEZA-MEDIA-AI/8.0"}
MAX_HISTORIAL = 300

TEMAS_RESPALDO = [
    "Fosa de las Marianas", "Bioluminiscencia", "Tiburón de Groenlandia",
    "Aurora polar", "Agujeros negros", "Volcanes submarinos", "Antártida",
    "Planeta Marte", "Cerebro humano", "Bosques tropicales", "Océanos",
]

# ==========================================================
# HISTORIAL
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
# BÚSQUEDA DE TENDENCIAS (GOOGLE TRENDS)
# ==========================================================

def obtener_tendencias_google():
    if not TIENE_PYTRENDS:
        print("[TENDENCIAS] pytrends no está instalado. Omitiendo.")
        return []
    
    print("[TENDENCIAS] Consultando Google Trends (México)...")
    try:
        pytrends = TrendReq(hl='es-MX', tz=-360) # tz=-360 para CDMX
        # Obtener búsquedas del día en México
        trending_searches = pytrends.trending_searches(pn='mexico')
        tendencias = trending_searches[0].tolist()
        
        # Filtrar las que ya se usaron
        historial = cargar_historial()
        tendencias_limpias = [t for t in tendencias if not tema_ya_utilizado(t, historial)]
        
        print(f"[TENDENCIAS] Encontradas {len(tendencias_limpias)} tendencias nuevas.")
        return tendencias_limpias[:5] # Solo las top 5
    except Exception as e:
        print(f"[TENDENCIAS] Error consultando Google Trends: {e}")
        return []

# ==========================================================
# GENERACIÓN DE GUIONES BASADOS EN TENDENCIAS
# ==========================================================

def generar_guion_tendencia(tendencia):
    print(f"[VIRAL] Creando guion sobre la tendencia: '{tendencia}'")
    
    # Le pedimos a la IA que escriba un guion atractivo sobre el tema de moda
    prompt = (
        f"Escribe un guion corto y viral en español para un video vertical sobre el tema en tendencia: '{tendencia}'. "
        "El guion debe tener un gancho intrigante al inicio, un desarrollo rápido y un cierre que invite a comentar. "
        "Divide el texto en 4 escenas separadas por saltos de línea. No uses introducciones, solo el texto del guion."
    )
    prompt_encoded = urllib.parse.quote(prompt)
    url = f"https://text.pollinations.ai/{prompt_encoded}?model=openai"
    
    try:
        respuesta = requests.get(url, timeout=60)
        respuesta.raise_for_status()
        texto = respuesta.text.strip()
        
        # Limpiar y dividir en oraciones
        oraciones = [o.strip() for o in re.split(r"(?<=[.!?])\s+", texto) if len(o.strip()) > 15]
        
        if len(oraciones) < 4:
            return None

        tercio = len(oraciones) // 4
        escenas = [
            {"numero": 1, "duracion": 10, "tipo": "gancho", "titulo": f"¿Qué es {tendencia}?", "narracion": " ".join(oraciones[:tercio])},
            {"numero": 2, "duracion": 15, "tipo": "desarrollo", "titulo": "El contexto", "narracion": " ".join(oraciones[tercio:tercio*2])},
            {"numero": 3, "duracion": 15, "tipo": "revelacion", "titulo": "Lo que nadie dice", "narracion": " ".join(oraciones[tercio*2:tercio*3])},
            {"numero": 4, "duracion": 10, "tipo": "cierre", "titulo": "Conclusión", "narracion": " ".join(oraciones[tercio*3:]) + " ¿Tú qué opinas? Comenta."}
        ]
        
        return {
            "titulo": f"TENDENCIA: {tendencia[:50]}",
            "formato": "vertical",
            "formato_legible": "YouTube Shorts (Tendencia Viral)",
            "duracion": 50,
            "escenas": escenas
        }
    except Exception as e:
        print(f"[VIRAL] Error generando guion: {e}")
        return None

# ==========================================================
# GENERACIÓN DE DRAMA (REDDIT STYLE)
# ==========================================================

def generar_historia_drama():
    print("[DRAMA] Generando historia de drama con IA...")
    prompt = "Escribe una historia corta de drama estilo Reddit (AITA) en español. Conflicto familiar o de pareja. Gancho fuerte, desarrollo tenso y final impactante."
    prompt_encoded = urllib.parse.quote(prompt)
    url = f"https://text.pollinations.ai/{prompt_encoded}?model=openai"
    
    try:
        respuesta = requests.get(url, timeout=60)
        texto = respuesta.text.strip()
        oraciones = [o.strip() for o in re.split(r"(?<=[.!?])\s+", texto) if len(o.strip()) > 20]
        
        if len(oraciones) < 4: return None

        tercio = len(oraciones) // 4
        escenas = [
            {"numero": 1, "duracion": 10, "tipo": "gancho", "titulo": "El problema", "narracion": " ".join(oraciones[:tercio])},
            {"numero": 2, "duracion": 15, "tipo": "desarrollo", "titulo": "Lo que pasó después", "narracion": " ".join(oraciones[tercio:tercio*2])},
            {"numero": 3, "duracion": 15, "tipo": "revelacion", "titulo": "La verdad sale a la luz", "narracion": " ".join(oraciones[tercio*2:tercio*3])},
            {"numero": 4, "duracion": 10, "tipo": "cierre", "titulo": "El desenlace", "narracion": " ".join(oraciones[tercio*3:]) + " ¿Tú qué harías? Comenta."}
        ]
        
        return {"titulo": "Una historia increíble", "formato": "vertical", "formato_legible": "YouTube Shorts (Drama)", "duracion": 50, "escenas": escenas}
    except Exception:
        return None

# ==========================================================
# DOCUMENTALES (WIKIPEDIA)
# ==========================================================

def investigar_tema(titulo):
    parametros = {"action": "query", "format": "json", "prop": "extracts", "titles": titulo, "explaintext": 1, "redirects": 1}
    try:
        respuesta = requests.get(URL_WIKIPEDIA, params=parametros, headers=CABECERAS, timeout=25)
        paginas = respuesta.json().get("query", {}).get("pages", {})
        for pagina in paginas.values():
            extracto = re.sub(r"\[\d+\]", "", pagina.get("extract", "")).strip()
            if len(extracto) < 600: return None
            return {"titulo": pagina.get("title", titulo), "texto": extracto[:12000]}
    except Exception:
        return None

def crear_guion_documental():
    inv = None
    for t in random.sample(TEMAS_RESPALDO, len(TEMAS_RESPALDO)):
        inv = investigar_tema(t)
        if inv: break
    
    if not inv: return None

    oraciones = [o.strip() for o in re.split(r"(?<=[.!?])\s+", inv["texto"]) if len(o.strip()) > 35]
    tercio = len(oraciones) // 3
    escenas = [
        {"numero": 1, "duracion": 15, "tipo": "gancho", "titulo": inv["titulo"], "narracion": " ".join(oraciones[:tercio])},
        {"numero": 2, "duracion": 25, "tipo": "desarrollo", "titulo": "El contexto", "narracion": " ".join(oraciones[tercio:tercio*2])},
        {"numero": 3, "duracion": 20, "tipo": "cierre", "titulo": "Conclusión", "narracion": " ".join(oraciones[tercio*2:])}
    ]
    return {"titulo": inv["titulo"], "formato": "vertical", "formato_legible": "YouTube Shorts (Documental)", "duracion": 60, "escenas": escenas}

# ==========================================================
# DECISIÓN EDITORIAL PRINCIPAL (TENDENCIA > DRAMA > DOCUMENTAL)
# ==========================================================

def crear_guion():
    # 1. PRIORIDAD: TENDENCIAS
    tendencias = obtener_tendencias_google()
    if tendencias:
        # Intentar con las 3 primeras tendencias por si la IA falla
        for tendencia in tendencias[:3]:
            guion = generar_guion_tendencia(tendencia)
            if guion: return guion

    # 2. SEGUNDA OPCIÓN: DRAMA
    print("[EDITORIAL] Sin tendencias claras. Pasando a Drama...")
    guion = generar_historia_drama()
    if guion: return guion

    # 3. ÚLTIMA OPCIÓN: DOCUMENTAL
    print("[EDITORIAL] Drama falló. Pasando a Documental...")
    guion = crear_guion_documental()
    if guion: return guion

    raise RuntimeError("No se pudo generar ningún tipo de contenido.")

# ==========================================================
# GUARDAR
# ==========================================================

def guardar_guion():
    guion = crear_guion()
    
    guion["idioma"] = IDIOMA
    guion["creado"] = datetime.now().astimezone().isoformat()
    guion["hashtags"] = ["#Shorts", "#Tendencias", "#Viral", "#FORTALEZAMEDIA"]
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
    print("=" * 55)

    return guion

if __name__ == "__main__":
    guardar_guion()