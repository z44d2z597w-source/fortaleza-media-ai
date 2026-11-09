import asyncio
import html
import json
import math
import os
import random
import re
import shutil
import subprocess
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
# FORTALEZA MEDIA AI 10.0
# PATTERN INTERRUPTS + LOWER THIRDS + PROGRESS BAR
# ==========================================================

FPS = 30
VOZ = "es-MX-DaliaNeural"
VELOCIDAD_VOZ = "+8%"

OUTPUT = Path("output")
RECURSOS = OUTPUT / "recursos"

MAX_ESCENAS = 20
IMAGENES_POR_ESCENA = 6

CORTE_MIN = 1.8
CORTE_MAX = 4.5
PAUSA_MIN = 0.30

CRF = "22"
XFADE_DURACION = 0.40

# Palabras que activan textos gigantes en pantalla
PALABRAS_IMPACTO = [
    "increíble", "sorprendente", "misterio", "secreto", 
    "peligro", "jamás", "nunca", "impactante", "aterrador", 
    "asombroso", "oculto", "verdad", "ciencia", "descubrimiento"
]

CABECERAS = {"User-Agent": "FORTALEZA-MEDIA-AI/10.0"}
PALETAS = [
    ("#071426", "#123D60", "#39B8D8"), ("#180D2C", "#43205E", "#B56CFF"),
    ("#111B18", "#245B43", "#65D6A0"), ("#29100D", "#74301F", "#FFAD64"),
    ("#10152C", "#293D75", "#82A7FF"), ("#25152B", "#63344E", "#FF83AE"),
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
# UTILIDADES
# ==========================================================

def preparar_carpetas():
    OUTPUT.mkdir(exist_ok=True)
    RECURSOS.mkdir(exist_ok=True)
    for archivo in RECURSOS.iterdir():
        if archivo.is_file(): archivo.unlink()

def fuente(tamano, negrita=False):
    rutas = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if negrita else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if negrita else
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for ruta in rutas:
        if os.path.exists(ruta): return ImageFont.truetype(ruta, tamano)
    return ImageFont.load_default()

def ejecutar(comando):
    resultado = subprocess.run(comando, capture_output=True, text=True)
    if resultado.returncode != 0:
        raise RuntimeError("ERROR FFmpeg:\n" + resultado.stderr[-6000:])

def limpiar_html(texto):
    return html.unescape(re.sub(r"<[^>]+>", "", str(texto))).strip()

def duracion_media(ffmpeg, archivo):
    resultado = subprocess.run([ffmpeg, "-i", str(archivo)], capture_output=True, text=True)
    coincidencia = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", resultado.stderr)
    if not coincidencia: raise RuntimeError(f"Duración desconocida: {archivo}")
    h, m, s = coincidencia.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)

def color_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))

def dividir_lineas(dibujo, texto, font, ancho):
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = (actual + " " + palabra).strip()
        if dibujo.textbbox((0, 0), prueba, font=font)[2] <= ancho:
            actual = prueba
        else:
            if actual: lineas.append(actual)
            actual = palabra
    if actual: lineas.append(actual)
    return lineas

# ==========================================================
# CORTES Y SINCRONIZACIÓN
# ==========================================================

def calcular_cortes(palabras, duracion):
    if duracion <= 0: return [0.0, duracion]
    if not palabras:
        n = max(1, int(round(duracion / 3.0)))
        return [i * duracion / n for i in range(n + 1)]

    candidatos = []
    for i in range(1, len(palabras)):
        gap = palabras[i]["inicio"] - palabras[i - 1]["fin"]
        if gap >= PAUSA_MIN:
            candidatos.append((palabras[i - 1]["fin"] + palabras[i]["inicio"]) / 2)
    for p in palabras:
        if p["texto"].strip().endswith((".", "?", "!")):
            candidatos.append(p["fin"] + 0.05)

    candidatos = sorted(set(round(c, 3) for c in candidatos))
    cortes = [0.0]
    for c in candidatos:
        if c - cortes[-1] < CORTE_MIN or duracion - c < CORTE_MIN: continue
        cortes.append(c)

    resultado = [0.0]
    for c in cortes[1:]:
        while c - resultado[-1] > CORTE_MAX: resultado.append(resultado[-1] + CORTE_MAX)
        resultado.append(c)
    while duracion - resultado[-1] > CORTE_MAX: resultado.append(resultado[-1] + CORTE_MAX)

    if resultado[-1] < duracion: resultado.append(duracion)
    else: resultado[-1] = duracion
    return resultado

def asignar_recursos(recursos, num_tomas):
    if num_tomas <= len(recursos): return recursos[:num_tomas]
    return [recursos[i % len(recursos)] for i in range(num_tomas)]

# ==========================================================
# FORMATO Y BÚSQUEDA (PIXABAY + WIKIMEDIA)
# ==========================================================

def seleccionar_formato(guion):
    texto = str(guion.get("formato", "")).lower().strip()
    if texto in {"horizontal", "video largo", "16:9", "largo"}:
        return {"nombre": "horizontal", "ancho": 1920, "alto": 1080, "orientacion": "horizontal"}
    if texto in {"vertical", "short", "shorts", "9:16"}:
        return {"nombre": "vertical", "ancho": 1080, "alto": 1920, "orientacion": "vertical"}
    
    duracion = int(guion.get("duracion", 0) or 0)
    escenas = guion.get("escenas", [])
    if duracion >= 180 or len(escenas) >= 8:
        return {"nombre": "horizontal", "ancho": 1920, "alto": 1080, "orientacion": "horizontal"}
    return {"nombre": "vertical", "ancho": 1080, "alto": 1920, "orientacion": "vertical"}

def crear_busqueda(titulo, narracion):
    palabras = re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ]{4,}", titulo + " " + narracion)
    resultado = [p for p in palabras if p.lower() not in STOPWORDS]
    return " ".join(list(dict.fromkeys(resultado))[:4])

def buscar_clips(titulo, narracion, numero, formato):
    clave = os.environ.get("PIXABAY_API_KEY")
    if not clave: return []
    consulta = crear_busqueda(titulo, narracion)
    print("[VIDEO] Buscando B-roll:", consulta)
    url = "https://pixabay.com/api/videos/"
    parametros = {"key": clave, "q": consulta, "orientation": formato["orientacion"], "per_page": 10, "safesearch": "true"}

    try:
        respuesta = requests.get(url, params=parametros, timeout=20)
        hits = respuesta.json().get("hits", [])
    except Exception as e:
        print("[VIDEO] Error Pixabay:", e)
        return []

    resultados = []
    for hit in hits:
        videos = hit.get("videos", {})
        mejor = videos.get("large") or videos.get("medium") or videos.get("small")
        if not mejor or "url" not in mejor: continue
        ruta = RECURSOS / f"clip_{numero:02d}_{len(resultados):02d}.mp4"
        try:
            with requests.get(mejor["url"], stream=True, timeout=30) as descarga:
                descarga.raise_for_status()
                with open(ruta, "wb") as f:
                    for chunk in descarga.iter_content(chunk_size=8192): f.write(chunk)
            resultados.append({"tipo": "video", "archivo": str(ruta), "autor": hit.get("user", "Pixabay"), "licencia": "Pixabay License", "url": hit.get("pageURL", "")})
            if len(resultados) >= 3: break
        except Exception: pass
    return resultados

def buscar_fotografias(titulo, narracion, numero):
    consulta = crear_busqueda(titulo, narracion)
    parametros = {"action": "query", "generator": "search", "gsrsearch": consulta, "gsrnamespace": 6, "gsrlimit": 20, "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 1600, "format": "json"}
    try:
        respuesta = requests.get("https://commons.wikimedia.org/w/api.php", params=parametros, headers=CABECERAS, timeout=25)
        paginas = respuesta.json().get("query", {}).get("pages", {})
    except Exception: return []

    resultados = []
    for pagina in paginas.values():
        info = pagina.get("imageinfo", [{}])[0]
        if not info.get("mime", "").startswith("image/"): continue
        url = info.get("thumburl") or info.get("url")
        if not url: continue
        try:
            imagen = Image.open(BytesIO(requests.get(url, headers=CABECERAS, timeout=20).content)).convert("RGB")
            if imagen.width < 500 or imagen.height < 350: continue
            ruta = RECURSOS / f"foto_{numero:02d}_{len(resultados):02d}.jpg"
            imagen.save(ruta, "JPEG", quality=92)
            meta = info.get("extmetadata", {})
            resultados.append({"tipo": "foto", "archivo": str(ruta), "autor": limpiar_html(meta.get("Artist", {}).get("value", "Desconocido")), "licencia": limpiar_html(meta.get("LicenseShortName", {}).get("value", "CC")), "url": info.get("descriptionurl", url)})
            if len(resultados) >= IMAGENES_POR_ESCENA: break
        except Exception: pass
    return resultados

# ==========================================================
# GENERADORES DE IMÁGENES (LOWER THIRD, TEXTOS, FONDOS)
# ==========================================================

def crear_lower_third(titulo, formato, acento, numero):
    ancho, alto = formato["ancho"], formato["alto"]
    imagen = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(imagen)
    
    # Posición: esquina inferior izquierda, encima de los subtítulos
    x = int(ancho * 0.06)
    y = int(alto * 0.68)
    ancho_lt = int(ancho * 0.75)
    alto_lt = int(alto * 0.12)
    
    # Fondo semitransparente con borde de acento
    dibujo.rounded_rectangle(
        (x, y, x + ancho_lt, y + alto_lt),
        radius=15, fill=(0, 0, 0, 190),
        outline=(*color_rgb(acento), 255), width=4
    )
    # Barra lateral de acento
    dibujo.rectangle((x, y, x + 10, y + alto_lt), fill=(*color_rgb(acento), 255))
    
    # Texto
    font = fuente(int(ancho * 0.035), True)
    texto = titulo.upper()
    lineas = dividir_lineas(dibujo, texto, font, ancho_lt - 40)[:2]
    yy = y + (alto_lt - len(lineas) * int(ancho * 0.045)) // 2
    for linea in lineas:
        dibujo.text((x + 35, yy), linea, font=font, fill="white")
        yy += int(ancho * 0.045)
    
    ruta = RECURSOS / f"lower_third_{numero:02d}.png"
    imagen.save(ruta)
    return str(ruta)

def crear_texto_impacto(palabra, formato):
    ancho, alto = formato["ancho"], formato["alto"]
    imagen = Image.new("RGBA", (ancho, alto), (0,0,0,0))
    dibujo = ImageDraw.Draw(imagen)
    tamano = int(ancho * 0.14)
    font = fuente(tamano, True)
    dibujo.text((ancho//2 + 8, alto//2 + 8), palabra.upper(), font=font, fill=(0,0,0,200), anchor="mm")
    dibujo.text((ancho//2, alto//2), palabra.upper(), font=font, fill="white", anchor="mm", stroke_width=6, stroke_fill="#FF0055")
    
    ruta = RECURSOS / f"impacto_{random.randint(1000,9999)}.png"
    imagen.save(ruta)
    return str(ruta)

def crear_escena(titulo, numero, total, fotografia, formato):
    ancho, alto = formato["ancho"], formato["alto"]
    if fotografia and os.path.exists(fotografia):
        imagen = ImageOps.fit(Image.open(fotografia).convert("RGB"), (ancho, alto), method=Image.Resampling.LANCZOS)
        imagen = ImageEnhance.Color(imagen).enhance(1.20)
        imagen = ImageEnhance.Contrast(imagen).enhance(1.14)
        imagen = ImageEnhance.Brightness(imagen).enhance(0.85)
    else:
        oscuro, medio, acento = PALETAS[numero % len(PALETAS)]
        imagen = ImageOps.colorize(Image.linear_gradient("L").resize((ancho, alto)), black=oscuro, white=medio).convert("RGB")

    dibujo = ImageDraw.Draw(imagen)
    margen = int(ancho * 0.06)
    dibujo.text((margen, int(alto * 0.055)), "FORTALEZA MEDIA AI", font=fuente(int(ancho * 0.025), True), fill="white", stroke_width=2, stroke_fill="#000000")
    
    if numero == 0:
        tamano = int(ancho * 0.068)
        font = fuente(tamano, True)
        lineas = dividir_lineas(dibujo, titulo.upper(), font, int(ancho * 0.86))[:3]
        dibujo.multiline_text((ancho//2, int(alto*0.30)), "\n".join(lineas), font=font, fill="white", anchor="mm", align="center", spacing=int(tamano*0.30), stroke_width=4, stroke_fill="#000000")

    ruta = RECURSOS / f"escena_{numero:02d}.jpg"
    imagen.save(ruta, quality=94)
    return str(ruta)

# ==========================================================
# AUDIO (VOZ, MÚSICA, SFX)
# ==========================================================

async def crear_voz(texto, ruta):
    comunicacion = edge_tts.Communicate(texto, voice=VOZ, rate=VELOCIDAD_VOZ, pitch="+0Hz")
    audio, palabras = bytearray(), []
    async for f in comunicacion.stream():
        if f["type"] == "audio": audio.extend(f["data"])
        elif f["type"] == "WordBoundary":
            inicio = f["offset"] / 10000000
            palabras.append({"texto": f["text"], "inicio": inicio, "fin": inicio + (f["duration"] / 10000000)})
    with open(ruta, "wb") as f: f.write(audio)
    return palabras

def crear_whoosh(ffmpeg, ruta):
    frecuencia, duracion = 44100, 0.4
    datos = array("h")
    for i in range(int(frecuencia * duracion)):
        t = i / frecuencia
        vol = (t / duracion) * (1 - t / duracion) * 4
        ruido = random.uniform(-1, 1)
        datos.append(int(32767 * 0.2 * vol * ruido)); datos.append(int(32767 * 0.2 * vol * ruido))
    with wave.open(str(ruta), "wb") as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(frecuencia)
        f.writeframes(datos.tobytes())
    return str(ruta)

def crear_musica(ffmpeg, duracion):
    ruta = RECURSOS / "musica_ambiente.wav"
    frecuencia = 22050
    datos = array("h")
    for i in range(int(frecuencia * duracion)):
        t = i / frecuencia
        modulacion = 0.65 + 0.35 * math.sin(2 * math.pi * 0.035 * t)
        sonido = (math.sin(2*math.pi*110*t)*0.26 + math.sin(2*math.pi*164.81*t)*0.18 + math.sin(2*math.pi*220*t)*0.11 + math.sin(2*math.pi*55*t)*0.10)
        valor = int(32767 * 0.055 * modulacion * sonido)
        datos.append(valor); datos.append(valor)
    with wave.open(str(ruta), "wb") as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(frecuencia)
        f.writeframes(datos.tobytes())
    return str(ruta)

# ==========================================================
# RENDERIZADO DE TOMAS (CON ZOOM PUNCH Y GLITCH)
# ==========================================================

def crear_toma(ffmpeg, recurso, destino, duracion, numero, formato, es_impacto=False):
    ancho, alto = formato["ancho"], formato["alto"]
    es_video = recurso.endswith(".mp4")
    filtros = []

    # 1. Escalado y recorte
    filtros.append(f"scale={int(ancho*1.2)}:{int(alto*1.2)}:force_original_aspect_ratio=increase,crop={int(ancho*1.2)}:{int(alto*1.2)}")

    # 2. Zoom Punch (solo para fotos de impacto)
    if es_impacto and not es_video:
        # Zoom de 1.5x a 1.0x en los primeros 15 frames (0.5s a 30fps)
        filtros.append("zoompan=z='if(lt(on,15),1.5-on/30,1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=" + f"{ancho}x{alto}:fps={FPS}")
    elif not es_video:
        # Zoom lento normal
        filtros.append(f"zoompan=z='min(zoom+0.0015,1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={ancho}x{alto}:fps={FPS}")
    else:
        # Para video, solo escalar al tamaño final
        filtros.append(f"scale={ancho}:{alto}:force_original_aspect_ratio=increase,crop={ancho}:{alto}")

    # 3. Etalonaje cinematográfico
    filtros.append("eq=contrast=1.15:brightness=-0.02:saturation=1.25:gamma=0.98,curves=preset=medium_contrast,unsharp=5:5:0.6:5:5:0.0")

    # 4. Glitch Pattern Interrupt (solo para el clip de impacto)
    if es_impacto:
        filtros.append("rgbashift=rh=8:bh=-8:enable='lt(t,0.3)',chromashift=cbh=5:crh=-5:enable='lt(t,0.3)'")

    # 5. Formato final
    filtros.append("setsar=1,format=yuv420p")

    filtro_str = ",".join(filtros)

    if es_video:
        ejecutar([ffmpeg, "-y", "-stream_loop", "-1", "-i", recurso, "-vf", filtro_str, "-t", f"{duracion:.3f}", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", CRF, "-pix_fmt", "yuv420p", "-r", str(FPS), str(destino)])
    else:
        ejecutar([ffmpeg, "-y", "-loop", "1", "-framerate", str(FPS), "-i", recurso, "-vf", filtro_str, "-t", f"{duracion:.3f}", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", CRF, "-pix_fmt", "yuv420p", "-r", str(FPS), str(destino)])

# ==========================================================
# CONCATENACIÓN Y MEZCLA FINAL
# ==========================================================

def concatenar_tomas(ffmpeg, archivos, destino, lista):
    with open(lista, "w", encoding="utf-8") as f:
        for a in archivos: f.write(f"file '{Path(a).resolve()}'\n")
    ejecutar([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(lista), "-c:v", "libx264", "-preset", "ultrafast", "-crf", CRF, "-pix_fmt", "yuv420p", "-r", str(FPS), "-an", str(destino)])

def unir_escenas_xfade(ffmpeg, archivos, duraciones, destino):
    n = len(archivos)
    if n == 1: shutil.copy2(archivos[0], destino); return
    filtros, last_v, last_a, offset = [], "[v0]", "[a0]", 0.0
    for i in range(n):
        filtros.extend([f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS[v{i}]", f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]"])
    for i in range(1, n):
        offset += duraciones[i - 1] - XFADE_DURACION
        filtros.extend([f"{last_v}[v{i}]xfade=transition='smoothleft':duration={XFADE_DURACION}:offset={offset:.3f}[vx{i}]", f"{last_a}[a{i}]acrossfade=d={XFADE_DURACION}:c1=tri:c2=tri[ax{i}]"])
        last_v, last_a = f"[vx{i}]", f"[ax{i}]"
    cmd = [ffmpeg, "-y"] + sum([["-i", a] for a in archivos], []) + ["-filter_complex", ";".join(filtros), "-map", last_v, "-map", last_a, "-c:v", "libx264", "-preset", "veryfast", "-crf", CRF, "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", str(destino)]
    ejecutar(cmd)

def mezclar_audio_y_barra(ffmpeg, video, musica, lista_whoosh, destino, duracion_total):
    # Construir filtro de audio
    filtro_audio = "[1:a]volume=0.10[musica];[0:a]volume=1.0[voz];[voz][musica]amix=inputs=2:duration=first[base];"
    for i in range(len(lista_whoosh)):
        filtro_audio += f"[{i+2}:a]volume=0.5[w{i}];[base][w{i}]amix=inputs=2:duration=first[base];"
    filtro_audio += "[base]alimiter=limit=0.95[audio]"

    # Construir filtro de video (barra de progreso)
    filtro_video = f"[0:v]vignette=PI/5,noise=alls=5:allf=t+u,eq=contrast=1.05:saturation=1.15,drawbox=x=0:y=h-8:w='iw*t/{duracion_total}':h=8:color=white@0.6:t=fill,format=yuv420p[vout]"

    filtro_total = filtro_video + ";" + filtro_audio

    cmd = [ffmpeg, "-y", "-i", video, "-stream_loop", "-1", "-i", musica]
    for w in lista_whoosh: cmd.extend(["-i", w])
    cmd.extend(["-filter_complex", filtro_total, "-map", "[vout]", "-map", "[audio]", "-c:v", "libx264", "-preset", "medium", "-crf", CRF, "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", destino])
    ejecutar(cmd)

# ==========================================================
# PRODUCCIÓN PRINCIPAL
# ==========================================================

async def crear_video():
    preparar_carpetas()
    with open("guion.json", encoding="utf-8") as f: guion = json.load(f)

    titulo = str(guion.get("titulo", "Historia"))
    escenas = [e for e in guion.get("escenas", []) if str(e.get("narracion", "")).strip()][:MAX_ESCENAS]
    formato = seleccionar_formato(guion)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    clips, duraciones, whooshes = [], [], []
    whoosh_base = crear_whoosh(ffmpeg, RECURSOS / "whoosh.wav")

    print("=" * 60 + f"\nFORTALEZA MEDIA AI 10.0 — PATTERN INTERRUPTS\nFORMATO: {formato['nombre']}\n" + "=" * 60)

    for numero, escena in enumerate(escenas):
        narracion = str(escena["narracion"]).strip()
        print(f"\n[ESCENA {numero + 1}/{len(escenas)}]")

        audio = RECURSOS / f"voz_{numero:02d}.mp3"
        palabras = await crear_voz(narracion, str(audio))
        duracion = duracion_media(ffmpeg, audio)
        
        cortes = calcular_cortes(palabras, duracion)
        num_tomas = max(1, len(cortes) - 1)

        # 1. Material
        clips_v = buscar_clips(titulo, narracion, numero, formato)
        recursos = [c["archivo"] for c in clips_v]
        if len(recursos) < num_tomas:
            recursos.extend([f["archivo"] for f in buscar_fotografias(titulo, narracion, numero)])
        
        if not recursos:
            img = RECURSOS / f"fondo_{numero:02d}.jpg"
            Image.new("RGB", (formato["ancho"], formato["alto"]), "#000000").save(img)
            recursos = [str(img)]

        recursos_asignados = asignar_recursos(recursos, num_tomas)
        
        # 2. Tomas (la primera con zoom punch y glitch)
        tomas = []
        for i in range(num_tomas):
            dur = cortes[i + 1] - cortes[i]
            if dur <= 0.4: continue
            toma = RECURSOS / f"toma_{numero:02d}_{i:02d}.mp4"
            crear_toma(ffmpeg, recursos_asignados[i], toma, dur, numero*10+i, formato, es_impacto=(i==0))
            tomas.append(str(toma))
            if i > 0: whooshes.append((whoosh_base, 0)) # Placeholder, se calcula después

        visual = RECURSOS / f"visual_{numero:02d}.mp4"
        concatenar_tomas(ffmpeg, tomas, visual, RECURSOS / f"lista_{numero:02d}.txt")

        # 3. Subtítulos y lower third
        # (Para simplificar, mantenemos los subtítulos de la 9.0)
        subtitulos = []
        grupos, grupo = [], []
        for p in palabras:
            grupo.append(p)
            if len(grupo) >= 4 or len(" ".join(x["texto"] for x in grupo)) >= 25:
                grupos.append(grupo); grupo = []
        if grupo: grupos.append(grupo)
        
        for i, g in enumerate(grupos):
            inicio, fin = max(0, g[0]["inicio"]), min(duracion, g[-1]["fin"] + 0.15)
            if fin <= inicio: continue
            ancho, alto = formato["ancho"], formato["alto"]
            imagen = Image.new("RGBA", (ancho, alto), (0,0,0,0))
            dibujo = ImageDraw.Draw(imagen)
            font = fuente(int(ancho * 0.045), True)
            lineas = dividir_lineas(dibujo, " ".join(x["texto"] for x in g), font, int(ancho*0.82))[:2]
            y = int(alto * 0.82) - (len(lineas) * 60) // 2
            for linea in lineas:
                dibujo.text((ancho//2, y), linea, font=font, fill="white", anchor="mm", stroke_width=4, stroke_fill="#000000")
                y += 70
            ruta = RECURSOS / f"sub_{numero:02d}_{i:04d}.png"
            imagen.save(ruta)
            subtitulos.append({"archivo": str(ruta), "inicio": inicio, "fin": fin})

        # Lower third
        acento = PALETAS[numero % len(PALETAS)][2]
        lt_path = crear_lower_third(str(escena.get("titulo", titulo)), formato, acento, numero)

        # 4. Componer escena (Visual + Subtítulos + Lower Third + Textos Gigantes)
        overlays_texto = []
        for p in palabras:
            palabra_limpia = re.sub(r"[^\w]", "", p["texto"].lower())
            if palabra_limpia in PALABRAS_IMPACTO:
                img_txt = crear_texto_impacto(p["texto"], formato)
                overlays_texto.append({"archivo": img_txt, "inicio": p["inicio"], "fin": min(duracion, p["fin"] + 0.4)})

        cmd = [ffmpeg, "-y", "-i", str(visual), "-i", str(audio)]
        for sub in subtitulos: cmd.extend(["-loop", "1", "-i", sub["archivo"]])
        cmd.extend(["-loop", "1", "-i", lt_path])
        for txt in overlays_texto: cmd.extend(["-loop", "1", "-i", txt["archivo"]])

        filtros, actual = [], "[0:v]"
        idx_entrada = 2
        for sub in subtitulos:
            filtros.append(f"{actual}[{idx_entrada}:v]overlay=0:0:enable='between(t,{sub['inicio']:.3f},{sub['fin']:.3f})'[v{idx_entrada}]")
            actual = f"[v{idx_entrada}]"; idx_entrada += 1
        
        # Lower Third animado (deslizar desde la izquierda en 0.5s)
        lt_idx = idx_entrada
        filtros.append(f"{actual}[{lt_idx}:v]overlay=x='if(lt(t,0),-w,if(lt(t,0.5),-w+t*2*w,0))':y=0:enable='between(t,0,4)'[v_lt]")
        actual = "[v_lt]"; idx_entrada += 1

        for txt in overlays_texto:
            filtros.append(f"{actual}[{idx_entrada}:v]overlay=0:0:enable='between(t,{txt['inicio']:.3f},{txt['fin']:.3f})'[v{idx_entrada}]")
            actual = f"[v{idx_entrada}]"; idx_entrada += 1
        
        if not filtros: filtros = ["[0:v]null[vfinal]"]; actual = "[vfinal]"
        else: 
            # La última salida se renombra a vfinal
            filtros[-1] = filtros[-1].replace(f"[v{idx_entrada-1}]", "[vfinal]")
            actual = "[vfinal]"

        escena_final = RECURSOS / f"escena_final_{numero:02d}.mp4"
        cmd.extend(["-filter_complex", ";".join(filtros), "-map", actual, "-map", "1:a", "-c:v", "libx264", "-preset", "ultrafast", "-crf", CRF, "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2", "-shortest", str(escena_final)])
        ejecutar(cmd)
        
        clips.append(str(escena_final))
        duraciones.append(duracion_media(ffmpeg, escena_final))
        print(f"[ESCENA] Terminada: {duraciones[-1]:.2f}s")

    # Unir todo
    print("\n[FINAL] Uniendo escenas...")
    video_base = OUTPUT / "video_base.mp4"
    if len(clips) > 1: unir_escenas_xfade(ffmpeg, clips, duraciones, video_base)
    else: shutil.copy2(clips[0], video_base)

    duracion_total = duracion_media(ffmpeg, video_base)
    musica = crear_musica(ffmpeg, max(10, int(duracion_total) + 5))

    # Whooshes rítmicos cada 2.5s (aproximación)
    lista_whooshes_abs = []
    t = 1.5
    while t < duracion_total - 1:
        lista_whooshes_abs.append(whoosh_base)
        t += 2.5

    destino = OUTPUT / "fortaleza_final.mp4"
    print("[FINAL] Aplicando barra de progreso y diseño de sonido...")
    mezclar_audio_y_barra(ffmpeg, str(video_base), musica, lista_whooshes_abs, str(destino), duracion_total)

    shutil.copy2(destino, OUTPUT / "fortaleza_short.mp4")
    if formato["nombre"] == "horizontal": shutil.copy2(destino, OUTPUT / "fortaleza_largo.mp4")

    print("\n" + "=" * 60 + "\nPRODUCCIÓN TERMINADA\n" + "=" * 60)
    return str(destino)

if __name__ == "__main__":
    asyncio.run(crear_video())