
import os
import re
import json
import random
import asyncio
import subprocess
import hashlib
from pathlib import Path
from urllib.parse import quote

import requests
import edge_tts


# ==========================================
# FORTALEZA MEDIA AI — MOTOR VISUAL 3.0
# CUATRO ESTILOS VISUALES ROTATIVOS
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

ESTILOS = {
    "minecraft": [
        "minecraft parkour gameplay",
        "minecraft gameplay",
        "block game parkour",
        "pixel game obstacle course",
    ],
    "satisfactorio": [
        "satisfying kinetic sand",
        "satisfying slime",
        "oddly satisfying",
        "satisfying cutting",
        "satisfying process",
    ],
    "roblox": [
        "roblox obby gameplay",
        "obby obstacle course",
        "colorful obstacle course game",
        "platform game gameplay",
    ],
    "cinematico": [
        "cinematic dark atmosphere",
        "abandoned building cinematic",
        "mysterious forest cinematic",
        "dark suspense cinematic",
        "dramatic landscape cinematic",
    ],
}

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
            "Error de FFmpeg:\n" + resultado.stderr[-3000:]
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


def limpiar_texto(texto):
    return re.sub(r"\s+", " ", str(texto)).strip()


def cargar_fondos_usados():
    if not HISTORIAL_FONDOS.exists():
        return []

    try:
        datos = json.loads(
            HISTORIAL_FONDOS.read_text(encoding="utf-8")
        )
        return datos if isinstance(datos, list) else []
    except Exception:
        return []


def guardar_fondo_usado(identificador):
    usados = cargar_fondos_usados()

    if identificador not in usados:
        usados.append(identificador)

    HISTORIAL_FONDOS.write_text(
        json.dumps(usados[-300:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def dividir_en_escenas(guion):
    escenas = guion.get("escenas", [])

    escenas_validas = [
        escena for escena in escenas
        if isinstance(escena, dict)
    ]

    if escenas_validas:
        return escenas_validas[:8]

    narracion = limpiar_texto(
        guion.get("narracion", "")
    )

    partes = re.split(r"(?<=[.!?])\s+", narracion)

    return [
        {
            "texto": parte,
            "visual": parte,
        }
        for parte in partes[:8]
        if parte
    ]


def obtener_estilo(guion):
    estilo = str(
        guion.get("estilo_visual", "cinematico")
    ).lower().strip()

    if estilo not in ESTILOS:
        estilo = "cinematico"

    return estilo


def buscar_videos_pixabay(termino, usados):
    if not PIXABAY_API_KEY:
        raise RuntimeError("Falta PIXABAY_API_KEY.")

    url = "https://pixabay.com/api/videos/"

    parametros = {
        "key": PIXABAY_API_KEY,
        "q": termino,
        "per_page": 50,
        "safesearch": "true",
        "order": "popular",
    }

    respuesta = requests.get(
        url,
        params=parametros,
        timeout=30,
    )

    respuesta.raise_for_status()

    resultados = respuesta.json().get("hits", [])
    random.shuffle(resultados)

    nuevos = []
    repetidos = []

    for video in resultados:
        identificador = str(video.get("id", ""))

        if not identificador:
            continue

        opciones = video.get("videos", {})

        candidatos = sorted(
            opciones.values(),
            key=lambda x: x.get("width", 0),
            reverse=True,
        )

        enlace = None

        for opcion in candidatos:
            if opcion.get("url"):
                enlace = opcion["url"]
                break

        if not enlace:
            continue

        elemento = {
            "id": identificador,
            "url": enlace,
        }

        if identificador in usados:
            repetidos.append(elemento)
        else:
            nuevos.append(elemento)

    return nuevos + repetidos


def seleccionar_clips(estilo, cantidad):
    usados = cargar_fondos_usados()
    terminos = ESTILOS[estilo].copy()
    random.shuffle(terminos)

    encontrados = {}
    repetidos = []

    for termino in terminos:
        print(f"[PIXABAY] Buscando: {termino}")

        try:
            resultados = buscar_videos_pixabay(
                termino,
                usados,
            )

            for video in resultados:
                identificador = video["id"]

                if identificador in encontrados:
                    continue

                if identificador in usados:
                    repetidos.append(video)
                else:
                    encontrados[identificador] = video

            if len(encontrados) >= cantidad:
                break

        except Exception as error:
            print(f"[AVISO] Búsqueda fallida: {error}")

    clips = list(encontrados.values())
    random.shuffle(clips)

    if len(clips) < cantidad:
        disponibles = [
            clip for clip in repetidos
            if clip["id"] not in {
                item["id"] for item in clips
            }
        ]

        random.shuffle(disponibles)
        clips.extend(disponibles)

    if not clips:
        raise RuntimeError(
            f"No se encontraron videos para el estilo {estilo}. "
            "No se utilizará un fondo estático."
        )

    # Se pueden repetir clips solo si el catálogo es insuficiente.
    while len(clips) < cantidad:
        clips.append(random.choice(clips))

    return clips[:cantidad]


def descargar_video(url, destino):
    respuesta = requests.get(
        url,
        stream=True,
        timeout=90,
    )
    respuesta.raise_for_status()

    with open(destino, "wb") as archivo:
        for bloque in respuesta.iter_content(
            chunk_size=1024 * 1024
        ):
            if bloque:
                archivo.write(bloque)

    if (
        not destino.exists()
        or destino.stat().st_size < 10000
    ):
        raise RuntimeError("Video descargado vacío o incompleto.")


def preparar_video(origen, destino, duracion):
    filtro = (
        f"scale={ANCHO}:{ALTO}:force_original_aspect_ratio=increase,"
        f"crop={ANCHO}:{ALTO},"
        f"fps={FPS},"
        "setsar=1,"
        "eq=contrast=1.06:saturation=1.12"
    )

    ejecutar([
        "ffmpeg",
        "-y",
        "-stream_loop", "-1",
        "-i", str(origen),
        "-t", f"{duracion:.3f}",
        "-vf", filtro,
        "-an",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        "-video_track_timescale", "30000",
        str(destino),
    ])


def crear_escenas(guion, duracion_total):
    escenas = dividir_en_escenas(guion)

    if not escenas:
        raise RuntimeError("El guion no contiene escenas.")

    estilo = obtener_estilo(guion)

    print(f"[ESTILO] {estilo.upper()}")

    cantidad = len(escenas)
    clips = seleccionar_clips(estilo, cantidad)

    duracion_por_escena = duracion_total / cantidad
    archivos = []

    for indice, (escena, clip) in enumerate(
        zip(escenas, clips)
    ):
        print(
            f"[FONDO {indice + 1}/{cantidad}] "
            f"Preparando estilo {estilo}..."
        )

        original = (
            CARPETA_TEMP /
            f"clip_{estilo}_{indice}.mp4"
        )

        preparado = (
            CARPETA_TEMP /
            f"escena_{indice}.mp4"
        )

        descargar_video(
            clip["url"],
            original,
        )

        preparar_video(
            original,
            preparado,
            duracion_por_escena,
        )

        guardar_fondo_usado(clip["id"])
        archivos.append(preparado)

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
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
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
        print(f"[AVISO] Voz principal: {error}")

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
    texto = texto.replace("{", "\\{")
    texto = texto.replace("}", "\\}")
    return texto


def crear_subtitulos(guion, duracion_audio, destino):
    palabras = limpiar_texto(
        guion["narracion"]
    ).split()

    if not palabras:
        raise RuntimeError("La narración está vacía.")

    grupos = [
        palabras[i:i + 5]
        for i in range(0, len(palabras), 5)
    ]

    duracion_grupo = duracion_audio / len(grupos)

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

    def tiempo(valor):
        horas = int(valor // 3600)
        minutos = int((valor % 3600) // 60)
        segundos = valor % 60
        return f"{horas}:{minutos:02d}:{segundos:05.2f}"

    for indice, grupo in enumerate(grupos):
        inicio = indice * duracion_grupo
        final = min(
            duracion_audio,
            (indice + 1) * duracion_grupo,
        )

        texto = escapar_ass(" ".join(grupo))

        lineas.append(
            f"Dialogue: 0,{tiempo(inicio)},{tiempo(final)},"
            f"Default,,0,0,0,,{texto}"
        )

    destino.write_text(
        "\n".join(lineas),
        encoding="utf-8",
    )


def mezclar_video_audio(video, audio, subtitulos, destino):
    ruta = str(subtitulos.resolve()).replace("\\", "/")
    ruta = ruta.replace(":", "\\:")
    ruta = ruta.replace("'", "\\'")

    filtro = (
        f"ass='{ruta}',"
        "eq=contrast=1.05:saturation=1.12"
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

    narracion = limpiar_texto(
        guion.get("narracion", "")
    )

    if not narracion:
        raise RuntimeError("No hay narración.")

    identificador = guion.get("id") or hashlib.sha256(
        narracion.encode("utf-8")
    ).hexdigest()[:12]

    estilo = obtener_estilo(guion)

    print("[AUDIO] Generando narración...")

    audio = CARPETA_TEMP / f"{identificador}.mp3"

    await generar_audio(
        narracion,
        audio,
    )

    duracion_audio = obtener_duracion(audio)

    if duracion_audio <= 0:
        raise RuntimeError("Duración de audio inválida.")

    if duracion_audio > DURACION_MAXIMA:
        raise RuntimeError(
            f"El audio dura {duracion_audio:.1f} segundos. "
            f"El máximo es {DURACION_MAXIMA}."
        )

    print(f"[AUDIO] {duracion_audio:.1f} segundos")
    print(f"[VIDEO] Estilo elegido: {estilo}")

    escenas = crear_escenas(
        guion,
        duracion_audio,
    )

    video_base = (
        CARPETA_TEMP /
        f"{identificador}_base.mp4"
    )

    unir_escenas(
        escenas,
        video_base,
    )

    subtitulos = (
        CARPETA_TEMP /
        f"{identificador}.ass"
    )

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

    salida = (
        CARPETA_SALIDA /
        f"{nombre}_{identificador}.mp4"
    )

    print("[RENDER] Combinando voz, fondos y subtítulos...")

    mezclar_video_audio(
        video_base,
        audio,
        subtitulos,
        salida,
    )

    duracion_final = obtener_duracion(salida)

    if duracion_final > DURACION_MAXIMA:
        salida.unlink(missing_ok=True)
        raise RuntimeError("El video supera el límite de duración.")

    print("====================================")
    print("[OK] VIDEO TERMINADO")
    print(f"[ARCHIVO] {salida}")
    print(f"[DURACIÓN] {duracion_final:.1f} segundos")
    print(f"[ESTILO] {estilo}")
    print("====================================")

    return salida
