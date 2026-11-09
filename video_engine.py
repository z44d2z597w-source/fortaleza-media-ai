import json
import random
import re
import requests
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

try:
    from pytrends.request import TrendReq
    TIENE_PYTRENDS = True
except ImportError:
    TIENE_PYTRENDS = False

# ==========================================================
# FORTALEZA MEDIA AI 10.0
# CEREBRO COMPLETO: TENDENCIAS + DRAMA IA + LOOP
# ==========================================================

VERSION = "10.0"
IDIOMA = "es-MX"
ARCHIVO_GUION = Path("guion.json")
ARCHIVO_HISTORIAL = Path("historial_temas.json")
CABECERAS = {"User-Agent": "FORTALEZA-MEDIA-AI/10.0"}

# Historias de respaldo por si la IA se cae
HISTORIAS_RESPALDO = [
    {
        "titulo": "El secreto de la habitación 404",
        "escenas": [
            {"numero": 1, "duracion": 8, "tipo": "gancho", "titulo": "El inicio", "narracion": "¡No vas a creer esto! Un hombre entró a un hotel y pidió la habitación 404. Lo que encontró adentro cambió su vida."},
            {"numero": 2, "duracion": 12, "tipo": "desarrollo", "titulo": "El conflicto", "narracion": "Al abrir la puerta, la habitación no tenía muebles. Solo había un espejo gigante que reflejaba un cuarto diferente."},
            {"numero": 3, "duracion": 12, "tipo": "revelacion", "titulo": "El giro", "narracion": "Cuando tocó el espejo, su mano atravesó el vidrio. Del otro lado, alguien exactamente igual a él lo estaba esperando."},
            {"numero": 4, "duracion": 8, "tipo": "cierre", "titulo": "El loop", "narracion": "Y por eso te digo... ¡No vas a creer esto!"}
        ]
    },
    {
        "titulo": "La desaparición en el bosque",
        "escenas": [
            {"numero": 1, "duracion": 8, "tipo": "gancho", "titulo": "El inicio", "narracion": "¡No vas a creer esto! Una pareja acampando en el bosque escuchó pasos afuera de su tienda de campaña."},
            {"numero": 2, "duracion": 12, "tipo": "desarrollo", "titulo": "El conflicto", "narracion": "Los pasos se detuvieron. Cuando salieron a revisar, encontraron huellas que no eran humanas, caminando en círculos perfectos."},
            {"numero": 3, "duracion": 12, "tipo": "revelacion", "titulo": "El giro", "narracion": "Al día siguiente, las fotos de su cámara mostraban que algo estuvo observándolos desde los árboles toda la noche."},
            {"numero": 4, "duracion": 8, "tipo": "cierre", "titulo": "El loop", "narracion": "Y por eso te digo... ¡No vas a creer esto!"}
        ]
    }
]

def cargar_historial():
    if not ARCHIVO_HISTORIAL.exists(): return []
    try:
        with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def guardar_historial(historial):
    with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=4)

def tema_ya_utilizado(titulo, historial):
    for e in historial:
        anterior = str(e.get("titulo", "") if isinstance(e, dict) else e).strip().lower()
        if anterior == titulo.strip().lower():
            return True
    return False

def obtener_tendencias_google():
    if not TIENE_PYTRENDS: 
        print("[TENDENCIAS] pytrends no instalado. Saltando...")
        return []
    print("[TENDENCIAS] Consultando Google Trends (México)...")
    try:
        pytrends = TrendReq(hl='es-MX', tz=-360)
        trending = pytrends.trending_searches(pn='mexico')[0].tolist()
        historial = cargar_historial()
        return [t for t in trending if not tema_ya_utilizado(t, historial)][:3]
    except Exception as e:
        print(f"[TENDENCIAS] Error: {e}")
        return []

def generar_historia_con_ia(prompt):
    print("[IA] Escribiendo historia con Pollinations...")
    prompt_encoded = urllib.parse.quote(prompt)
    url = f"https://text.pollinations.ai/{prompt_encoded}?model=openai"
    
    try:
        respuesta = requests.get(url, timeout=60)
        respuesta.raise_for_status()
        texto = respuesta.text.strip()
        
        # Limpiar el texto
        texto = re.sub(r"^(Escena \d+:?|Aquí tienes.*?:)", "", texto, flags=re.IGNORECASE|re.MULTILINE).strip()
        oraciones = [o.strip() for o in re.split(r"(?<=[.!?])\s+", texto) if len(o.strip()) > 10]
        
        if len(oraciones) < 4: return None

        cuarto = len(oraciones) // 4
        escenas = [
            {"numero": 1, "duracion": 8, "tipo": "gancho", "titulo": "El inicio", "narracion": " ".join(oraciones[:cuarto])},
            {"numero": 2, "duracion": 12, "tipo": "desarrollo", "titulo": "El conflicto", "narracion": " ".join(oraciones[cuarto:cuarto*2])},
            {"numero": 3, "duracion": 12, "tipo": "revelacion", "titulo": "El giro", "narracion": " ".join(oraciones[cuarto*2:cuarto*3])},
            {"numero": 4, "duracion": 8, "tipo": "cierre", "titulo": "El loop", "narracion": " ".join(oraciones[cuarto*3:])}
        ]
        
        return {
            "titulo": "La historia que no te esperabas",
            "formato": "vertical",
            "formato_legible": "YouTube Shorts (IA Drama)",
            "duracion": 40,
            "escenas": escenas
        }
    except Exception as e:
        print(f"[IA] Error generando historia: {e}")
        return None

def crear_guion():
    # 1. Intentar con Tendencias de Google
    tendencias = obtener_tendencias_google()
    if tendencias:
        for t in tendencias:
            prompt = f"Escribe un guion corto y viral en español sobre el tema en tendencia '{t}'. REGLA 1: Empieza con una frase de 5 palabras que impacte. REGLA 2: El final debe terminar con las mismas palabras del inicio para crear un LOOP. Divide el texto en 4 escenas separadas por saltos de línea."
            guion = generar_historia_con_ia(prompt)
            if guion:
                guion["titulo"] = f"TENDENCIA: {t[:40]}"
                guion["formato_legible"] = "YouTube Shorts (Tendencia)"
                return guion

    # 2. Intentar con Drama IA
    print("[EDITORIAL] Sin tendencias. Pasando a Drama IA...")
    prompt_drama = "Escribe una historia de misterio o drama (estilo Reddit) en español. REGLA 1: Empieza con un gancho brutal (Ej: 'No vas a creer esto:'). REGLA 2: El último segundo debe conectar perfectamente con la primera frase para crear un LOOP. Usa frases cortas. Divide el texto en 4 escenas separadas por saltos de línea."
    guion = generar_historia_con_ia(prompt_drama)
    if guion: return guion

    # 3. Plan B: Historia pre-escrita
    print("[EDITORIAL] IA falló. Usando historia de respaldo...")
    historia = random.choice(HISTORIAS_RESPALDO)
    return {
        "titulo": historia["titulo"],
        "formato": "vertical",
        "formato_legible": "YouTube Shorts (Respaldo)",
        "duracion": 40,
        "escenas": historia["escenas"]
    }

def guardar_guion():
    guion = crear_guion()
    
    guion["idioma"] = IDIOMA
    guion["creado"] = datetime.now(timezone.utc).isoformat()
    guion["hashtags"] = ["#Shorts", "#Viral", "#Misterio", "#FORTALEZAMEDIA"]
    guion["descripcion"] = f"{guion['titulo']}\n\n" + " ".join(guion["hashtags"])

    with open(ARCHIVO_GUION, "w", encoding="utf-8") as f:
        json.dump(guion, f, ensure_ascii=False, indent=4)

    historial = cargar_historial()
    historial.append({"titulo": guion["titulo"], "creado": guion["creado"]})
    guardar_historial(historial)

    print("=" * 55)
    print("GUION GENERADO CON ÉXITO")
    print("Título:", guion["titulo"])
    print("Tipo:", guion["formato_legible"])
    print("=" * 55)
    return guion

# ESTA LÍNEA ES LA QUE FALTABA Y CAUSABA EL ERROR:
if __name__ == "__main__":
    guardar_guion()