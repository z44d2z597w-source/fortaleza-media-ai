import os
import re
import json
import math
import random
import asyncio
import subprocess
import hashlib
from pathlib import Path
from urllib.parse import quote

import requests
import edge_tts


# ==========================================
# FORTALEZA MEDIA AI — MOTOR DE RENDERIZADO
# ==========================================

ANCHO = 1080
ALTO = 1920
FPS = 30
DURACION_MAXIMA = 178

CARPETA_SALIDA = Path("output")
CARPETA_TEMP = Path("temp")
HISTORIAL_FONDOS = Path("fondos_usados.json")

PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

VOZ_PRINCIPAL = "es-MX-DaliaNeural"
VOZ_RESPALDO = "es-MX-JorgeNeural"

CARPETA_SALIDA.mkdir(exist_ok=True)
CARPETA_TEMP.mkdir(exist_ok=True)


def ejecutar(comando):
    resultado = subprocess.run(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if resultado.returncode != 0:
        raise RuntimeError(
            "Error al ejecutar FFmpeg:\n" + resultado.stderr[-3000:]
        )

    return resultado


def verificar_ffmpeg():
    for programa in ("ffmpeg", "ffprobe"):
        resultado = subprocess.run(
            [programa, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if resultado.returncode != 0:
            raise RuntimeError(f"No se encontró {programa}.")


def cargar_fondos_usados():
    if not HISTORIAL_FONDOS.exists():
        return []

    try:
        return json.loads(
            HISTORIAL_FONDOS.read_text(encoding="utf-8")
        )
    except Exception:
        return []


def guardar_fondo_usado(identificador):
    usados = cargar_fondos_usados()

    if identificador not in usados:
        usados.append(identificador)

    HISTORIAL_FONDOS.write_text(
        json.dumps(usados[-200:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def limpiar_texto(texto):
    texto = re.sub(r"\s+", " ", str(texto))
    return texto.strip()


def dividir_en_escenas(guion):
    escenas = guion.get("escenas", [])

    if escenas:
        return escenas

    narracion = limpiar_texto(guion.get("narracion", ""))
    partes = re.split(r"(?<=[.!?])\s+", narracion)

    return [
        {
            "texto": parte,
            "visual": "Escena cinematográfica relacionada con la narración",
        }
        for parte in partes
        if parte
    ]


def buscar_video_pixabay(termino, usados):
    if not PIXABAY_API_KEY:
        return None

    url = "https://pixabay.com/api/videos/"

    parametros = {
        "key": PIXABAY_API_KEY,
        "q": termino,
        "per_page": 30,
        "safesearch": "true",
        "order": "popular",
    }

    try:
        respuesta = requests.get(
            url,
            params=parametros,
            timeout=25,
        )
        respuesta.raise_for_status()

        resultados = respuesta.json().get("hits", [])
        random.shuffle(resultados)

        for video in resultados:
            identificador = str(video.get("id", ""))

            if identificador in usados:
                continue

            opciones = video.get("videos", {})

            candidatos = sorted(
                opciones.values(),
                key=lambda x: x.get("width", 0),
                reverse=True,
            )

            for opcion in candidatos:
                enlace = opcion.get("url")

                if enlace:
                    return {
                        "id": identificador,
                        "url": enlace,
                    }

    except Exception as error:
        print(f"[AVISO] Pixabay: {error}")

    return None


def descargar_video(url, destino):
    respuesta = requests.get(
        url,
        stream=True,
        timeout=60,
    )
    respuesta.raise_for_status()

    with open(destino, "wb") as archivo:
        for bloque in respuesta.iter_content(chunk_size=1024 * 1024):
            if bloque:
                archivo.write(bloque)

    if not os.path.exists(destino) or os.path.getsize(destino) < 10000:
        raise RuntimeError("El video descargado está vacío o incompleto.")


def generar_imagen_ia(prompt, destino):
    texto = quote(
        prompt + ", cinematic photography, vertical composition, 9:16",
        safe="",
    )

    semilla = random.randint(1, 999999999)

    url = (
        f"https://image.pollinations.ai/prompt/{texto}"
        f"?width=1080&height=1920&seed={semilla}&nologo=true"
    )

    try:
        respuesta = requests.get(url, timeout=90)
        respuesta.raise_for_status()

        with open(destino, "wb") as archivo:
            archivo.write(respuesta.content)

        if os.path.getsize(destino) < 10000:
            raise RuntimeError("La imagen generada es demasiado pequeña.")

        return True

    except Exception as error:
        print(f"[AVISO] Imagen IA no disponible: {error}")
        return False


def crear_fondo_respaldo(destino):
    ejecutar([
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", f"color=c=0x101827:s={ANCHO}x{ALTO}:d=3",
        "-frames:v", "1",
        str(destino),
    ])


def preparar_video(origen, destino, duracion):
    ejecutar([
        "ffmpeg",
        "-y",
        "-stream_loop", "-1",
        "-i", str(origen),
        "-t", str(duracion),
        "-vf",
        (
            f"scale={ANCHO}:{ALTO}:force_original_aspect_ratio=increase,"
            f"crop={ANCHO}:{ALTO},"
            f"fps={FPS},"
            "setsar=1"
        ),
        "-an",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "24",
        "-pix_fmt", "yuv420p",
        str(destino),
    ])


def preparar_imagen(origen, destino, duracion, indice):
    cuadros = max(1, int(duracion * FPS))
    zoom_maximo = 1.12

    filtro = (
        f"scale={ANCHO}:{ALTO}:force_original_aspect_ratio=increase,"
        f"crop={ANCHO}:{ALTO},"
        f"zoompan=z='min(zoom+0.0005,{zoom_maximo})':"
        "d=1:"
        "x='iw/2-(iw/zoom/2)':"
        "y='ih/2-(ih/zoom/2)':"
        f"s={ANCHO}x{ALTO}:fps={FPS},"
        "setsar=1"
    )

    ejecutar([
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", str(origen),
        "-vf", filtro,
        "-frames:v", str(cuadros),
        "-an",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "24",
        "-pix_fmt", "yuv420p",
        str(destino),
    ])


def crear_escenas(guion, duracion_total):
    escenas = dividir_en_escenas(guion)
    escenas = escenas[:8]

    if not escenas:
        raise RuntimeError("El guion no contiene escenas.")

    duracion_por_escena = duracion_total / len(escenas)
    archivos = []
    usados = cargar_fondos_usados()

    for indice, escena in enumerate(escenas):
        print(f"[ESCENA {indice + 1}/{len(escenas)}] Preparando fondo...")

        visual = limpiar_texto(
            escena.get("visual", "Escena cinematográfica")
        )

        video_encontrado = buscar_video_pixabay(visual, usados)

        archivo_final = CARPETA_TEMP / f"escena_{indice}.mp4"

        if video_encontrado:
            archivo_original = CARPETA_TEMP / f"pixabay_{indice}.mp4"

            try:
                descargar_video(
                    video_encontrado["url"],
                    archivo_original,
                )

                preparar_video(
                    archivo_original,
                    archivo_final,
                    duracion_por_escena,
                )

                guardar_fondo_usado(video_encontrado["id"])
                archivos.append(archivo_final)
                continue

            except Exception as error:
                print(f"[AVISO] Video no utilizable: {error}")

        imagen = CARPETA_TEMP / f"imagen_{indice}.jpg"

        if generar_imagen_ia(visual, imagen):
            preparar_imagen(
                imagen,
                archivo_final,
                duracion_por_escena,
                indice,
            )
            archivos.append(archivo_final)
            continue

        imagen_respaldo = CARPETA_TEMP / f"respaldo_{indice}.mp4"
        crear_fondo_respaldo(imagen_respaldo)
        preparar_video(
            imagen_respaldo,
            archivo_final,
            duracion_por_escena,
        )
        archivos.append(archivo_final)

    return archivos


def unir_escenas(archivos, destino):
    lista = CARPETA_TEMP / "lista_escenas.txt"

    with open(lista, "w", encoding="utf-8") as archivo:
        for elemento in archivos:
            ruta = str(elemento.resolve()).replace("\\", "/")
            ruta = ruta.replace("'", "'\\''")
            archivo.write(f"file '{ruta}'\n")

    ejecutar([
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(lista),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-an",
        str(destino),
    ])


async def generar_audio(texto, destino):
    try:
        comunicacion = edge_tts.Communicate(
            texto,
            VOZ_PRINCIPAL,
            rate="+3%",
            pitch="+0Hz",
        )
        await comunicacion.save(str(destino))

    except Exception as error:
        print(f"[AVISO] Voz principal no disponible: {error}")

        comunicacion = edge_tts.Communicate(
            texto,
            VOZ_RESPALDO,
            rate="+3%",
        )
        await comunicacion.save(str(destino))


def obtener_duracion(archivo):
    resultado = ejecutar([
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(archivo),
    ])

    return float(resultado.stdout.strip())


def escapar_ass(texto):
    texto = limpiar_texto(texto)
    texto = texto.replace("\\", "\\\\")
    texto = texto.replace("{", "\\{").replace("}", "\\}")
    return texto


def crear_subtitulos(guion, duracion_audio, destino):
    palabras = limpiar_texto(guion["narracion"]).split()

    if not palabras:
        raise RuntimeError("La narración está vacía.")

    # Grupos cortos para facilitar la lectura.
    grupos = [
        palabras[i:i + 5]
        for i in range(0, len(palabras), 5)
    ]

    duracion_por_grupo = duracion_audio / len(grupos)

    lineas = [
        "[Script Info]",
        "Title: Fortaleza Media AI",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "WrapStyle: 2",
        "",
        "[V4+ Styles]",
        (
            "Format: Name, Fontname, Fontsize, PrimaryColour, "
            "SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
            "BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding"
        ),
        (
            "Style: Default,Arial,68,&H00FFFFFF,&H000000FF,"
            "&H00000000,&H90000000,-1,0,0,0,100,100,1,0,1,4,2,2,"
            "70,70,430,1"
        ),
        "",
        "[Events]",
        (
            "Format: Layer, Start, End, Style, Name, MarginL, "
            "MarginR, MarginV, Effect, Text"
        ),
    ]

    for indice, grupo in enumerate(grupos):
        inicio = indice * duracion_por_grupo
        final = min(
            duracion_audio,
            (indice + 1) * duracion_por_grupo,
        )

        texto = escapar_ass(" ".join(grupo))

        def tiempo(valor):
            horas = int(valor // 3600)
            minutos = int((valor % 3600) // 60)
            segundos = valor % 60
            return f"{horas}:{minutos:02d}:{segundos:05.2f}"

        lineas.append(
            f"Dialogue: 0,{tiempo(inicio)},{tiempo(final)},"
            f"Default,,0,0,0,,{texto}"
        )

    destino.write_text(
        "\n".join(lineas),
        encoding="utf-8",
    )


def mezclar_video_audio(video, audio, subtitulos, destino):
    filtro = (
        f"ass={str(subtitulos.resolve())}:"
        "fontsdir=/usr/share/fonts/truetype/msttcorefonts,"
        "eq=contrast=1.05:saturation=1.12,"
        "drawbox=x=0:y=0:w=iw:h=12:color=white@0.15:t=fill"
    )

    ejecutar([
        "ffmpeg",
        "-y",
        "-i", str(video),
        "-i", str(audio),
        "-vf", filtro,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "21",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        "-shortest",
        "-movflags", "+faststart",
        str(destino),
    ])


async def renderizar_short(guion=None):
    verificar_ffmpeg()

    if guion is None:
        from video_engine import obtener_guion_hoy
        guion = obtener_guion_hoy()

    narracion = limpiar_texto(guion.get("narracion", ""))

    if not narracion:
        raise RuntimeError("No hay narración para generar el video.")

    identificador = guion.get("id") or hashlib.sha256(
        narracion.encode("utf-8")
    ).hexdigest()[:12]

    print("[AUDIO] Generando narración...")

    audio = CARPETA_TEMP / f"{identificador}.mp3"
    await generar_audio(narracion, audio)

    duracion_audio = obtener_duracion(audio)

    if duracion_audio <= 0:
        raise RuntimeError("La duración del audio no es válida.")

    if duracion_audio > DURACION_MAXIMA:
        raise RuntimeError(
            f"El audio dura {duracion_audio:.1f} segundos. "
            f"Supera el límite de {DURACION_MAXIMA} segundos."
        )

    print(f"[AUDIO] Duración: {duracion_audio:.1f} segundos")
    print("[VIDEO] Creando escenas...")

    escenas = crear_escenas(guion, duracion_audio)

    video_sin_audio = CARPETA_TEMP / f"{identificador}_base.mp4"
    unir_escenas(escenas, video_sin_audio)

    subtitulos = CARPETA_TEMP / f"{identificador}.ass"

    crear_subtitulos(
        guion,
        duracion_audio,
        subtitulos,
    )

    titulo = limpiar_texto(
        guion.get("titulo", "fortaleza_media")
    )

    nombre = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        titulo,
    )[:60]

    salida = CARPETA_SALIDA / f"{nombre}_{identificador}.mp4"

    print("[RENDER] Combinando video, voz y subtítulos...")

    mezclar_video_audio(
        video_sin_audio,
        audio,
        subtitulos,
        salida,
    )

    duracion_final = obtener_duracion(salida)

    if duracion_final > DURACION_MAXIMA:
        salida.unlink(missing_ok=True)
        raise RuntimeError("El video final supera el límite permitido.")

    print("====================================")
    print("[OK] VIDEO TERMINADO")
    print(f"[ARCHIVO] {salida}")
    print(f"[DURACIÓN] {duracion_final:.1f} segundos")
    print("====================================")

    return salida