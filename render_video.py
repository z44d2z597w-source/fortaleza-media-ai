import asyncio
import html
import json
import math
import os
import random
import re
import shutil
import subprocess
import urllib.parse
import wave
from array import array
from io import BytesIO
from pathlib import Path

import requests
import edge_tts
import imageio_ffmpeg
from PIL import (
    Image, ImageDraw, ImageFont, ImageEnhance,
    ImageFilter, ImageOps,
)

# ==========================================================
# FORTALEZA MEDIA AI 13.0 — EDICIÓN TITÁN
# SISTEMA EVOLUTIVO MULTIDIMENSIONAL + AUDIO DUCKING
# ==========================================================

FPS = 30
VOZ = "es-MX-DaliaNeural"
VELOCIDAD_VOZ = "+8%"

OUTPUT = Path("output")
RECURSOS = OUTPUT / "recursos"
ARCHIVO_CONFIG = Path("config_edicion.json")
REPORTE_PRODUCCION = OUTPUT / "reporte_edicion.json"

MAX_ESCENAS = 20
IMAGENES_POR_ESCENA = 6

# Configuración por defecto del sistema evolutivo
CONFIG_DEFECTO = {
    "corte_min": 1.8,
    "corte_max": 4.5,
    "zoom_intensidad": 0.0015,
    "score_global": 0,
    "score_pacing": 0,
    "score_visual": 0,
    "score_audio": 0,
    "score_texto": 0,
    "intentos": 0,
    "historial_scores": []
}

PALABRAS_IMPACTO = [
    "increíble", "sorprendente", "misterio", "secreto", "peligro", 
    "jamás", "nunca", "impactante", "aterrador", "asombroso", 
    "oculto", "verdad", "ciencia", "descubrimiento", "tendencia", 
    "viral", "drama", "historia", "enigma", "prohibido"
]

CABECERAS = {
    "User-Agent": "FortalezaMediaAI/13.0 (https://github.com/z44d2z597w-source/fortaleza-media-ai) python-requests"
}

PALETAS = [
    ("#071426", "#123D60", "#39B8D8"), ("#180D2C", "#43205E", "#B56CFF"),
    ("#111B18", "#245B43", "#65D6A0"), ("#29100D", "#74301F", "#FFAD64"),
    ("#10152C", "#293D75", "#82A7FF"), ("#25152B", "#63344E", "#FF83AE"),
    ("#2B0A0A", "#6B1010", "#FF4444"), ("#0A2B2B", "#106B6B", "#44FFFF"),
]

STOPWORDS = {
    "para", "porque", "sobre", "desde", "hasta", "donde", "cuando", "también",
    "tienen", "tiene", "puede", "pueden", "entre", "esto", "esta", "este",
    "como", "pero", "algo", "algunos", "algunas", "todo", "todos", "cada",
    "muchas", "muchos", "hacia", "después", "durante", "ser", "son", "del",
    "las", "los", "una", "uno", "unos", "unas", "con", "sin", "por",
    "que", "sus", "hay", "más", "muy", "hoy", "nuestro", "nuestra",
}

# ==========================================================
# 1. SISTEMA EVOLUTIVO (EL CEREBRO)
# ==========================================================

def cargar_configuracion_evolutiva():
    if ARCHIVO_CONFIG.exists():
        try:
            with open(ARCHIVO_CONFIG, "r", encoding="utf-8") as f:
                config = json.load(f)
                print(f"[EVOLUCIÓN] Cerebro cargado. Intento N° {config.get('intentos', 1)}.")
                print(f"[EVOLUCIÓN] Score Global anterior: {config.get('score_global', 0)}/100")
                return config
        except Exception as e:
            print(f"[EVOLUCIÓN] Error leyendo config, usando defecto: {e}")
    return CONFIG_DEFECTO.copy()

def evaluar_y_mutar(config, metricas):
    print("\n[EVOLUCIÓN] Evaluando calidad de la edición...")
    
    # 1. Evaluación de Pacing (Ritmo)
    score_pacing = 50
    if metricas["promedio_toma"] < 2.5: score_pacing += 30
    elif metricas["promedio_toma"] < 3.5: score_pacing += 15
    elif metricas["promedio_toma"] > 5.0: score_pacing -= 20
    
    # 2. Evaluación Visual
    score_visual = 50
    if metricas["ratio_video"] > 0.5: score_visual += 30  # Prefiere video sobre fotos
    elif metricas["ratio_video"] > 0.2: score_visual += 15
    if metricas["uso_ia"] > 0: score_visual -= 10 # La IA es respaldo, no ideal

    # 3. Evaluación de Audio
    score_audio = 80
    if metricas["whooshes_colocados"] > 5: score_audio += 20

    # 4. Evaluación de Texto
    score_texto = 50
    if metricas["textos_impacto"] > 3: score_texto += 25
    if metricas["textos_impacto"] > 8: score_texto += 25

    score_global = int((score_pacing + score_visual + score_audio + score_texto) / 4)

    config["score_global"] = score_global
    config["score_pacing"] = score_pacing
    config["score_visual"] = score_visual
    config["score_audio"] = score_audio
    config["score_texto"] = score_texto
    config["intentos"] = config.get("intentos", 0) + 1
    
    # MUTACIÓN: Si el video fue muy lento (bajo Pacing), cortamos más rápido
    if score_pacing < 60:
        config["corte_min"] = max(1.2, config["corte_min"] - 0.2)
        config["corte_max"] = max(2.5, config["corte_max"] - 0.5)
        print("[EVOLUCIÓN] Mutación: Cortes serán más rápidos mañana.")
    
    # Si el video no tuvo suficiente texto, forzamos más sensibilidad
    if score_texto < 60:
        print("[EVOLUCIÓN] Mutación: Aumentando sensibilidad de palabras de impacto.")

    config["historial_scores"].append(score_global)

    with open(ARCHIVO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    
    print(f"[EVOLUCIÓN] Score Final: {score_global}/100 (Pacing: {score_pacing}, Visual: {score_visual}, Audio: {score_audio}, Texto: {score_texto})")
    return config

CONFIG = cargar_configuracion_evolutiva()

# ==========================================================
# 2. UTILIDADES GENERALES
# ==========================================================

def preparar_carpetas():
    OUTPUT.mkdir(exist_ok=True)
    RECURSOS.mkdir(exist_ok=True)
    for archivo in RECURSOS.iterdir():
        if archivo.is_file(): archivo.unlink()

def obtener_fuente(tamano, negrita=False):
    rutas = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if negrita else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if negrita else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for ruta in rutas:
        if os.path.exists(ruta): return ImageFont.truetype(ruta, tamano)
    return ImageFont.load_default()

def ejecutar_ffmpeg(comando):
    resultado = subprocess.run(comando, capture_output=True, text=True)
    if resultado.returncode != 0:
        raise RuntimeError(f"FALLO FFmpeg:\n{resultado.stderr[-6000:]}")
    return resultado

def limpiar_texto_html(texto):
    return html.unescape(re.sub(r"<[^>]+>", "", str(texto))).strip()

def obtener_duracion(ffmpeg, archivo):
    resultado = subprocess.run([ffmpeg, "-i", str(archivo)], capture_output=True, text=True)
    coincidencia = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", resultado.stderr)
    if not coincidencia: raise RuntimeError(f"No se pudo leer duración de {archivo}")
    h, m, s = coincidencia.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)

def hex_a_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

def dividir_texto_en_lineas(dibujo, texto, font, ancho_maximo):
    lineas = []
    linea_actual = ""
    for palabra in texto.split():
        prueba = (linea_actual + " " + palabra).strip()
        if dibujo.textbbox((0, 0), prueba, font=font)[2] <= ancho_maximo:
            linea_actual = prueba
        else:
            if linea_actual: lineas.append(linea_actual)
            linea_actual = palabra
    if linea_actual: lineas.append(linea_actual)
    return lineas

# ==========================================================
# 3. MOTOR DE CORTES DINÁMICOS
# ==========================================================

def calcular_tiempos_de_corte(palabras, duracion_total):
    c_min = CONFIG.get("corte_min", 1.8)
    c_max = CONFIG.get("corte_max", 4.5)
    pausa_min = 0.3

    if duracion_total <= 0: return [0.0, duracion_total]
    if not palabras:
        divisiones = max(1, int(round(duracion_total / 3.0)))
        return [i * duracion_total / divisiones for i in range(divisiones + 1)]

    puntos_candidatos = []
    for i in range(1, len(palabras)):
        pausa = palabras[i]["inicio"] - palabras[i - 1]["fin"]
        if pausa >= pausa_min:
            puntos_candidatos.append((palabras[i - 1]["fin"] + palabras[i]["inicio"]) / 2)
            
    for p in palabras:
        if p["texto"].strip().endswith((".", "?", "!")):
            puntos_candidatos.append(p["fin"] + 0.05)

    puntos_candidatos = sorted(set(round(c, 3) for c in puntos_candidatos))
    cortes_aprobados = [0.0]
    
    for c in puntos_candidatos:
        if c - cortes_aprobados[-1] < c_min or duracion_total - c < c_min: continue
        cortes_aprobados.append(c)

    resultado_final = [0.0]
    for c in cortes_aprobados[1:]:
        while c - resultado_final[-1] > c_max: 
            resultado_final.append(resultado_final[-1] + c_max)
        resultado_final.append(c)
    while duracion_total - resultado_final[-1] > c_max: 
        resultado_final.append(resultado_final[-1] + c_max)

    if resultado_final[-1] < duracion_total: resultado_final.append(duracion_total)
    else: resultado_final[-1] = duracion_total
    
    return resultado_final

def ajustar_recursos_a_tomas(recursos_disponibles, cantidad_tomas):
    if cantidad_tomas <= len(recursos_disponibles): 
        return recursos_disponibles[:cantidad_tomas]
    return [recursos_disponibles[i % len(recursos_disponibles)] for i in range(cantidad_tomas)]

# ==========================================================
# 4. BÚSQUEDA Y GENERACIÓN DE MATERIAL VISUAL
# ==========================================================

def generar_palabras_clave_busqueda(titulo, narracion):
    palabras = re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ]{4,}", titulo + " " + narracion)
    filtradas = [p for p in palabras if p.lower() not in STOPWORDS]
    unicas = list(dict.fromkeys(filtradas))
    return " ".join(unicas[:4]) if unicas else "cinematic"

def buscar_videos_stock(titulo, narracion, num_escena, formato):
    clave_api = os.environ.get("PIXABAY_API_KEY")
    if not clave_api: return []
    
    consulta = generar_palabras_clave_busqueda(titulo, narracion)
    print(f"[STOCK] Buscando video de: '{consulta}'")
    
    url = "https://pixabay.com/api/videos/"
    parametros = {"key": clave_api, "q": consulta, "orientation": formato["orientacion"], "per_page": 15, "safesearch": "true"}
    
    try:
        respuesta = requests.get(url, params=parametros, timeout=20)
        hits = respuesta.json().get("hits", [])
    except Exception as e:
        print(f"[STOCK] Error conectando a Pixabay: {e}")
        return []

    descargas = []
    for hit in hits:
        opciones = hit.get("videos", {})
        mejor_video = opciones.get("large") or opciones.get("medium") or opciones.get("small")
        if not mejor_video or "url" not in mejor_video: continue
        
        ruta_destino = RECURSOS / f"stock_vid_{num_escena:02d}_{len(descargas):02d}.mp4"
        try:
            with requests.get(mejor_video["url"], stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(ruta_destino, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            if os.path.getsize(ruta_destino) < 15000: continue # Archivo muy pequeño (corrupto)
            descargas.append({"tipo": "video", "archivo": str(ruta_destino)})
            if len(descargas) >= 3: break # Máximo 3 clips por escena para no saturar
        except Exception:
            pass
            
    return descargas

def buscar_fotos_wikimedia(titulo, narracion, num_escena):
    consulta = generar_palabras_clave_busqueda(titulo, narracion)
    print(f"[STOCK] Buscando fotos de: '{consulta}'")
    
    parametros = {"action": "query", "generator": "search", "gsrsearch": consulta, "gsrnamespace": 6, "gsrlimit": 20, "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 1600, "format": "json"}
    
    try:
        respuesta = requests.get("https://commons.wikimedia.org/w/api.php", params=parametros, headers=CABECERAS, timeout=25)
        paginas = respuesta.json().get("query", {}).get("pages", {})
    except Exception:
        return []

    descargas = []
    for pagina in paginas.values():
        info = pagina.get("imageinfo", [{}])[0]
        if not info.get("mime", "").startswith("image/"): continue
        
        url_imagen = info.get("thumburl") or info.get("url")
        try:
            binario = requests.get(url_imagen, headers=CABECERAS, timeout=20).content
            imagen = Image.open(BytesIO(binario)).convert("RGB")
            if imagen.width < 600 or imagen.height < 400: continue
            
            ruta_destino = RECURSOS / f"stock_img_{num_escena:02d}_{len(descargas):02d}.jpg"
            imagen.save(ruta_destino, "JPEG", quality=92)
            descargas.append({"tipo": "foto", "archivo": str(ruta_destino)})
            if len(descargas) >= IMAGENES_POR_ESCENA: break
        except Exception:
            pass
            
    return descargas

def generar_imagen_artificial(prompt, num_escena, formato):
    print(f"[IA] Generando imagen para: '{prompt[:50]}...'")
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width={formato['ancho']}&height={formato['alto']}&nologo=true&enhance=true"
    
    try:
        respuesta = requests.get(url, timeout=90)
        respuesta.raise_for_status()
        ruta_destino = RECURSOS / f"ia_img_{num_escena:02d}.jpg"
        with open(ruta_destino, "wb") as f: f.write(respuesta.content)
        return {"tipo": "foto", "archivo": str(ruta_destino)}
    except Exception as e:
        print(f"[IA] Falló la generación visual: {e}")
        return None

# ==========================================================
# 5. GENERACIÓN DE AUDIO Y EFECTOS
# ==========================================================

async def generar_voz_ia(texto, ruta_salida):
    comunicacion = edge_tts.Communicate(texto, voice=VOZ, rate=VELOCIDAD_VOZ, pitch="+0Hz")
    audio_bytes = bytearray()
    marcas_palabras = []
    
    async for fragmento in comunicacion.stream():
        if fragmento["type"] == "audio": 
            audio_bytes.extend(fragmento["data"])
        elif fragmento["type"] == "WordBoundary":
            inicio = fragmento["offset"] / 10000000
            marcas_palabras.append({
                "texto": fragmento["text"], 
                "inicio": inicio, 
                "fin": inicio + (fragmento["duration"] / 10000000)
            })
            
    with open(ruta_salida, "wb") as f: 
        f.write(audio_bytes)
    return marcas_palabras

def generar_efecto_whoosh(ruta_salida):
    frecuencia, duracion = 44100, 0.4
    datos = array("h")
    for i in range(int(frecuencia * duracion)):
        t = i / frecuencia
        vol = (t / duracion) * (1 - t / duracion) * 4
        ruido = random.uniform(-1, 1)
        datos.append(int(32767 * 0.2 * vol * ruido))
        datos.append(int(32767 * 0.2 * vol * ruido))
    with wave.open(str(ruta_salida), "wb") as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(frecuencia)
        f.writeframes(datos.tobytes())
    return str(ruta_salida)

def generar_musica_ambiente(duracion_total):
    ruta_salida = RECURSOS / "musica_ambiente.wav"
    frecuencia = 22050
    datos = array("h")
    for i in range(int(frecuencia * duracion_total)):
        t = i / frecuencia
        modulacion = 0.65 + 0.35 * math.sin(2 * math.pi * 0.035 * t)
        sonido = (math.sin(2*math.pi*110*t)*0.26 + math.sin(2*math.pi*164.81*t)*0.18 + math.sin(2*math.pi*220*t)*0.11)
        valor = int(32767 * 0.055 * modulacion * sonido)
        datos.append(valor); datos.append(valor)
    with wave.open(str(ruta_salida), "wb") as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(frecuencia)
        f.writeframes(datos.tobytes())
    return str(ruta_salida)

# ==========================================================
# 6. DISEÑO GRÁFICO Y OVERLAYS
# ==========================================================

def crear_grafico_subtitulo(palabras_grupo, num_grupo, formato):
    ancho, alto = formato["ancho"], formato["alto"]
    imagen = Image.new("RGBA", (ancho, alto), (0,0,0,0))
    dibujo = ImageDraw.Draw(imagen)
    
    font = obtener_fuente(int(ancho * 0.045), True)
    texto_completo = " ".join(x["texto"] for x in palabras_grupo)
    lineas = dividir_texto_en_lineas(dibujo, texto_completo, font, int(ancho*0.82))[:2]
    
    y_inicial = int(alto * 0.82) - (len(lineas) * 60) // 2
    y_actual = y_inicial
    
    for linea in lineas:
        dibujo.text((ancho//2, y_actual), linea, font=font, fill="white", anchor="mm", stroke_width=4, stroke_fill="#000000")
        y_actual += 70
        
    ruta_destino = RECURSOS / f"sub_{num_grupo:04d}.png"
    imagen.save(ruta_destino)
    return str(ruta_destino)

def crear_grafico_lower_third(titulo_escena, formato, color_acento, num_escena):
    ancho, alto = formato["ancho"], formato["alto"]
    imagen = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(imagen)
    
    x, y = int(ancho * 0.06), int(alto * 0.65)
    caja_ancho, caja_alto = int(ancho * 0.80), int(alto * 0.12)
    
    dibujo.rounded_rectangle((x, y, x + caja_ancho, y + caja_alto), radius=15, fill=(0, 0, 0, 200), outline=(*hex_a_rgb(color_acento), 255), width=4)
    dibujo.rectangle((x, y, x + 10, y + caja_alto), fill=(*hex_a_rgb(color_acento), 255))
    
    font = obtener_fuente(int(ancho * 0.035), True)
    lineas = dividir_texto_en_lineas(dibujo, titulo_escena.upper(), font, caja_ancho - 50)[:2]
    
    y_texto = y + (caja_alto - len(lineas) * int(ancho * 0.045)) // 2
    for linea in lineas:
        dibujo.text((x + 35, y_texto), linea, font=font, fill="white")
        y_texto += int(ancho * 0.045)
        
    ruta_destino = RECURSOS / f"lower_third_{num_escena:02d}.png"
    imagen.save(ruta_destino)
    return str(ruta_destino)

def crear_grafico_texto_gigante(palabra, formato):
    ancho, alto = formato["ancho"], formato["alto"]
    imagen = Image.new("RGBA", (ancho, alto), (0,0,0,0))
    dibujo = ImageDraw.Draw(imagen)
    
    tamano_font = int(ancho * 0.15)
    font = obtener_fuente(tamano_font, True)
    
    # Sombra dura para que resalte en cualquier fondo
    dibujo.text((ancho//2 + 10, alto//2 + 10), palabra.upper(), font=font, fill=(0,0,0,220), anchor="mm")
    # Texto principal
    dibujo.text((ancho//2, alto//2), palabra.upper(), font=font, fill="white", anchor="mm", stroke_width=8, stroke_fill="#FF0055")
    
    ruta_destino = RECURSOS / f"impacto_{random.randint(10000,99999)}.png"
    imagen.save(ruta_destino)
    return str(ruta_destino)

# ==========================================================
# 7. MOTOR DE RENDERIZADO VISUAL
# ==========================================================

def crear_toma_individual(ffmpeg, ruta_recurso, ruta_destino, duracion_toma, indice_toma, formato, es_impacto=False):
    ancho, alto = formato["ancho"], formato["alto"]
    es_video = ruta_recurso.endswith(".mp4")
    filtros = []

    # 1. Escalado inicial (1.2x para permitir movimiento de cámara sin bordes negros)
    filtros.append(f"scale={int(ancho*1.2)}:{int(alto*1.2)}:force_original_aspect_ratio=increase,crop={int(ancho*1.2)}:{int(alto*1.2)}")

    # 2. Matriz de 10 movimientos de cámara
    matriz_movimientos = [
        ("min(zoom+0.0015,1.3)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"), # Zoom In Centro
        ("min(zoom+0.0020,1.4)", "iw/2-(iw/zoom/2)+on*0.15", "ih/2-(ih/zoom/2)"), # Zoom In + Paneo Der
        ("min(zoom+0.0015,1.3)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)+on*0.15"), # Zoom In + Paneo Abajo
        ("max(zoom-0.0010,1.0)", "iw/2-(iw/zoom/2)-on*0.10", "ih/2-(ih/zoom/2)"), # Zoom Out + Paneo Izq
        ("min(zoom+0.0012,1.25)", "iw/2-(iw/zoom/2)-on*0.10", "ih/2-(ih/zoom/2)-on*0.10"), # Diagonal Arriba Izq
        ("min(zoom+0.0012,1.25)", "iw/2-(iw/zoom/2)+on*0.10", "ih/2-(ih/zoom/2)-on*0.10"), # Diagonal Arriba Der
        ("max(zoom-0.0008,1.0)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)+on*0.08"), # Zoom Out + Paneo Abajo
        ("min(zoom+0.0018,1.35)", "iw/2-(iw/zoom/2)+on*0.20", "ih/2-(ih/zoom/2)"), # Paneo Rápido Der
        ("min(zoom+0.0010,1.2)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)-on*0.10"), # Paneo Arriba
        ("min(zoom+0.0015,1.3)", "iw/2-(iw/zoom/2)-on*0.15", "ih/2-(ih/zoom/2)")  # Paneo Rápido Izq
    ]
    
    zoom, x, y = matriz_movimientos[indice_toma % len(matriz_movimientos)]

    if es_impacto and not es_video:
        # Zoom PUNCH (Golpe visual en el primer frame)
        filtros.append(f"zoompan=z='if(lt(on,15),1.6-on/25,1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={ancho}x{alto}:fps={FPS}")
    elif not es_video:
        # Movimiento normal para fotos
        filtros.append(f"zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s={ancho}x{alto}:fps={FPS}")
    else:
        # Para video real (Pixabay), no aplicamos zoompan porque ya tienen movimiento
        filtros.append(f"scale={ancho}:{alto}:force_original_aspect_ratio=increase,crop={ancho}:{alto}")

    # 3. Etalonaje Cinematográfico (Color, Contraste, Nitidez)
    filtros.append("eq=contrast=1.18:brightness=-0.02:saturation=1.30:gamma=0.95")
    filtros.append("curves=preset=medium_contrast")
    filtros.append("unsharp=5:5:0.8:5:5:0.0")

    # 4. Pattern Interrupt (Glitch y Aberración Cromática en el impacto)
    if es_impacto:
        filtros.append("rgbashift=rh=10:bh=-10:enable='lt(t,0.25)'")
        filtros.append("chromashift=cbh=6:crh=-6:enable='lt(t,0.25)'")

    # 5. Cierre
    filtros.append("setsar=1,format=yuv420p")
    cadena_filtros = ",".join(filtros)

    # Construir comando
    comando = [ffmpeg, "-y"]
    if es_video:
        comando.extend(["-stream_loop", "-1", "-i", ruta_recurso])
    else:
        comando.extend(["-loop", "1", "-framerate", str(FPS), "-i", ruta_recurso])
        
    comando.extend([
        "-vf", cadena_filtros, "-t", f"{duracion_toma:.3f}", "-an", 
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", 
        "-pix_fmt", "yuv420p", "-r", str(FPS), str(ruta_destino)
    ])
    ejecutar_ffmpeg(comando)

def concatenar_tomas_escena(ffmpeg, lista_tomas, ruta_destino, archivo_txt_lista):
    with open(archivo_txt_lista, "w", encoding="utf-8") as f:
        for t in lista_tomas: f.write(f"file '{Path(t).resolve()}'\n")
        
    ejecutar_ffmpeg([
        ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(archivo_txt_lista),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p", "-r", str(FPS), "-an", str(ruta_destino)
    ])

def unir_todas_las_escenas_xfade(ffmpeg, lista_escenas, duraciones_escenas, ruta_destino):
    n = len(lista_escenas)
    if n == 1: 
        shutil.copy2(lista_escenas[0], ruta_destino)
        return
        
    filtros = []
    last_v, last_a = "[v0]", "[a0]"
    offset = 0.0
    xfade_dur = 0.4
    
    for i in range(n):
        filtros.extend([f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS[v{i}]", f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]"])
        
    for i in range(1, n):
        offset += duraciones_escenas[i - 1] - xfade_dur
        filtros.append(f"{last_v}[v{i}]xfade=transition='smoothleft':duration={xfade_dur}:offset={offset:.3f}[vx{i}]")
        filtros.append(f"{last_a}[a{i}]acrossfade=d={xfade_dur}:c1=tri:c2=tri[ax{i}]")
        last_v, last_a = f"[vx{i}]", f"[ax{i}]"
        
    comando = [ffmpeg, "-y"]
    for escena in lista_escenas: comando.extend(["-i", escena])
    comando.extend([
        "-filter_complex", ";".join(filtros), "-map", last_v, "-map", last_a,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p", 
        "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", str(ruta_destino)
    ])
    ejecutar_ffmpeg(comando)

# ==========================================================
# 8. MEZCLA FINAL DE AUDIO (CON DUCKING) Y VIDEO
# ==========================================================

def mezcla_final_pro(ffmpeg, video_entrada, musica_entrada, lista_whooshes, ruta_destino, duracion_total):
    print("[RENDER] Aplicando mezcla de audio profesional y barra de progreso...")
    
    # 1. Filtro de Video (Viñeta + Barra de progreso)
    filtro_video = (
        f"[0:v]vignette=PI/6,eq=contrast=1.05:saturation=1.20,"
        f"drawbox=x=0:y=h-10:w='iw*t/{duracion_total}':h=10:color=white@0.8:t=fill,format=yuv420p[vout]"
    )
    
    # 2. Filtro de Audio (Ducking + Limitador)
    # El Ducking hace que la música baje su volumen cuando la voz habla
    filtro_audio = "[1:a]volume=0.15[musica];[0:a]volume=1.0[voz];"
    filtro_audio += "[musica][voz]sidechaincompress=threshold=0.03:ratio=8:attack=200:release=1000[musica_duck];"
    filtro_audio += "[voz][musica_duck]amix=inputs=2:duration=first[base];"
    
    # Mezclar SFX (Whooshes)
    for i in range(len(lista_whooshes)):
        filtro_audio += f"[{i+2}:a]volume=0.6[w{i}];[base][w{i}]amix=inputs=2:duration=first[base];"
        
    filtro_audio += "[base]alimiter=limit=0.95[audio]"
    
    filtro_total = filtro_video + ";" + filtro_audio

    comando = [ffmpeg, "-y", "-i", video_entrada, "-stream_loop", "-1", "-i", musica_entrada]
    for w in lista_whooshes: 
        comando.extend(["-i", w])
        
    comando.extend([
        "-filter_complex", filtro_total, "-map", "[vout]", "-map", "[audio]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-maxrate", "8M", "-bufsize", "16M",
        "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
        "-t", f"{duracion_total:.3f}", "-movflags", "+faststart", ruta_destino
    ])
    ejecutar_ffmpeg(comando)

# ==========================================================
# 9. ORQUESTADOR PRINCIPAL DE PRODUCCIÓN
# ==========================================================

async def crear_video():
    preparar_carpetas()
    
    with open("guion.json", encoding="utf-8") as f: 
        guion = json.load(f)

    titulo = str(guion.get("titulo", "Historia"))
    escenas = [e for e in guion.get("escenas", []) if str(e.get("narracion", "")).strip()][:MAX_ESCENAS]
    
    # Forzar formato vertical para máxima retención
    formato = {"nombre": "vertical", "ancho": 1080, "alto": 1920, "orientacion": "vertical"}
    
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    # Métricas para el sistema evolutivo
    metricas = {
        "total_tomas": 0, 
        "tomadas_video": 0, 
        "duracion_total_tomas": 0, 
        "textos_impacto": 0, 
        "whooshes_colocados": 0,
        "uso_ia": 0
    }

    archivos_escenas_finales = []
    duraciones_escenas_finales = []
    archivo_whoosh = generar_efecto_whoosh(RECURSOS / "whoosh.wav")

    print("============================================================")
    print("FORTALEZA MEDIA AI 13.0 — INICIANDO PRODUCCIÓN TITÁN")
    print(f"Título: {titulo}")
    print(f"Escenas: {len(escenas)}")
    print("============================================================")

    for num_escena, datos_escena in enumerate(escenas):
        print(f"\n[ESCENA {num_escena + 1}/{len(escenas)}]")
        narracion = str(datos_escena["narracion"]).strip()
        titulo_escena = str(datos_escena.get("titulo", titulo))
        
        # 1. Generar Voz
        ruta_voz = RECURSOS / f"voz_{num_escena:02d}.mp3"
        marcas_palabras = await generar_voz_ia(narracion, str(ruta_voz))
        duracion_voz = obtener_duracion(ffmpeg, ruta_voz)
        
        # 2. Calcular Cortes
        cortes = calcular_tiempos_de_corte(marcas_palabras, duracion_voz)
        cantidad_tomas = max(1, len(cortes) - 1)
        
        # 3. Buscar Material Visual
        videos_descargados = buscar_videos_stock(titulo, narracion, num_escena, formato)
        lista_recursos = [v["archivo"] for v in videos_descargados]
        metricas["tomadas_video"] += len(lista_recursos)
        
        if len(lista_recursos) < cantidad_tomas:
            fotos_descargadas = buscar_fotos_wikimedia(titulo, narracion, num_escena)
            lista_recursos.extend([f["archivo"] for f in fotos_descargadas])
            
        if not lista_recursos:
            print("[ALERTA] Sin material de stock. Despertando IA Generativa...")
            prompt_ia = f"Cinematic, highly detailed, dramatic, {narracion[:100]}"
            img_ia = generar_imagen_artificial(prompt_ia, num_escena, formato)
            if img_ia:
                lista_recursos = [img_ia["archivo"]]
                metricas["uso_ia"] += 1
            else:
                # Fondo de respaldo si la IA falla
                ruta_fondo = RECURSOS / f"fondo_respaldo_{num_escena}.jpg"
                Image.new("RGB", (formato["ancho"], formato["alto"]), "#101010").save(ruta_fondo)
                lista_recursos = [str(ruta_fondo)]

        # Asignar recursos a cada toma
        recursos_asignados = ajustar_recursos_a_tomas(lista_recursos, cantidad_tomas)
        
        # 4. Renderizar Tomas Individuales
        lista_tomas_mp4 = []
        for i in range(cantidad_tomas):
            dur_toma = cortes[i + 1] - cortes[i]
            if dur_toma <= 0.4: continue
            
            ruta_toma = RECURSOS / f"toma_{num_escena:02d}_{i:02d}.mp4"
            es_impacto = (i == 0) # Solo la primera toma de la escena tiene efecto glitch
            
            crear_toma_individual(ffmpeg, recursos_asignados[i], ruta_toma, dur_toma, num_escena*10+i, formato, es_impacto)
            lista_tomas_mp4.append(str(ruta_toma))
            
            metricas["total_tomas"] += 1
            metricas["duracion_total_tomas"] += dur_toma
            if i > 0: metricas["whooshes_colocados"] += 1

        # 5. Unir Tomas de la Escena
        ruta_visual = RECURSOS / f"visual_escena_{num_escena:02d}.mp4"
        concatenar_tomas_escena(ffmpeg, lista_tomas_mp4, ruta_visual, RECURSOS / f"lista_tomas_{num_escena:02d}.txt")

        # 6. Generar Gráficos (Subtítulos, Lower Thirds, Impacto)
        # Subtítulos
        subtitulos_img = []
        grupos_palabras, grupo_actual = [], []
        for p in marcas_palabras:
            grupo_actual.append(p)
            if len(grupo_actual) >= 4 or len(" ".join(x["texto"] for x in grupo_actual)) >= 25:
                grupos_palabras.append(grupo_actual)
                grupo_actual = []
        if grupo_actual: grupos_palabras.append(grupo_actual)
        
        for idx_g, grupo in enumerate(grupos_palabras):
            inicio, fin = max(0, grupo[0]["inicio"]), min(duracion_voz, grupo[-1]["fin"] + 0.15)
            if fin <= inicio: continue
            ruta_img_sub = crear_grafico_subtitulo(grupo, num_escena*100 + idx_g, formato)
            subtitulos_img.append({"archivo": ruta_img_sub, "inicio": inicio, "fin": fin})

        # Lower Third
        color_acento = PALETAS[num_escena % len(PALETAS)][2]
        ruta_lt = crear_grafico_lower_third(titulo_escena, formato, color_acento, num_escena)

        # Textos de Impacto
        textos_gigantes = []
        for p in marcas_palabras:
            palabra_limpia = re.sub(r"[^\w]", "", p["texto"].lower())
            if palabra_limpia in PALABRAS_IMPACTO:
                ruta_txt = crear_grafico_texto_gigante(p["texto"], formato)
                textos_gigantes.append({"archivo": ruta_txt, "inicio": p["inicio"], "fin": min(duracion_voz, p["fin"] + 0.4)})
                metricas["textos_impacto"] += 1

        # 7. Componer Escena Final (Video + Audio + Overlays)
        cmd_componer = [ffmpeg, "-y", "-i", str(ruta_visual), "-i", str(ruta_voz)]
        
        for sub in subtitulos_img: cmd_componer.extend(["-loop", "1", "-framerate", str(FPS), "-i", sub["archivo"]])
        cmd_componer.extend(["-loop", "1", "-framerate", str(FPS), "-i", ruta_lt])
        for txt in textos_gigantes: cmd_componer.extend(["-loop", "1", "-framerate", str(FPS), "-i", txt["archivo"]])

        filtros_comp, actual, idx_in = [], "[0:v]", 2
        
        # Overlay Subtítulos
        for sub in subtitulos_img:
            filtros_comp.append(f"{actual}[{idx_in}:v]overlay=0:0:enable='between(t\\,{sub['inicio']:.3f}\\,{sub['fin']:.3f})'[v{idx_in}]")
            actual = f"[v{idx_in}]"; idx_in += 1
            
        # Overlay Lower Third (Animado deslizante)
        filtros_comp.append(f"{actual}[{idx_in}:v]overlay=x='if(lt(t\\,0)\\,-w\\,if(lt(t\\,0.5)\\,-w+t*2*w\\,0))':y=0:enable='between(t\\,0\\,4)'[v_lt]")
        actual = "[v_lt]"; idx_in += 1

        # Overlay Textos Gigantes
        for txt in textos_gigantes:
            filtros_comp.append(f"{actual}[{idx_in}:v]overlay=0:0:enable='between(t\\,{txt['inicio']:.3f}\\,{txt['fin']:.3f})'[v{idx_in}]")
            actual = f"[v{idx_in}]"; idx_in += 1
            
        # Cierre
        if not filtros_comp: 
            filtros_comp = ["[0:v]format=yuv420p[vfinal]"]
        else: 
            filtros_comp.append(f"{actual}format=yuv420p[vfinal]")

        ruta_escena_completa = RECURSOS / f"escena_completa_{num_escena:02d}.mp4"
        cmd_componer.extend([
            "-filter_complex", ";".join(filtros_comp), "-map", "[vfinal]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p", 
            "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-t", f"{duracion_voz:.3f}", str(ruta_escena_completa)
        ])
        ejecutar_ffmpeg(cmd_componer)
        
        archivos_escenas_finales.append(str(ruta_escena_completa))
        duraciones_escenas_finales.append(obtener_duracion(ffmpeg, ruta_escena_completa))
        print(f"[ESCENA] Terminada correctamente.")

    # 8. Unir Todo (XFade)
    print("\n[RENDER] Uniendo todas las escenas con transiciones XFade...")
    video_base_unido = OUTPUT / "video_base_unido.mp4"
    unir_todas_las_escenas_xfade(ffmpeg, archivos_escenas_finales, duraciones_escenas_finales, str(video_base_unido))

    # 9. Mezcla Final (Música, Ducking, Barra de progreso)
    duracion_total_video = obtener_duracion(ffmpeg, video_base_unido)
    pista_musica = generar_musica_ambiente(max(10, int(duracion_total_video) + 5))
    
    # Calcular dónde van los whooshes (cada 2.5 segundos aprox)
    lista_whooshes_finales = [archivo_whoosh for _ in range(int(duracion_total_video // 2.5))]

    destino_final = OUTPUT / "fortaleza_final.mp4"
    mezcla_final_pro(ffmpeg, str(video_base_unido), pista_musica, lista_whooshes_finales, str(destino_final), duracion_total_video)

    # 10. Validar y Copiar Alias
    shutil.copy2(destino_final, OUTPUT / "fortaleza_short.mp4")
    
    # Guardar Reporte
    metricas["promedio_toma"] = metricas["duracion_total_tomas"] / max(1, metricas["total_tomas"])
    metricas["ratio_video"] = metricas["tomadas_video"] / max(1, metricas["total_tomas"])
    metricas["duracion_total_video"] = round(duracion_total_video, 2)
    
    with open(REPORTE_PRODUCCION, "w", encoding="utf-8") as f:
        json.dump(metricas, f, ensure_ascii=False, indent=4)

    # 11. Mutar Cerebro Evolutivo
    evaluar_y_mutar(CONFIG, metricas)

    print("\n============================================================")
    print("PRODUCCIÓN TITÁN COMPLETADA CON ÉXITO")
    print("============================================================")
    return str(destino_final)

if __name__ == "__main__":
    asyncio.run(crear_video())