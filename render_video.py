import asyncio
import json
import math
import os
import random
import re
import shutil
import subprocess
import textwrap
import time
from pathlib import Path
from urllib.parse import quote

import edge_tts
import imageio_ffmpeg
import requests

from PIL import Image, ImageDraw, ImageFont, ImageFilter


# ============================================================
# FORTALEZA MEDIA AI — RENDER ENGINE 4.0
# Shorts verticales + videos horizontales
# Fotos y clips de Wikimedia Commons, voz, subtitulos y musica
# ============================================================

BASE = Path(__file__).resolve().parent
OUTPUT = BASE / "output"
TEMP = OUTPUT / "temp"
GUION_FILE = BASE / "guion.json"

FPS = 30
VOICE = "es-MX-DaliaNeural"
VOICE_RATE = "+5%"
MUSIC_VOLUME = 0.10
MAX_MEDIA_MB = 45
REQUEST_TIMEOUT = 35

ANCHO = 1080
ALTO = 1920

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "FORTALEZA-MEDIA-AI/4.0 (video production)"
})

PALETAS = [
    ("#07111f", "#123c58", "#39c6d8"),
    ("#10101d", "#34214f", "#b18cff"),
    ("#101b16", "#24533b", "#77d69b"),
    ("#1b1110", "#653522", "#ffb36b"),
    ("#101827", "#243b68", "#80aaff"),
]

# ------------------------------------------------------------
# UTILIDADES
# ------------------------------------------------------------

def ejecutar(comando, timeout=900):
    proceso = subprocess.run(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout
    )

    if proceso.returncode != 0:
        error = proceso.stderr[-5000:] if proceso.stderr else "Error FFmpeg"
        raise RuntimeError(error)

    return proceso


def limpiar_texto(texto):
    texto = str(texto or "")
    return re.sub(r"\s+", " ", texto).strip()


def cargar_fuente(tamano, negrita=False):
    candidatos = []

    if negrita:
        candidatos += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
    else:
        candidatos += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]

    for ruta in candidatos:
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, tamano)

    return ImageFont.load_default()


def obtener_dimensiones(formato):
    texto = str(formato or "").lower()

    if "horizontal" in texto or "16:9" in texto:
        return 1920, 1080

    return 1080, 1920


def duracion_media(ruta):
    comando = [
        FFMPEG, "-i", str(ruta),
        "-f", "null", "-"
    ]

    proceso = subprocess.run(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    coincidencia = re.search(
        r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)",
        proceso.stderr
    )

    if not coincidencia:
        return 0

    horas, minutos, segundos = coincidencia.groups()

    return (
        int(horas) * 3600
        + int(minutos) * 60
        + float(segundos)
    )


def escapar_ruta_ffmpeg(ruta):
    return (
        str(Path(ruta).resolve())
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
    )


def descargar_archivo(url, destino, max_mb=MAX_MEDIA_MB):
    respuesta = SESSION.get(
        url,
        timeout=REQUEST_TIMEOUT,
        stream=True
    )
    respuesta.raise_for_status()

    longitud = int(respuesta.headers.get("content-length", 0))

    if longitud and longitud > max_mb * 1024 * 1024:
        raise ValueError("Archivo demasiado grande")

    total = 0

    with open(destino, "wb") as archivo:
        for bloque in respuesta.iter_content(1024 * 128):
            if not bloque:
                continue

            total += len(bloque)

            if total > max_mb * 1024 * 1024:
                raise ValueError("Se superó el límite de descarga")

            archivo.write(bloque)

    if total < 1024:
        raise ValueError("Archivo descargado incompleto")

    return Path(destino)


# ------------------------------------------------------------
# WIKIMEDIA COMMONS: FOTOS, VIDEOS Y LICENCIAS
# ------------------------------------------------------------

def buscar_archivos_commons(consulta, limite=12):
    parametros = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": consulta,
        "gsrnamespace": 6,
        "gsrlimit": limite,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
    }

    respuesta = SESSION.get(
        "https://commons.wikimedia.org/w/api.php",
        params=parametros,
        timeout=REQUEST_TIMEOUT
    )
    respuesta.raise_for_status()

    paginas = respuesta.json().get("query", {}).get("pages", {})

    return list(paginas.values())


def extraer_credito(pagina, url):
    informacion = pagina.get("imageinfo", [{}])[0]
    metadata = informacion.get("extmetadata", {})

    def valor(campo):
        dato = metadata.get(campo, {})
        return limpiar_texto(dato.get("value", ""))

    autor = valor("Artist") or "Autor no especificado"
    licencia = valor("LicenseShortName") or "Consultar licencia"
    licencia_url = valor("LicenseUrl")
    credito = valor("Credit")

    return {
        "archivo": pagina.get("title", ""),
        "autor": autor,
        "licencia": licencia,
        "licencia_url": licencia_url,
        "credito": credito,
        "url": url,
    }


def es_video(url):
    extension = Path(url.split("?")[0]).suffix.lower()
    return extension in (".mp4", ".webm", ".ogv", ".ogg", ".mov")


def buscar_recurso(consulta, permitir_video=True):
    paginas = buscar_archivos_commons(consulta, limite=15)

    videos = []
    imagenes = []

    for pagina in paginas:
        informacion = pagina.get("imageinfo", [{}])[0]
        url = informacion.get("url", "")

        if not url:
            continue

        credito = extraer_credito(pagina, url)

        if es_video(url):
            videos.append((url, credito))
        elif url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            imagenes.append((url, credito))

    if permitir_video and videos:
        random.shuffle(videos)

        for url, credito in videos[:3]:
            try:
                extension = Path(url.split("?")[0]).suffix.lower()
                destino = TEMP / f"clip_{int(time.time() * 1000)}{extension}"
                descargar_archivo(url, destino)
                return destino, credito, "video"
            except Exception:
                continue

    random.shuffle(imagenes)

    for url, credito in imagenes[:5]:
        try:
            destino = TEMP / f"imagen_{int(time.time() * 1000)}.jpg"
            descargar_archivo(url, destino)

            with Image.open(destino) as imagen:
                imagen.verify()

            return destino, credito, "imagen"

        except Exception:
            continue

    return None, None, None


# ------------------------------------------------------------
# IMAGEN DE RESPALDO Y DISEÑO
# ------------------------------------------------------------

def crear_fondo_respaldo(titulo, narracion, destino, ancho, alto):
    color_a, color_b, acento = random.choice(PALETAS)

    imagen = Image.new("RGB", (ancho, alto), color_a)
    pixeles = imagen.load()

    def rgb(hexadecimal):
        hexadecimal = hexadecimal.lstrip("#")
        return tuple(
            int(hexadecimal[i:i + 2], 16)
            for i in (0, 2, 4)
        )

    a = rgb(color_a)
    b = rgb(color_b)

    for y in range(alto):
        proporcion = y / max(1, alto - 1)

        color = tuple(
            int(a[i] * (1 - proporcion) + b[i] * proporcion)
            for i in range(3)
        )

        for x in range(ancho):
            pixeles[x, y] = color

    capa = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(capa)

    tamano = int(min(ancho, alto) * 0.45)

    dibujo.ellipse(
        (
            ancho * 0.45,
            alto * 0.10,
            ancho * 0.45 + tamano,
            alto * 0.10 + tamano
        ),
        fill=(255, 255, 255, 18)
    )

    imagen = Image.alpha_composite(
        imagen.convert("RGBA"),
        capa
    ).convert("RGB")

    fuente_marca = cargar_fuente(max(22, int(ancho * 0.022)), True)
    fuente_titulo = cargar_fuente(max(38, int(ancho * 0.065)), True)
    fuente_cuerpo = cargar_fuente(max(25, int(ancho * 0.027)))

    dibujo = ImageDraw.Draw(imagen)

    margen = int(ancho * 0.075)

    dibujo.text(
        (margen, int(alto * 0.08)),
        "FORTALEZA MEDIA AI",
        font=fuente_marca,
        fill=acento
    )

    titulo = limpiar_texto(titulo)
    lineas = textwrap.wrap(titulo, width=22 if ancho < 1500 else 34)

    y = int(alto * 0.29)

    for linea in lineas[:4]:
        dibujo.text(
            (margen, y),
            linea,
            font=fuente_titulo,
            fill="white",
            stroke_width=2,
            stroke_fill="#101010"
        )
        y += int(fuente_titulo.size * 1.25)

    resumen = limpiar_texto(narracion)[:180]
    resumen_lineas = textwrap.wrap(
        resumen,
        width=38 if ancho < 1500 else 65
    )

    y = min(y + int(alto * 0.07), int(alto * 0.68))

    for linea in resumen_lineas[:4]:
        dibujo.text(
            (margen, y),
            linea,
            font=fuente_cuerpo,
            fill="#e8edf5"
        )
        y += int(fuente_cuerpo.size * 1.5)

    imagen.save(destino, quality=94)
    return Path(destino)


def preparar_imagen(ruta, destino, ancho, alto):
    with Image.open(ruta) as original:
        imagen = original.convert("RGB")

    escala = max(ancho / imagen.width, alto / imagen.height)

    nuevo_ancho = int(imagen.width * escala)
    nuevo_alto = int(imagen.height * escala)

    imagen = imagen.resize(
        (nuevo_ancho, nuevo_alto),
        Image.Resampling.LANCZOS
    )

    izquierda = (nuevo_ancho - ancho) // 2
    arriba = (nuevo_alto - alto) // 2

    imagen = imagen.crop((
        izquierda,
        arriba,
        izquierda + ancho,
        arriba + alto
    ))

    imagen = imagen.filter(ImageFilter.GaussianBlur(radius=0.25))
    imagen.save(destino, quality=94)

    return Path(destino)


def crear_overlay(titulo, numero, total, destino, ancho, alto):
    imagen = Image.new(
        "RGBA",
        (ancho, alto),
        (0, 0, 0, 0)
    )

    dibujo = ImageDraw.Draw(imagen)

    margen = int(ancho * 0.055)
    fuente = cargar_fuente(max(20, int(ancho * 0.022)), True)

    dibujo.rounded_rectangle(
        (
            margen,
            margen,
            margen + int(ancho * 0.39),
            margen + int(alto * 0.045)
        ),
        radius=18,
        fill=(4, 12, 22, 185)
    )

    dibujo.text(
        (margen + 18, margen + 10),
        "FORTALEZA MEDIA AI",
        font=fuente,
        fill=(255, 255, 255, 235)
    )

    texto_contador = f"{numero:02d} / {total:02d}"

    caja = dibujo.textbbox((0, 0), texto_contador, font=fuente)
    ancho_texto = caja[2] - caja[0]

    dibujo.rounded_rectangle(
        (
            ancho - margen - ancho_texto - 35,
            margen,
            ancho - margen,
            margen + int(alto * 0.045)
        ),
        radius=18,
        fill=(4, 12, 22, 185)
    )

    dibujo.text(
        (
            ancho - margen - ancho_texto - 17,
            margen + 10
        ),
        texto_contador,
        font=fuente,
        fill=(255, 255, 255, 235)
    )

    imagen.save(destino)
    return Path(destino)


# ------------------------------------------------------------
# VOZ Y SUBTITULOS SINCRONIZADOS
# ------------------------------------------------------------

def tiempo_srt(segundos):
    milisegundos = int(max(0, segundos) * 1000)

    horas = milisegundos // 3600000
    milisegundos %= 3600000

    minutos = milisegundos // 60000
    milisegundos %= 60000

    segundos_enteros = milisegundos // 1000
    milisegundos %= 1000

    return (
        f"{horas:02}:{minutos:02}:"
        f"{segundos_enteros:02},{milisegundos:03}"
    )


async def generar_voz_y_subtitulos(texto, audio_path, srt_path):
    texto = limpiar_texto(texto)

    if not texto:
        texto = "Acompáñanos a descubrir esta historia."

    comunicacion = edge_tts.Communicate(
        texto,
        VOICE,
        rate=VOICE_RATE
    )

    palabras = []

    with open(audio_path, "wb") as audio:
        async for evento in comunicacion.stream():
            if evento["type"] == "audio":
                audio.write(evento["data"])

            elif evento["type"] == "WordBoundary":
                palabra = limpiar_texto(evento.get("text", ""))

                if palabra:
                    inicio = evento.get("offset", 0) / 10_000_000
                    duracion = evento.get("duration", 0) / 10_000_000

                    palabras.append({
                        "texto": palabra,
                        "inicio": inicio,
                        "fin": inicio + max(duracion, 0.12)
                    })

    if not Path(audio_path).exists() or Path(audio_path).stat().st_size < 1000:
        raise RuntimeError("No se pudo generar la narración")

    bloques = []

    for indice in range(0, len(palabras), 5):
        grupo = palabras[indice:indice + 5]

        if not grupo:
            continue

        inicio = grupo[0]["inicio"]
        fin = max(grupo[-1]["fin"], inicio + 0.35)
        frase = " ".join(p["texto"] for p in grupo)

        bloques.append((inicio, fin, frase))

    with open(srt_path, "w", encoding="utf-8") as archivo:
        for numero, (inicio, fin, frase) in enumerate(bloques, 1):
            archivo.write(
                f"{numero}\n"
                f"{tiempo_srt(inicio)} --> {tiempo_srt(fin)}\n"
                f"{frase}\n\n"
            )

    return Path(audio_path), Path(srt_path)


# ------------------------------------------------------------
# MUSICA AMBIENTAL ORIGINAL
# ------------------------------------------------------------

def crear_musica(destino, duracion):
    import wave
    from array import array

    frecuencia = 44100
    duracion = max(1.0, float(duracion))
    total = int(frecuencia * duracion)

    tonos = [110.0, 164.81, 220.0]
    muestras = array("h")

    bloque = 44100

    for inicio in range(0, total, bloque):
        fin = min(total, inicio + bloque)

        for indice in range(inicio, fin):
            t = indice / frecuencia

            entrada = min(1.0, t / 2.0)
            salida = min(1.0, (duracion - t) / 2.5)
            envolvente = max(0.0, min(entrada, salida))

            valor = sum(
                math.sin(2 * math.pi * tono * t) * peso
                for tono, peso in zip(tonos, (0.40, 0.25, 0.16))
            )

            muestra = int(
                max(-1.0, min(1.0, valor * envolvente * 0.18))
                * 32767
            )

            muestras.append(muestra)
            muestras.append(muestra)

    with wave.open(str(destino), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(frecuencia)
        wav.writeframes(muestras.tobytes())

    return Path(destino)


# ------------------------------------------------------------
# VIDEO POR ESCENA
# ------------------------------------------------------------

def renderizar_escena(
    recurso,
    tipo,
    overlay,
    subtitulos,
    audio,
    destino,
    duracion,
    ancho,
    alto
):
    duracion = max(1.0, duracion)

    filtro_subtitulos = (
        f"subtitles='{escapar_ruta_ffmpeg(subtitulos)}':"
        "force_style='FontName=DejaVu Sans,"
        "FontSize=22,"
        "Bold=1,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00101010,"
        "BorderStyle=1,"
        "Outline=3,"
        "Shadow=1,"
        "Alignment=2,"
        "MarginV=75'"
    )

    overlay_path = escapar_ruta_ffmpeg(overlay)

    if tipo == "video":
        entrada = [
            FFMPEG,
            "-y",
            "-stream_loop", "-1",
            "-i", str(recurso),
            "-i", str(overlay),
        ]

        filtro = (
            f"[0:v]scale={ancho}:{alto}:force_original_aspect_ratio=increase,"
            f"crop={ancho}:{alto},fps={FPS},"
            f"trim=duration={duracion},setpts=PTS-STARTPTS[v0];"
            f"[v0][1:v]overlay=0:0:format=auto,"
            f"{filtro_subtitulos}[v]"
        )

        comando = entrada + [
            "-filter_complex", filtro,
            "-map", "[v]",
            "-an",
            "-t", str(duracion),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "21",
            "-pix_fmt", "yuv420p",
            "-r", str(FPS),
            "-movflags", "+faststart",
            str(destino)
        ]

    else:
        entrada = [
            FFMPEG,
            "-y",
            "-loop", "1",
            "-i", str(recurso),
            "-i", str(overlay),
        ]

        zoom = (
            f"scale={ancho * 2}:{alto * 2},"
            f"zoompan=z='min(zoom+0.0007,1.12)':"
            f"x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':"
            f"d={int(duracion * FPS)}:"
            f"s={ancho}x{alto}:fps={FPS},"
            f"trim=duration={duracion},setpts=PTS-STARTPTS"
        )

        filtro = (
            f"[0:v]{zoom}[fondo];"
            f"[fondo][1:v]overlay=0:0:format=auto,"
            f"{filtro_subtitulos}[v]"
        )

        comando = entrada + [
            "-filter_complex", filtro,
            "-map", "[v]",
            "-an",
            "-t", str(duracion),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "21",
            "-pix_fmt", "yuv420p",
            "-r", str(FPS),
            "-movflags", "+faststart",
            str(destino)
        ]

    ejecutar(comando, timeout=900)

    if not Path(destino).exists() or Path(destino).stat().st_size < 5000:
        raise RuntimeError(f"No se pudo generar la escena: {destino}")

    return Path(destino)


# ------------------------------------------------------------
# ENSAMBLADO FINAL
# ------------------------------------------------------------

def unir_videos(escenas, destino):
    lista = TEMP / "lista_escenas.txt"

    with open(lista, "w", encoding="utf-8") as archivo:
        for escena in escenas:
            ruta = str(Path(escena).resolve())
            ruta = ruta.replace("'", "'\\''")
            archivo.write(f"file '{ruta}'\n")

    ejecutar([
        FFMPEG,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(lista),
        "-an",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "21",
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        "-movflags", "+faststart",
        str(destino)
    ], timeout=1800)

    return Path(destino)


def unir_audios(audios, destino):
    lista = TEMP / "lista_audios.txt"

    with open(lista, "w", encoding="utf-8") as archivo:
        for audio in audios:
            ruta = str(Path(audio).resolve())
            ruta = ruta.replace("'", "'\\''")
            archivo.write(f"file '{ruta}'\n")

    ejecutar([
        FFMPEG,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(lista),
        "-vn",
        "-c:a", "aac",
        "-b:a", "192k",
        str(destino)
    ], timeout=900)

    return Path(destino)


def mezclar_audio(video, voz, musica, destino):
    ejecutar([
        FFMPEG,
        "-y",
        "-i", str(video),
        "-i", str(voz),
        "-i", str(musica),
        "-filter_complex",
        (
            "[1:a]volume=1.0[voz];"
            f"[2:a]volume={MUSIC_VOLUME}[musica];"
            "[voz][musica]amix=inputs=2:"
            "duration=first:dropout_transition=2[audio]"
        ),
        "-map", "0:v:0",
        "-map", "[audio]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(destino)
    ], timeout=1800)

    if not Path(destino).exists() or Path(destino).stat().st_size < 100_000:
        raise RuntimeError("El archivo final no se generó correctamente")

    return Path(destino)


# ------------------------------------------------------------
# CREDITOS
# ------------------------------------------------------------

def guardar_creditos(creditos):
    archivo = OUTPUT / "creditos_imagenes.txt"

    with open(archivo, "w", encoding="utf-8") as salida:
        salida.write("FORTALEZA MEDIA AI — CREDITOS DE MATERIAL\n")
        salida.write("=" * 55 + "\n\n")

        for numero, credito in enumerate(creditos, 1):
            salida.write(f"RECURSO {numero}\n")
            salida.write(f"Archivo: {credito.get('archivo', '')}\n")
            salida.write(f"Autor: {credito.get('autor', '')}\n")
            salida.write(f"Licencia: {credito.get('licencia', '')}\n")
            salida.write(f"Licencia URL: {credito.get('licencia_url', '')}\n")
            salida.write(f"Crédito: {credito.get('credito', '')}\n")
            salida.write(f"Fuente: {credito.get('url', '')}\n\n")

    return archivo


def actualizar_guion_creditos(creditos):
    if not GUION_FILE.exists():
        return

    with open(GUION_FILE, "r", encoding="utf-8") as archivo:
        guion = json.load(archivo)

    guion["creditos_multimedia"] = creditos
    guion["motor_video"] = "FORTALEZA MEDIA AI 4.0"

    with open(GUION_FILE, "w", encoding="utf-8") as archivo:
        json.dump(
            guion,
            archivo,
            ensure_ascii=False,
            indent=2
        )


# ------------------------------------------------------------
# PRODUCCION PRINCIPAL
# ------------------------------------------------------------

async def crear_video():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    if TEMP.exists():
        shutil.rmtree(TEMP)

    TEMP.mkdir(parents=True, exist_ok=True)

    if not GUION_FILE.exists():
        raise FileNotFoundError("No existe guion.json")

    with open(GUION_FILE, "r", encoding="utf-8") as archivo:
        guion = json.load(archivo)

    titulo = limpiar_texto(guion.get("titulo", "Descubre esta historia"))
    formato = guion.get("formato", "YouTube Shorts 9:16")
    escenas = guion.get("escenas", [])

    if not isinstance(escenas, list) or not escenas:
        raise ValueError("El guion no contiene escenas")

    ancho, alto = obtener_dimensiones(formato)

    print(f"FORTALEZA MEDIA AI 4.0")
    print(f"Formato: {formato}")
    print(f"Resolución: {ancho}x{alto}")
    print(f"Escenas: {len(escenas)}")

    videos = []
    audios = []
    creditos = []
    duraciones = []

    total = len(escenas)

    for indice, escena in enumerate(escenas, 1):
        print(f"Procesando escena {indice}/{total}")

        narracion = limpiar_texto(
            escena.get("narracion")
            or escena.get("texto")
            or escena.get("descripcion")
            or ""
        )

        titulo_escena = limpiar_texto(
            escena.get("titulo")
            or titulo
        )

        if not narracion:
            narracion = titulo_escena or titulo

        consulta = limpiar_texto(
            escena.get("busqueda")
            or escena.get("visual")
            or titulo_escena
            or titulo
        )

        audio = TEMP / f"voz_{indice:02d}.mp3"
        srt = TEMP / f"subtitulos_{indice:02d}.srt"

        await generar_voz_y_subtitulos(
            narracion,
            audio,
            srt
        )

        duracion = duracion_media(audio)

        if duracion <= 0:
            raise RuntimeError(
                f"No se pudo determinar la duración de la voz {indice}"
            )

        duracion += 0.45

        recurso, credito, tipo = buscar_recurso(
            consulta,
            permitir_video=True
        )

        if recurso is None or tipo is None:
            recurso = TEMP / f"respaldo_{indice:02d}.jpg"

            crear_fondo_respaldo(
                titulo_escena,
                narracion,
                recurso,
                ancho,
                alto
            )

            tipo = "imagen"

        elif tipo == "imagen":
            preparada = TEMP / f"preparada_{indice:02d}.jpg"

            preparar_imagen(
                recurso,
                preparada,
                ancho,
                alto
            )

            recurso = preparada

        if credito:
            credito["escena"] = indice
            credito["tipo"] = tipo
            creditos.append(credito)

        overlay = TEMP / f"overlay_{indice:02d}.png"

        crear_overlay(
            titulo,
            indice,
            total,
            overlay,
            ancho,
            alto
        )

        video_escena = TEMP / f"escena_{indice:02d}.mp4"

        renderizar_escena(
            recurso,
            tipo,
            overlay,
            srt,
            audio,
            video_escena,
            duracion,
            ancho,
            alto
        )

        videos.append(video_escena)
        audios.append(audio)
        duraciones.append(duracion)

    print("Uniendo escenas...")

    video_sin_audio = TEMP / "video_sin_audio.mp4"
    unir_videos(videos, video_sin_audio)

    print("Uniendo narraciones...")

    voz_completa = TEMP / "voz_completa.m4a"
    unir_audios(audios, voz_completa)

    duracion_total = sum(duraciones)

    musica = TEMP / "musica_ambiente.wav"
    crear_musica(musica, duracion_total + 2)

    print("Mezclando voz y música...")

    destino = OUTPUT / "fortaleza_final.mp4"
    mezclar_audio(
        video_sin_audio,
        voz_completa,
        musica,
        destino
    )

    # Compatibilidad con el workflow anterior.
    alias = OUTPUT / "fortaleza_short.mp4"
    shutil.copy2(destino, alias)

    guardar_creditos(creditos)
    actualizar_guion_creditos(creditos)

    informe = {
        "titulo": titulo,
        "formato": formato,
        "resolucion": f"{ancho}x{alto}",
        "fps": FPS,
        "escenas": total,
        "duracion_segundos": round(duracion_total, 2),
        "archivo": str(destino),
        "tamano_bytes": destino.stat().st_size,
        "creditos_multimedia": len(creditos),
        "motor": "FORTALEZA MEDIA AI 4.0",
        "fecha_produccion": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime()
        )
    }

    with open(
        OUTPUT / "informe_render.json",
        "w",
        encoding="utf-8"
    ) as archivo:
        json.dump(
            informe,
            archivo,
            ensure_ascii=False,
            indent=2
        )

    print("PRODUCCION TERMINADA")
    print(f"Archivo: {destino}")
    print(f"Duración aproximada: {duracion_total:.1f} segundos")

    return str(destino)


if __name__ == "__main__":
    resultado = asyncio.run(crear_video())
    print(resultado)