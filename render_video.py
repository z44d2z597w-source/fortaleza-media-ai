import asyncio
import html
import json
import math
import os
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
# FORTALEZA MEDIA AI 8.0
# MOTOR AUDIOVISUAL — B-ROLL + EDICIÓN REACTIVA A LA VOZ
# ==========================================================

FPS = 30
VOZ = "es-MX-DaliaNeural"
VELOCIDAD_VOZ = "+5%"

OUTPUT = Path("output")
RECURSOS = OUTPUT / "recursos"

MAX_ESCENAS = 20
IMAGENES_POR_ESCENA = 6

CORTE_MIN = 2.2
CORTE_MAX = 5.5
PAUSA_MIN = 0.35

CRF = "22"
XFADE_DURACION = 0.55

CABECERAS = {
    "User-Agent": "FORTALEZA-MEDIA-AI/8.0"
}

PALETAS = [
    ("#071426", "#123D60", "#39B8D8"),
    ("#180D2C", "#43205E", "#B56CFF"),
    ("#111B18", "#245B43", "#65D6A0"),
    ("#29100D", "#74301F", "#FFAD64"),
    ("#10152C", "#293D75", "#82A7FF"),
    ("#25152B", "#63344E", "#FF83AE"),
]

STOPWORDS = {
    "para", "porque", "sobre", "desde", "hasta",
    "donde", "cuando", "también", "tienen", "tiene",
    "puede", "pueden", "entre", "esto", "esta",
    "este", "como", "pero", "algo", "algunos",
    "algunas", "todo", "todos", "cada", "muchas",
    "muchos", "hacia", "después", "durante",
    "ser", "son", "del", "las", "los", "una",
    "uno", "unos", "unas", "con", "sin", "por",
    "que", "sus", "hay", "más", "muy", "hoy",
    "nuestro", "nuestra", "existe", "llamado",
    "llamada", "parte", "conoce", "conocen",
}

# ==========================================================
# CONFIGURACIÓN Y UTILIDADES
# ==========================================================

def preparar_carpetas():
    OUTPUT.mkdir(exist_ok=True)
    RECURSOS.mkdir(exist_ok=True)
    for archivo in RECURSOS.iterdir():
        if archivo.is_file():
            archivo.unlink()


def fuente(tamano, negrita=False):
    rutas = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if negrita else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if negrita else
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for ruta in rutas:
        if os.path.exists(ruta):
            return ImageFont.truetype(ruta, tamano)
    return ImageFont.load_default()


def ejecutar(comando):
    resultado = subprocess.run(
        comando, capture_output=True, text=True,
    )
    if resultado.returncode != 0:
        raise RuntimeError(
            "ERROR FFmpeg:\n" + resultado.stderr[-6000:]
        )


def limpiar_html(texto):
    texto = re.sub(r"<[^>]+>", "", str(texto))
    return html.unescape(texto).strip()


def duracion_media(ffmpeg, archivo):
    resultado = subprocess.run(
        [ffmpeg, "-i", str(archivo)],
        capture_output=True, text=True,
    )
    coincidencia = re.search(
        r"Duration: (\d+):(\d+):(\d+\.\d+)",
        resultado.stderr,
    )
    if not coincidencia:
        raise RuntimeError(
            f"No se pudo determinar la duración de {archivo}"
        )
    horas, minutos, segundos = coincidencia.groups()
    return int(horas) * 3600 + int(minutos) * 60 + float(segundos)


def color_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def dividir_lineas(dibujo, texto, font, ancho):
    lineas = []
    actual = ""
    for palabra in texto.split():
        prueba = (actual + " " + palabra).strip()
        caja = dibujo.textbbox((0, 0), prueba, font=font)
        if caja[2] - caja[0] <= ancho:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas

# ==========================================================
# CÁLCULO DE CORTES BASADOS EN LA VOZ
# ==========================================================

def calcular_cortes(palabras, duracion):
    if duracion <= 0:
        return [0.0, duracion]
    if not palabras:
        n = max(1, int(round(duracion / 4.0)))
        return [i * duracion / n for i in range(n + 1)]

    candidatos = []
    for i in range(1, len(palabras)):
        gap = palabras[i]["inicio"] - palabras[i - 1]["fin"]
        if gap >= PAUSA_MIN:
            candidatos.append(
                (palabras[i - 1]["fin"] + palabras[i]["inicio"]) / 2
            )
    for p in palabras:
        if p["texto"].strip().endswith((".", "?", "!")):
            candidatos.append(p["fin"] + 0.05)

    candidatos = sorted(set(round(c, 3) for c in candidatos))
    cortes = [0.0]
    for c in candidatos:
        if c - cortes[-1] < CORTE_MIN:
            continue
        if duracion - c < CORTE_MIN:
            continue
        cortes.append(c)

    resultado = [0.0]
    for c in cortes[1:]:
        while c - resultado[-1] > CORTE_MAX:
            resultado.append(resultado[-1] + CORTE_MAX)
        resultado.append(c)

    while duracion - resultado[-1] > CORTE_MAX:
        resultado.append(resultado[-1] + CORTE_MAX)

    if resultado[-1] < duracion:
        resultado.append(duracion)
    else:
        resultado[-1] = duracion

    return resultado


def asignar_recursos(recursos, num_tomas):
    if num_tomas <= len(recursos):
        return recursos[:num_tomas]
    return [recursos[i % len(recursos)] for i in range(num_tomas)]

# ==========================================================
# SELECCIÓN DE FORMATO
# ==========================================================

def seleccionar_formato(guion):
    texto = str(guion.get("formato", "")).lower().strip()

    if texto in {"horizontal", "video largo", "16:9", "largo"}:
        return {
            "nombre": "horizontal",
            "ancho": 1920, "alto": 1080,
            "etiqueta": "YOUTUBE VIDEO",
            "orientacion": "horizontal",
        }
    if texto in {"vertical", "short", "shorts", "9:16"}:
        return {
            "nombre": "vertical",
            "ancho": 1080, "alto": 1920,
            "etiqueta": "YOUTUBE SHORTS",
            "orientacion": "vertical",
        }

    duracion = int(guion.get("duracion", 0) or 0)
    escenas = guion.get("escenas", [])
    if duracion >= 180 or len(escenas) >= 8:
        return {
            "nombre": "horizontal",
            "ancho": 1920, "alto": 1080,
            "etiqueta": "YOUTUBE VIDEO",
            "orientacion": "horizontal",
        }
    return {
        "nombre": "vertical",
        "ancho": 1080, "alto": 1920,
        "etiqueta": "YOUTUBE SHORTS",
        "orientacion": "vertical",
    }

# ==========================================================
# BÚSQUEDA DE RECURSOS (VIDEOS + FOTOS)
# ==========================================================

def crear_busqueda(titulo, narracion):
    palabras = re.findall(
        r"[a-zA-ZáéíóúÁÉÍÓÚñÑ]{4,}",
        titulo + " " + narracion,
    )
    resultado = []
    for palabra in palabras:
        if palabra.lower() in STOPWORDS:
            continue
        if palabra.lower() not in [x.lower() for x in resultado]:
            resultado.append(palabra)
    return " ".join(resultado[:4]) # Consulta corta para Pixabay

def buscar_clips(titulo, narracion, numero, formato):
    clave = os.environ.get("PIXABAY_API_KEY")
    if not clave:
        return []

    consulta = crear_busqueda(titulo, narracion)
    print("[VIDEO] Buscando B-roll:", consulta)

    url = "https://pixabay.com/api/videos/"
    parametros = {
        "key": clave,
        "q": consulta,
        "orientation": formato["orientacion"],
        "per_page": 10,
        "safesearch": "true"
    }

    try:
        respuesta = requests.get(url, params=parametros, timeout=20)
        respuesta.raise_for_status()
        hits = respuesta.json().get("hits", [])
    except Exception as e:
        print("[VIDEO] Error Pixabay:", e)
        return []

    resultados = []
    for hit in hits:
        videos = hit.get("videos", {})
        # Buscar la mejor calidad disponible (medium o large)
        mejor = videos.get("large") or videos.get("medium") or videos.get("small")
        if not mejor or "url" not in mejor:
            continue
        
        url_video = mejor["url"]
        ruta = RECURSOS / f"clip_{numero:02d}_{len(resultados):02d}.mp4"
        
        try:
            descarga = requests.get(url_video, stream=True, timeout=30)
            descarga.raise_for_status()
            with open(ruta, "wb") as f:
                for chunk in descarga.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            resultados.append({
                "tipo": "video",
                "archivo": str(ruta),
                "autor": hit.get("user", "Pixabay"),
                "licencia": "Pixabay License",
                "url": hit.get("pageURL", ""),
            })
            print("[VIDEO] Clip descargado:", len(resultados))
            if len(resultados) >= 3: # Máximo 3 clips por escena
                break
        except Exception as e:
            print("[VIDEO] Error descarga:", e)

    return resultados

def buscar_fotografias(titulo, narracion, numero):
    consulta = crear_busqueda(titulo, narracion)
    print("[VISUAL] Buscando fotos:", consulta)

    parametros = {
        "action": "query", "generator": "search",
        "gsrsearch": consulta, "gsrnamespace": 6,
        "gsrlimit": 20, "prop": "imageinfo",
        "iiprop": "url|extmetadata", "iiurlwidth": 1600,
        "format": "json",
    }

    try:
        respuesta = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params=parametros, headers=CABECERAS, timeout=25,
        )
        respuesta.raise_for_status()
        paginas = respuesta.json().get("query", {}).get("pages", {})
    except Exception as error:
        print("[VISUAL] Búsqueda fallida:", error)
        return []

    resultados = []
    for pagina in paginas.values():
        informacion = pagina.get("imageinfo", [])
        if not informacion: continue
        info = informacion[0]
        if not info.get("mime", "").startswith("image/"): continue
        url = info.get("thumburl") or info.get("url")
        
        try:
            descarga = requests.get(url, headers=CABECERAS, timeout=20)
            imagen = Image.open(BytesIO(descarga.content)).convert("RGB")
            if imagen.width < 500 or imagen.height < 350: continue
            
            ruta = RECURSOS / f"foto_{numero:02d}_{len(resultados):02d}.jpg"
            imagen.save(ruta, "JPEG", quality=92)
            
            metadatos = info.get("extmetadata", {})
            resultados.append({
                "tipo": "foto",
                "archivo": str(ruta),
                "autor": limpiar_html(metadatos.get("Artist", {}).get("value", "Desconocido")),
                "licencia": limpiar_html(metadatos.get("LicenseShortName", {}).get("value", "CC")),
                "url": info.get("descriptionurl", url),
            })
            if len(resultados) >= IMAGENES_POR_ESCENA:
                break
        except Exception:
            pass

    return resultados

# ==========================================================
# FONDOS Y FOTOGRAFÍA CINEMATOGRÁFICA
# ==========================================================

def crear_fondo(numero, ancho, alto):
    oscuro, medio, acento = PALETAS[numero % len(PALETAS)]
    gradiente = Image.linear_gradient("L").resize((ancho, alto))
    imagen = ImageOps.colorize(gradiente, black=oscuro, white=medio).convert("RGB")
    dibujo = ImageDraw.Draw(imagen, "RGBA")
    rgb = color_rgb(acento)
    for i in range(10):
        radio = 100 + i * 80
        dibujo.ellipse(
            (int(ancho*0.72)-radio, int(alto*0.2)+i*100-radio,
             int(ancho*0.72)+radio, int(alto*0.2)+i*100+radio),
            outline=(*rgb, max(10, 65 - i * 5)), width=4,
        )
    return imagen

def preparar_fotografia(ruta, ancho, alto):
    imagen = Image.open(ruta).convert("RGB")
    imagen = ImageOps.fit(imagen, (ancho, alto), method=Image.Resampling.LANCZOS)
    imagen = ImageEnhance.Color(imagen).enhance(1.20)
    imagen = ImageEnhance.Contrast(imagen).enhance(1.14)
    imagen = ImageEnhance.Brightness(imagen).enhance(0.85)
    mascara = Image.new("L", (ancho, alto), 0)
    dibujo = ImageDraw.Draw(mascara)
    dibujo.ellipse((-ancho*0.2, -alto*0.2, ancho*1.2, alto*1.2), fill=255)
    mascara = mascara.filter(ImageFilter.GaussianBlur(max(40, int(ancho*0.07))))
    return Image.composite(imagen, Image.new("RGB", (ancho, alto), (0, 0, 0)), mascara)

def crear_escena(titulo, numero, total, fotografia, formato):
    ancho, alto = formato["ancho"], formato["alto"]
    if fotografia and os.path.exists(fotografia):
        imagen = preparar_fotografia(fotografia, ancho, alto)
    else:
        imagen = crear_fondo(numero, ancho, alto)

    dibujo = ImageDraw.Draw(imagen)
    acento = PALETAS[numero % len(PALETAS)][2]
    margen = int(ancho * 0.06)

    dibujo.text((margen, int(alto * 0.055)), "FORTALEZA MEDIA AI",
                font=fuente(int(ancho * 0.025), True), fill="white", stroke_width=2, stroke_fill="#000000")
    dibujo.rounded_rectangle((margen, int(alto*0.105), margen+int(ancho*0.23), int(alto*0.112)), radius=5, fill=acento)
    dibujo.text((ancho - margen, int(alto * 0.055)), f"{numero + 1:02d}/{total:02d}",
                font=fuente(int(ancho * 0.023), True), fill=acento, anchor="ra")

    if numero == 0:
        tamano = int(ancho * 0.068)
        font = fuente(tamano, True)
        lineas = dividir_lineas(dibujo, titulo.upper(), font, int(ancho * 0.86))[:3]
        dibujo.multiline_text((ancho//2, int(alto*0.30)), "\n".join(lineas),
                              font=font, fill="white", anchor="mm", align="center",
                              spacing=int(tamano*0.30), stroke_width=4, stroke_fill="#000000")

    ruta = RECURSOS / f"escena_{numero:02d}.jpg"
    imagen.save(ruta, quality=94)
    return str(ruta)

# ==========================================================
# VOZ IA Y SUBTÍTULOS
# ==========================================================

async def crear_voz(texto, ruta):
    comunicacion = edge_tts.Communicate(texto, voice=VOZ, rate=VELOCIDAD_VOZ, pitch="+0Hz")
    audio, palabras = bytearray(), []
    async for fragmento in comunicacion.stream():
        if fragmento["type"] == "audio":
            audio.extend(fragmento["data"])
        elif fragmento["type"] == "WordBoundary":
            inicio = fragmento["offset"] / 10000000
            duracion = fragmento["duration"] / 10000000
            palabras.append({"texto": fragmento["text"], "inicio": inicio, "fin": inicio + duracion})
    if not audio: raise RuntimeError("Voz sin audio.")
    with open(ruta, "wb") as archivo: archivo.write(audio)
    return palabras

def crear_imagen_subtitulo(palabras, numero, formato, acento):
    ancho, alto = formato["ancho"], formato["alto"]
    imagen = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(imagen)
    frase = " ".join(p["texto"] for p in palabras)
    tamano = int(ancho * 0.044)
    font = fuente(tamano, True)
    lineas = dividir_lineas(dibujo, frase, font, int(ancho * 0.82))[:3]

    alto_linea = int(tamano * 1.45)
    caja_alto = len(lineas) * alto_linea + 65
    centro_y = int(alto * 0.78)
    superior = centro_y - caja_alto // 2
    inferior = centro_y + caja_alto // 2

    dibujo.rounded_rectangle((int(ancho*0.055), superior, int(ancho*0.945), inferior),
                             radius=30, fill=(0,0,0,205), outline=(*color_rgb(acento),245), width=4)
    dibujo.rectangle((int(ancho*0.055)+6, superior+12, int(ancho*0.055)+14, inferior-12),
                     fill=(*color_rgb(acento), 255))

    y = centro_y - (len(lineas) * alto_linea) // 2
    for linea in lineas:
        dibujo.text((ancho//2, y), linea, font=font, fill="white", anchor="mm", stroke_width=3, stroke_fill="#000000")
        y += alto_linea

    ruta = RECURSOS / f"caption_{numero:04d}.png"
    imagen.save(ruta)
    return str(ruta)

def crear_subtitulos(palabras, duracion, numero, formato, acento):
    grupos, grupo = [], []
    for palabra in palabras:
        grupo.append(palabra)
        if len(grupo) >= 5 or len(" ".join(p["texto"] for p in grupo)) >= 32:
            grupos.append(grupo)
            grupo = []
    if grupo: grupos.append(grupo)

    resultado = []
    for indice, grupo in enumerate(grupos):
        inicio = max(0, grupo[0]["inicio"])
        fin = min(duracion, grupo[-1]["fin"] + 0.18)
        if fin <= inicio: continue
        ruta = crear_imagen_subtitulo(grupo, numero * 100 + indice, formato, acento)
        resultado.append({"archivo": ruta, "inicio": inicio, "fin": fin})
    return resultado

# ==========================================================
# RENDERIZADO DE TOMAS (VIDEO Y FOTO)
# ==========================================================

def crear_toma_foto(ffmpeg, imagen, destino, duracion, numero, formato):
    ancho, alto = formato["ancho"], formato["alto"]
    escala_ancho, escala_alto = int(ancho * 1.20), int(alto * 1.20)

    movimientos = [
        ("min(zoom+0.0011,1.25)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
        ("min(zoom+0.0013,1.28)", "iw/2-(iw/zoom/2)+on*0.15", "ih/2-(ih/zoom/2)"),
        ("min(zoom+0.0011,1.22)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)+on*0.12"),
        ("max(zoom-0.0008,1.0)", "iw/2-(iw/zoom/2)-on*0.10", "ih/2-(ih/zoom/2)"),
    ]
    zoom, x, y = movimientos[numero % len(movimientos)]
    
    color = "eq=contrast=1.12:brightness=-0.02:saturation=1.20:gamma=0.98,curves=preset=medium_contrast,unsharp=5:5:0.6:5:5:0.0"
    salida = f"zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s={ancho}x{alto}:fps={FPS},{color},setsar=1,format=yuv420p"
    filtro = f"scale={escala_ancho}:{escala_alto}:force_original_aspect_ratio=increase,crop={escala_ancho}:{escala_alto}," + salida

    ejecutar([
        ffmpeg, "-y", "-loop", "1", "-framerate", str(FPS), "-i", imagen,
        "-vf", filtro, "-t", f"{duracion:.3f}", "-an", "-c:v", "libx264",
        "-preset", "ultrafast", "-crf", CRF, "-pix_fmt", "yuv420p", "-r", str(FPS), str(destino)
    ])

def crear_toma_video(ffmpeg, clip, destino, duracion, numero, formato):
    ancho, alto = formato["ancho"], formato["alto"]
    
    # Etalonaje para video (no zoompan, porque ya hay movimiento)
    color = "eq=contrast=1.10:brightness=-0.02:saturation=1.15:gamma=0.98,curves=preset=medium_contrast,unsharp=5:5:0.5:5:5:0.0"
    filtro = f"scale={ancho}:{alto}:force_original_aspect_ratio=increase,crop={ancho}:{alto},{color},setsar=1,format=yuv420p,fps={FPS}"

    ejecutar([
        ffmpeg, "-y", "-stream_loop", "-1", "-i", clip,
        "-vf", filtro, "-t", f"{duracion:.3f}", "-an", "-c:v", "libx264",
        "-preset", "ultrafast", "-crf", CRF, "-pix_fmt", "yuv420p", "-r", str(FPS), str(destino)
    ])

# ==========================================================
# CONCATENACIÓN Y TRANSICIONES
# ==========================================================

def concatenar_tomas(ffmpeg, archivos, destino, lista):
    with open(lista, "w", encoding="utf-8") as archivo:
        for elemento in archivos:
            archivo.write(f"file '{Path(elemento).resolve()}'\n")
    ejecutar([
        ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", CRF,
        "-pix_fmt", "yuv420p", "-r", str(FPS), "-an", str(destino)
    ])

def unir_escenas_xfade(ffmpeg, archivos, duraciones, destino):
    n = len(archivos)
    if n == 1:
        shutil.copy2(archivos[0], destino)
        return

    overlap = XFADE_DURACION
    transiciones = ["fade", "slideleft", "circleopen", "dissolve", "wipeleft", "fadeblack"]
    filtros, last_v, last_a, offset = [], "[v0]", "[a0]", 0.0
    
    for i in range(n):
        filtros.append(f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS[v{i}]")
        filtros.append(f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]")

    for i in range(1, n):
        offset += duraciones[i - 1] - overlap
        trans = transiciones[(i - 1) % len(transiciones)]
        filtros.append(f"{last_v}[v{i}]xfade=transition={trans}:duration={overlap}:offset={offset:.3f}[vx{i}]")
        filtros.append(f"{last_a}[a{i}]acrossfade=d={overlap}:c1=tri:c2=tri[ax{i}]")
        last_v, last_a = f"[vx{i}]", f"[ax{i}]"

    comando = [ffmpeg, "-y"]
    for archivo in archivos: comando.extend(["-i", archivo])
    comando.extend([
        "-filter_complex", ";".join(filtros), "-map", last_v, "-map", last_a,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", CRF, "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", "-movflags", "+faststart", str(destino)
    ])
    ejecutar(comando)

def unir_escenas(ffmpeg, archivos, duraciones, destino):
    try:
        unir_escenas_xfade(ffmpeg, archivos, duraciones, destino)
    except Exception as e:
        print("[AVISO] xfade falló, usando concat:", e)
        lista = destino.parent / "lista_final.txt"
        concatenar_tomas(ffmpeg, archivos, destino, lista)

# ==========================================================
# MÚSICA Y MEZCLA FINAL
# ==========================================================

def crear_musica(ffmpeg, duracion):
    ruta = RECURSOS / "musica_ambiente.wav"
    frecuencia = 22050
    datos = array("h")
    for i in range(int(frecuencia * duracion)):
        t = i / frecuencia
        modulacion = 0.65 + 0.35 * math.sin(2 * math.pi * 0.035 * t)
        sonido = (math.sin(2*math.pi*110*t)*0.26 + math.sin(2*math.pi*164.81*t)*0.18 +
                  math.sin(2*math.pi*220*t)*0.11 + math.sin(2*math.pi*55*t)*0.10)
        valor = int(32767 * 0.055 * modulacion * sonido)
        datos.append(valor)
        datos.append(valor)
    with wave.open(str(ruta), "wb") as archivo:
        archivo.setnchannels(2); archivo.setsampwidth(2)
        archivo.setframerate(frecuencia); archivo.writeframes(datos.tobytes())
    return str(ruta)

def mezclar_audio_y_efectos(ffmpeg, video, musica, destino):
    filtro = (
        "[0:v]vignette=PI/5,noise=alls=6:allf=t+u,eq=contrast=1.04:saturation=1.10,format=yuv420p[vout];"
        "[1:a]volume=0.12[musica];[0:a]volume=1.0[voz];"
        "[voz][musica]amix=inputs=2:duration=first:dropout_transition=3,alimiter=limit=0.95[audio]"
    )
    ejecutar([
        ffmpeg, "-y", "-i", str(video), "-stream_loop", "-1", "-i", str(musica),
        "-filter_complex", filtro, "-map", "[vout]", "-map", "[audio]",
        "-c:v", "libx264", "-preset", "medium", "-crf", CRF, "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-shortest", "-movflags", "+faststart", str(destino)
    ])

def guardar_creditos(fuentes):
    ruta = OUTPUT / "creditos_imagenes.txt"
    with open(ruta, "w", encoding="utf-8") as archivo:
        archivo.write("FUENTES VISUALES - FORTALEZA MEDIA AI 8.0\n\n")
        for elemento in fuentes:
            archivo.write(f"[{elemento['tipo'].upper()}] Autor: {elemento['autor']}\nLicencia: {elemento['licencia']}\nFuente: {elemento['url']}\n\n")
    return str(ruta)

# ==========================================================
# PRODUCCIÓN PRINCIPAL
# ==========================================================

async def crear_video():
    preparar_carpetas()
    guion_path = Path("guion.json")
    if not guion_path.exists(): raise FileNotFoundError("No se encontró guion.json")

    with open(guion_path, encoding="utf-8") as archivo:
        guion = json.load(archivo)

    titulo = str(guion.get("titulo", "Una historia sorprendente"))
    escenas = [e for e in guion.get("escenas", []) if str(e.get("narracion", "")).strip()][:MAX_ESCENAS]
    if not escenas: raise ValueError("El guion no contiene narraciones.")

    formato = seleccionar_formato(guion)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    print("=" * 60)
    print("FORTALEZA MEDIA AI 8.0 — B-ROLL")
    print("FORMATO:", formato["nombre"])
    print("=" * 60)

    clips, duraciones, fuentes = [], [], []

    for numero, escena in enumerate(escenas):
        narracion = str(escena["narracion"]).strip()
        titulo_escena = str(escena.get("titulo", titulo))
        print(f"\n[ESCENA {numero + 1}/{len(escenas)}]")

        # 1. Buscar voz y calcular cortes (para saber cuántas tomas necesitamos)
        audio = RECURSOS / f"voz_{numero:02d}.mp3"
        palabras = await crear_voz(narracion, str(audio))
        duracion = duracion_media(ffmpeg, audio)
        if duracion <= 0: raise RuntimeError("Duración inválida.")
        
        cortes = calcular_cortes(palabras, duracion)
        num_tomas = max(1, len(cortes) - 1)

        # 2. Buscar recursos (Video y Foto)
        # Primero intentamos conseguir clips de video
        clips_video = buscar_clips(titulo_escena, narracion, numero, formato)
        fuentes.extend(clips_video)
        
        recursos = [c["archivo"] for c in clips_video]

        # Si no hay suficientes videos, rellenamos con fotos
        if len(recursos) < num_tomas:
            fotos_necesarias = num_tomas - len(recursos)
            fotos = buscar_fotografias(titulo_escena, narracion, numero)
            fuentes.extend(fotos)
            recursos.extend([f["archivo"] for f in fotos])

        # Si todo falla, usar fondo de respaldo
        if not recursos:
            respaldo = RECURSOS / f"respaldo_{numero:02d}.jpg"
            crear_fondo(numero, formato["ancho"], formato["alto"]).save(respaldo, quality=92)
            recursos = [str(respaldo)]

        # Portada de la escena en la primera imagen/clip si es la escena 1
        # (En esta versión, para no romper el video, aplicamos el texto sobre una foto en el índice 0)
        if numero == 0:
            # Si el primer recurso es un video, lo reemplazamos por una foto con el título para el inicio
            fotos_portada = buscar_fotografias(titulo_escena, narracion, 99)
            if fotos_portada:
                fuentes.extend(fotos_portada)
                portada = crear_escena(titulo_escena, 0, len(escenas), fotos_portada[0]["archivo"], formato)
                recursos[0] = portada

        recursos_asignados = asignar_recursos(recursos, num_tomas)
        
        print(f"[EDITORIAL] {num_tomas} tomas ({len(clips_video)} clips, {len(recursos)-len(clips_video)} fotos)")

        # 3. Crear tomas
        tomas = []
        for i in range(num_tomas):
            dur_toma = cortes[i + 1] - cortes[i]
            if dur_toma <= 0.4: continue
            
            toma = RECURSOS / f"toma_{numero:02d}_{i:02d}.mp4"
            recurso = recursos_asignados[i]
            
            # Si es video, usar crear_toma_video. Si es foto, crear_toma_foto.
            if recurso.endswith(".mp4"):
                crear_toma_video(ffmpeg, recurso, toma, dur_toma, numero*10+i, formato)
            else:
                crear_toma_foto(ffmpeg, recurso, toma, dur_toma, numero*10+i, formato)
            
            tomas.append(str(toma))

        # 4. Unir tomas de la escena
        visual = RECURSOS / f"visual_{numero:02d}.mp4"
        concatenar_tomas(ffmpeg, tomas, visual, RECURSOS / f"lista_visual_{numero:02d}.txt")

        # 5. Subtítulos
        acento = PALETAS[numero % len(PALETAS)][2]
        subtitulos = crear_subtitulos(palabras, duracion, numero, formato, acento)
        
        comando = [ffmpeg, "-y", "-i", str(visual), "-i", str(audio)]
        for subtitulo in subtitulos:
            comando.extend(["-loop", "1", "-framerate", str(FPS), "-i", subtitulo["archivo"]])

        filtros, actual = [], "[0:v]"
        for indice, subtitulo in enumerate(subtitulos):
            entrada = indice + 2
            salida = f"[v{indice + 1}]"
            filtros.append(
                f"{actual}[{entrada}:v]overlay=0:0:eof_action=pass:"
                f"enable='between(t\\,{subtitulo['inicio']:.3f}\\,{subtitulo['fin']:.3f})'{salida}"
            )
            actual = salida

        filtro_final = ";".join(filtros) if filtros else "[0:v]null[vfinal]"
        actual = actual if filtros else "[vfinal]"

        escena_final = RECURSOS / f"escena_final_{numero:02d}.mp4"
        comando.extend([
            "-filter_complex", filtro_final, "-map", actual, "-map", "1:a",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", CRF, "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
            "-shortest", "-movflags", "+faststart", str(escena_final)
        ])
        ejecutar(comando)
        
        clips.append(str(escena_final))
        duraciones.append(duracion_media(ffmpeg, escena_final))
        print("[ESCENA] Terminada:", round(duraciones[-1], 2), "s")

    # 6. Unir escenas, música y validar
    print("\n[FINAL] Uniendo escenas...")
    video_base = OUTPUT / "video_base.mp4"
    unir_escenas(ffmpeg, clips, duraciones, video_base)

    duracion_total = duracion_media(ffmpeg, video_base)
    print("[AUDIO] Creando música...")
    musica = crear_musica(ffmpeg, max(10, int(duracion_total) + 5))

    destino = OUTPUT / "fortaleza_final.mp4"
    print("[FINAL] Mezclando audio y aplicando efectos...")
    mezclar_audio_y_efectos(ffmpeg, video_base, musica, destino)

    shutil.copy2(destino, OUTPUT / "fortaleza_short.mp4")
    if formato["nombre"] == "horizontal":
        shutil.copy2(destino, OUTPUT / "fortaleza_largo.mp4")

    guardar_creditos(fuentes)

    for archivo in {destino, OUTPUT / "fortaleza_short.mp4"}:
        if not archivo.exists(): raise FileNotFoundError(f"No se generó: {archivo}")
        if archivo.stat().st_size <= 100_000: raise RuntimeError("MP4 vacío.")
        with archivo.open("rb") as f:
            if b"ftyp" not in f.read(16): raise RuntimeError("Cabecera MP4 inválida.")

    estado = {
        "version": "8.0", "titulo": titulo, "formato": formato["nombre"],
        "resolucion": f"{formato['ancho']}x{formato['alto']}", "escenas": len(escenas),
        "fotografias": len(fuentes), "duracion_segundos": round(duracion_total, 2),
        "archivo": str(destino), "tamano_mb": round(destino.stat().st_size / 1048576, 2), "validado": True,
    }

    with open(OUTPUT / "estado_produccion.json", "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=4)

    print("\n" + "=" * 60 + "\nFORTALEZA MEDIA AI 8.0 — TERMINADA\n" + "=" * 60)
    print(json.dumps(estado, ensure_ascii=False, indent=4))
    
    return str(OUTPUT / "fortaleza_final.mp4")

if __name__ == "__main__":
    asyncio.run(crear_video())