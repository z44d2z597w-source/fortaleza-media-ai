
import os
import re
import json
import random
import asyncio
import subprocess
import hashlib
import time
from pathlib import Path

import requests
import edge_tts


# ==========================================
# FORTALEZA MEDIA AI - MOTOR VISUAL 5.0
# DRAMA Y AVENTURAS
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

BUSQUEDAS_CATEGORIA = {
    "drama": [
        "emotional cinematic family",
        "friends emotional conversation",
        "dramatic cinematic storytelling",
        "person looking through old photographs",
        "emotional reunion cinematic",
        "cinematic sunset silhouette",
    ],
    "aventura": [
        "cute cartoon animals adventure",
        "colorful fantasy animated world",
        "magical forest fantasy",
        "cute animals exploring nature",
        "cartoon fantasy adventure",
        "magical glowing portal fantasy",
        "funny cute animal friends",
    ],
}

CARPETA_SALIDA.mkdir(exist_ok=True)
CARPETA_TEMP.mkdir(exist_ok=True)


# ==========================================
# HERRAMIENTAS
# ==========================================

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
            raise RuntimeError(
                f"No se encontró {programa}."
            )


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
        json.dumps(
            usados[-300:],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# ==========================================
# CATEGORÍA
# ==========================================

def obtener_categoria(guion):
    categoria = str(
        guion.get("categoria", "drama")
    ).lower().strip()

    if categoria not in BUSQUEDAS_CATEGORIA:
        categoria = "drama"

    return categoria


def obtener_nombre_categoria(categoria):
    nombres = {
        "drama": "DRAMA EMOCIONAL",
        "aventura": "AVENTURA INFANTIL",
    }

    return nombres.get(categoria, "DRAMA EMOCIONAL")


# ==========================================
# ESCENAS
# ==========================================

def dividir_en_escenas(guion):
    escenas = guion.get("escenas", [])

    validas = [
        escena for escena in escenas
        if isinstance(escena, dict)
        and escena.get("visual")
    ]

    if validas:
        return validas[:8]

    raise RuntimeError(
        "El guion no contiene escenas visuales válidas."
    )


def crear_consulta_visual(escena):
    visual = limpiar_texto(
        escena.get("visual", "")
    )

    consulta = re.sub(
        r"[^a-zA-Z0-9 ]",
        " ",
        visual,
    )

    consulta = limpiar_texto(consulta)

    palabras = consulta.split()

    consulta = " ".join(palabras[:9])

    if not consulta:
        raise RuntimeError(
            "La escena no contiene una descripción visual buscable."
        )

    return consulta


# ==========================================
# PIXABAY
# ==========================================

def buscar_videos_pixabay(termino, usados):
    if not PIXABAY_API_KEY:
        raise RuntimeError(
            "Falta configurar PIXABAY_API_KEY."
        )

    respuesta = requests.get(
        "https://pixabay.com/api/videos/",
        params={
            "key": PIXABAY_API_KEY,
            "q": termino,
            "per_page": 30,
            "safesearch": "true",
            "order": "popular",
        },
        timeout=30,
    )

    respuesta.raise_for_status()

    resultados = respuesta.json().get("hits", [])

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

    random.shuffle(nuevos)
    random.shuffle(repetidos)

    return nuevos + repetidos


def buscar_candidatos_escena(escena, categoria):
    usados = cargar_fondos_usados()

    consulta_visual = crear_consulta_visual(escena)

    consultas = [
        consulta_visual,
        *BUSQUEDAS_CATEGORIA[categoria],
    ]

    candidatos = {}

    print(f"[CATEGORÍA] {obtener_nombre_categoria(categoria)}")
    print(f"[ESCENA] {escena.get('texto', '')[:100]}")

    for termino in consultas:
        if len(candidatos) >= 10:
            break

        print(f"[PIXABAY] Buscando: {termino}")

        try:
            resultados = buscar_videos_pixabay(
                termino,
                usados,
            )

            for video in resultados:
                candidatos[video["id"]] = video

                if len(candidatos) >= 10:
                    break

        except Exception as error:
            print(
                f"[AVISO] Falló la búsqueda '{termino}': {error}"
            )

        time.sleep(1)

    clips = list(candidatos.values())

    if not clips:
        raise RuntimeError(
            f"No se encontraron fondos para la escena: {consulta_visual}"
        )

    print(
        f"[PIXABAY] {len(clips)} candidatos encontrados."
    )

    return clips


# ==========================================
# DESCARGAR VIDEOS CON REINTENTOS
# ==========================================

def descargar_video(url, destino):
    temporal = destino.with_suffix(
        destino.suffix + ".part"
    )

    ultimo_error = None

    for intento in range(1, 5):
        espera = min(8 * intento, 30)

        try:
            print(
                f"[DESCARGA] Intento {intento}/4: {destino.name}"
            )

            with requests.get(
                url,
                stream=True,
                timeout=(20, 120),
                headers={
                    "User-Agent": "Mozilla/5.0"
                },
            ) as respuesta:

                if respuesta.status_code == 429:
                    retry_after = respuesta.headers.get(
                        "Retry-After"
                    )

                    try:
                        espera = min(
                            max(int(retry_after), 1),
                            60,
                        )
                    except (TypeError, ValueError):
                        espera = min(10 * intento, 45)

                    raise requests.exceptions.HTTPError(
                        "Pixabay limitó temporalmente la descarga.",
                        response=respuesta,
                    )

                respuesta.raise_for_status()

                with open(temporal, "wb") as archivo:
                    for bloque in respuesta.iter_content(
                        chunk_size=512 * 1024
                    ):
                        if bloque:
                            archivo.write(bloque)

            if (
                not temporal.exists()
                or temporal.stat().st_size < 10000
            ):
                raise RuntimeError(
                    "Video vacío o incompleto."
                )

            temporal.replace(destino)

            print(
                f"[DESCARGA OK] "
                f"{destino.stat().st_size / 1024 / 1024:.2f} MB"
            )

            return

        except Exception as error:
            ultimo_error = error
            temporal.unlink(missing_ok=True)

            if intento < 4:
                print(
                    f"[AVISO] {error}. "
                    f"Reintentando en {espera} segundos."
                )

                time.sleep(espera)

    raise RuntimeError(
        f"No se pudo descargar el video: {ultimo_error}"
    )


# ==========================================
# PREPARAR VIDEO VERTICAL
# ==========================================

def preparar_video(origen, destino, duracion):
    filtro = (
        f"scale={ANCHO}:{ALTO}:"
        "force_original_aspect_ratio=increase,"
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


# ==========================================
# CREAR FONDOS PARA CADA ESCENA
# ==========================================

def crear_escenas(guion, duracion_total):
    escenas = dividir_en_escenas(guion)

    categoria = obtener_categoria(guion)

    cantidad = len(escenas)
    duracion_por_escena = duracion_total / cantidad

    archivos = []

    print("==========================================")
    print("[MOTOR VISUAL 5.0]")
    print(f"[CATEGORÍA] {obtener_nombre_categoria(categoria)}")
    print(f"[ESCENAS] {cantidad}")
    print("==========================================")

    for indice, escena in enumerate(escenas):
        print(
            f"\n[FONDO {indice + 1}/{cantidad}]"
        )

        candidatos = buscar_candidatos_escena(
            escena,
            categoria,
        )

        preparado = (
            CARPETA_TEMP /
            f"escena_{indice}.mp4"
        )

        fondo_creado = False

        for numero, clip in enumerate(candidatos, start=1):
            original = (
                CARPETA_TEMP /
                f"clip_{indice}_{numero}.mp4"
            )

            try:
                descargar_video(
                    clip["url"],
                    original,
                )

                preparar_video(
                    original,
                    preparado,
                    duracion_por_escena,
                )

                if (
                    not preparado.exists()
                    or preparado.stat().st_size < 10000
                ):
                    raise RuntimeError(
                        "El fondo procesado está vacío."
                    )

                guardar_fondo_usado(clip["id"])

                archivos.append(preparado)
                fondo_creado = True

                print(
                    f"[FONDO OK] Escena {indice + 1}: "
                    f"video {clip['id']}"
                )

                break

            except Exception as error:
                print(
                    f"[AVISO] Clip descartado: {error}"
                )

                original.unlink(missing_ok=True)
                preparado.unlink(missing_ok=True)

        if not fondo_creado:
            raise RuntimeError(
                f"No se pudo obtener un fondo para la escena "
                f"{indice + 1}. Se cancela el video para evitar "
                "fondos negros o escenas incorrectas."
            )

    return archivos


# ==========================================
# UNIR ESCENAS
# ==========================================

def unir_escenas(archivos, destino):
    lista = CARPETA_TEMP / "lista_escenas.txt"

    with open(lista, "w", encoding="utf-8") as archivo:
        for elemento in archivos:
            ruta = str(
                elemento.resolve()
            ).replace("\\", "/")

            ruta = ruta.replace("'", "'\\''")

            archivo.write(
                f"file '{ruta}'\n"
            )

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


# ==========================================
# GENERAR AUDIO
# ==========================================

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


# ==========================================
# DURACIÓN
# ==========================================

def obtener_duracion(archivo):
    resultado = ejecutar([
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(archivo),
    ])

    return float(resultado.stdout.strip())


# ==========================================
# SUBTÍTULOS
# ==========================================

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
        raise RuntimeError(
            "La narración está vacía."
        )

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

        return (
            f"{horas}:{minutos:02d}:{segundos:05.2f}"
        )

    for indice, grupo in enumerate(grupos):
        inicio = indice * duracion_grupo

        final = min(
            duracion_audio,
            (indice + 1) * duracion_grupo,
        )

        texto = escapar_ass(" ".join(grupo))

        lineas.append(
            f"Dialogue: 0,{tiempo(inicio)},"
            f"{tiempo(final)},Default,,0,0,0,,{texto}"
        )

    destino.write_text(
        "\n".join(lineas),
        encoding="utf-8",
    )


# ==========================================
# MEZCLAR VIDEO Y AUDIO
# ==========================================

def mezclar_video_audio(video, audio, subtitulos, destino):
    ruta = str(
        subtitulos.resolve()
    ).replace("\\", "/")

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


# ==========================================
# GENERADOR PRINCIPAL
# ==========================================

async def renderizar_short(guion=None):
    verificar_ffmpeg()

    if guion is None:
        from video_engine import obtener_guion_hoy
        guion = obtener_guion_hoy()

    narracion = limpiar_texto(
        guion.get("narracion", "")
    )

    if not narracion:
        raise RuntimeError(
            "No hay narración."
        )

    identificador = guion.get("id") or hashlib.sha256(
        narracion.encode("utf-8")
    ).hexdigest()[:12]

    categoria = obtener_categoria(guion)

    print("==========================================")
    print("[FORTALEZA MEDIA AI]")
    print(f"[CATEGORÍA] {obtener_nombre_categoria(categoria)}")
    print("==========================================")

    print("[AUDIO] Generando narración...")

    audio = CARPETA_TEMP / f"{identificador}.mp3"

    await generar_audio(
        narracion,
        audio,
    )

    duracion_audio = obtener_duracion(audio)

    if duracion_audio <= 0:
        raise RuntimeError(
            "Duración de audio inválida."
        )

    if duracion_audio > DURACION_MAXIMA:
        raise RuntimeError(
            f"El audio dura {duracion_audio:.1f} segundos. "
            f"Máximo permitido: {DURACION_MAXIMA}."
        )

    print(f"[AUDIO] {duracion_audio:.1f} segundos")

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

    print("[RENDER] Combinando video, audio y subtítulos...")

    mezclar_video_audio(
        video_base,
        audio,
        subtitulos,
        salida,
    )

    duracion_final = obtener_duracion(salida)

    if duracion_final > DURACION_MAXIMA:
        salida.unlink(missing_ok=True)

        raise RuntimeError(
            "El video supera el límite de duración."
        )

    if (
        not salida.exists()
        or salida.stat().st_size < 1_000_000
    ):
        salida.unlink(missing_ok=True)

        raise RuntimeError(
            "El video final está vacío o pesa menos de 1 MB."
        )

    print("==========================================")
    print("[OK] VIDEO TERMINADO")
    print(f"[ARCHIVO] {salida}")
    print(f"[DURACIÓN] {duracion_final:.1f} segundos")
    print(f"[CATEGORÍA] {obtener_nombre_categoria(categoria)}")
    print("==========================================")

    return salida
