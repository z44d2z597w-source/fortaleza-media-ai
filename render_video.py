
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
    ImageFilter, ImageOps
)


# ==========================================================
# FORTALEZA MEDIA AI 5.0
# MOTOR AUDIOVISUAL INTELIGENTE
# ==========================================================

FPS = 30
VOZ = "es-MX-DaliaNeural"
VELOCIDAD_VOZ = "+5%"

OUTPUT = Path("output")
RECURSOS = OUTPUT / "recursos"

MAX_ESCENAS = 20
IMAGENES_POR_ESCENA = 4

CRF = "22"
MAX_MB = 80

CABECERAS = {
    "User-Agent": "FORTALEZA-MEDIA-AI/5.0"
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

    for archivo in OUTPUT.glob("*.mp4"):
        archivo.unlink()

    for archivo in OUTPUT.glob("*.png"):
        archivo.unlink()

    for archivo in OUTPUT.glob("*.txt"):
        archivo.unlink()

    for archivo in OUTPUT.glob("*.wav"):
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
        comando,
        capture_output=True,
        text=True
    )

    if resultado.returncode != 0:
        raise RuntimeError(
            "ERROR FFmpeg:\n" + resultado.stderr[-6000:]
        )


def limpiar_html(texto):
    texto = re.sub(r"<[^>]+>", "", str(texto))
    return html.unescape(texto).strip()


def duracion_audio(ffmpeg, archivo):
    resultado = subprocess.run(
        [ffmpeg, "-i", str(archivo)],
        capture_output=True,
        text=True
    )

    coincidencia = re.search(
        r"Duration: (\d+):(\d+):(\d+\.\d+)",
        resultado.stderr
    )

    if not coincidencia:
        raise RuntimeError(
            "No se pudo determinar la duración del audio."
        )

    horas, minutos, segundos = coincidencia.groups()

    return (
        int(horas) * 3600
        + int(minutos) * 60
        + float(segundos)
    )


def color_rgb(color):
    color = color.lstrip("#")
    return tuple(
        int(color[i:i + 2], 16)
        for i in (0, 2, 4)
    )


def dividir_lineas(dibujo, texto, font, ancho):
    lineas = []
    actual = ""

    for palabra in texto.split():
        prueba = (actual + " " + palabra).strip()

        caja = dibujo.textbbox(
            (0, 0), prueba, font=font
        )

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
# SELECCIÓN AUTOMÁTICA DE FORMATO
# ==========================================================

def seleccionar_formato(guion):
    texto = str(
        guion.get("formato", "")
    ).lower()

    duracion = int(
        guion.get("duracion", 0) or 0
    )

    escenas = guion.get("escenas", [])

    horizontal = (
        "horizontal" in texto
        or "video largo" in texto
        or "16:9" in texto
        or duracion >= 180
        or len(escenas) >= 8
    )

    if horizontal:
        return {
            "nombre": "horizontal",
            "ancho": 1920,
            "alto": 1080,
            "etiqueta": "YOUTUBE VIDEO",
        }

    return {
        "nombre": "vertical",
        "ancho": 1080,
        "alto": 1920,
        "etiqueta": "YOUTUBE SHORTS",
    }


# ==========================================================
# BÚSQUEDA DE FOTOGRAFÍAS
# WIKIMEDIA COMMONS
# ==========================================================

def crear_busqueda(titulo, narracion):
    palabras = re.findall(
        r"[a-zA-ZáéíóúÁÉÍÓÚñÑ]{4,}",
        titulo + " " + narracion
    )

    resultado = []

    for palabra in palabras:
        if palabra.lower() in STOPWORDS:
            continue

        if palabra.lower() not in [
            x.lower() for x in resultado
        ]:
            resultado.append(palabra)

    return " ".join(resultado[:9])


def buscar_fotografias(titulo, narracion, numero):
    consulta = crear_busqueda(titulo, narracion)

    print("[VISUAL] Buscando:", consulta)

    parametros = {
        "action": "query",
        "generator": "search",
        "gsrsearch": consulta,
        "gsrnamespace": 6,
        "gsrlimit": 25,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 1600,
        "format": "json",
    }

    try:
        respuesta = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params=parametros,
            headers=CABECERAS,
            timeout=25
        )

        respuesta.raise_for_status()

        paginas = respuesta.json().get(
            "query", {}
        ).get("pages", {})

    except Exception as error:
        print("[VISUAL] Búsqueda fallida:", error)
        return []

    resultados = []
    urls_vistas = set()

    for pagina in paginas.values():
        informacion = pagina.get("imageinfo", [])

        if not informacion:
            continue

        info = informacion[0]

        if not info.get("mime", "").startswith("image/"):
            continue

        url = info.get("thumburl") or info.get("url")

        if not url or url in urls_vistas:
            continue

        urls_vistas.add(url)

        try:
            descarga = requests.get(
                url,
                headers=CABECERAS,
                timeout=30
            )

            descarga.raise_for_status()

            imagen = Image.open(
                BytesIO(descarga.content)
            ).convert("RGB")

            if imagen.width < 500 or imagen.height < 350:
                continue

            ruta = RECURSOS / (
                f"foto_{numero:02d}_{len(resultados):02d}.jpg"
            )

            imagen.save(
                ruta,
                "JPEG",
                quality=92
            )

            metadatos = info.get("extmetadata", {})

            autor = limpiar_html(
                metadatos.get(
                    "Artist", {}
                ).get("value", "Autor no indicado")
            )

            licencia = limpiar_html(
                metadatos.get(
                    "LicenseShortName", {}
                ).get("value", "Consultar licencia")
            )

            pagina_url = info.get(
                "descriptionurl", url
            )

            resultados.append({
                "archivo": str(ruta),
                "autor": autor,
                "licencia": licencia,
                "url": pagina_url,
            })

            print(
                "[VISUAL] Fotografía:",
                len(resultados)
            )

            if len(resultados) >= IMAGENES_POR_ESCENA:
                break

        except Exception as error:
            print("[VISUAL] Imagen omitida:", error)

    return resultados


# ==========================================================
# FONDOS Y FOTOGRAFÍA CINEMATOGRÁFICA
# ==========================================================

def crear_fondo(numero, ancho, alto):
    oscuro, medio, acento = PALETAS[
        numero % len(PALETAS)
    ]

    gradiente = Image.linear_gradient("L").resize(
        (ancho, alto)
    )

    imagen = ImageOps.colorize(
        gradiente,
        black=oscuro,
        white=medio
    ).convert("RGB")

    dibujo = ImageDraw.Draw(imagen, "RGBA")
    rgb = color_rgb(acento)

    for i in range(10):
        radio = 100 + i * 80
        x = int(ancho * 0.72)
        y = int(alto * 0.2) + i * 100

        dibujo.ellipse(
            (
                x - radio, y - radio,
                x + radio, y + radio
            ),
            outline=(*rgb, max(10, 65 - i * 5)),
            width=4
        )

    return imagen


def preparar_fotografia(ruta, ancho, alto):
    imagen = Image.open(ruta).convert("RGB")

    imagen = ImageOps.fit(
        imagen,
        (ancho, alto),
        method=Image.Resampling.LANCZOS
    )

    imagen = ImageEnhance.Color(imagen).enhance(1.22)
    imagen = ImageEnhance.Contrast(imagen).enhance(1.16)
    imagen = ImageEnhance.Brightness(imagen).enhance(0.82)

    mascara = Image.new("L", (ancho, alto), 0)
    dibujo = ImageDraw.Draw(mascara)

    dibujo.ellipse(
        (-ancho * 0.2, -alto * 0.2,
         ancho * 1.2, alto * 1.2),
        fill=255
    )

    mascara = mascara.filter(
        ImageFilter.GaussianBlur(
            max(40, int(ancho * 0.07))
        )
    )

    sombra = Image.new(
        "RGB", (ancho, alto), (0, 0, 0)
    )

    return Image.composite(
        imagen, sombra, mascara
    )


# ==========================================================
# DISEÑO DE ESCENAS
# ==========================================================

def crear_escena(
    titulo,
    numero,
    total,
    fotografia,
    formato
):
    ancho = formato["ancho"]
    alto = formato["alto"]

    if fotografia and os.path.exists(fotografia):
        imagen = preparar_fotografia(
            fotografia, ancho, alto
        )
    else:
        imagen = crear_fondo(
            numero, ancho, alto
        )

    dibujo = ImageDraw.Draw(imagen)

    acento = PALETAS[
        numero % len(PALETAS)
    ][2]

    margen = int(ancho * 0.06)

    dibujo.text(
        (margen, int(alto * 0.055)),
        "FORTALEZA MEDIA AI",
        font=fuente(int(ancho * 0.025), True),
        fill="white",
        stroke_width=2,
        stroke_fill="#000000"
    )

    dibujo.rounded_rectangle(
        (
            margen,
            int(alto * 0.105),
            margen + int(ancho * 0.23),
            int(alto * 0.112)
        ),
        radius=5,
        fill=acento
    )

    dibujo.text(
        (ancho - margen, int(alto * 0.055)),
        f"{numero + 1:02d}/{total:02d}",
        font=fuente(int(ancho * 0.023), True),
        fill=acento,
        anchor="ra"
    )

    if numero == 0:
        tamano = int(ancho * 0.068)
        font = fuente(tamano, True)

        lineas = dividir_lineas(
            dibujo,
            titulo.upper(),
            font,
            int(ancho * 0.86)
        )[:3]

        dibujo.multiline_text(
            (ancho // 2, int(alto * 0.30)),
            "\n".join(lineas),
            font=font,
            fill="white",
            anchor="mm",
            align="center",
            spacing=int(tamano * 0.30),
            stroke_width=4,
            stroke_fill="#000000"
        )

    ruta = RECURSOS / f"escena_{numero:02d}.jpg"

    imagen.save(ruta, quality=94)

    return str(ruta)


# ==========================================================
# VOZ IA Y SINCRONIZACIÓN
# ==========================================================

async def crear_voz(texto, ruta):
    comunicacion = edge_tts.Communicate(
        texto,
        voice=VOZ,
        rate=VELOCIDAD_VOZ,
        pitch="+0Hz"
    )

    audio = bytearray()
    palabras = []

    async for fragmento in comunicacion.stream():
        if fragmento["type"] == "audio":
            audio.extend(fragmento["data"])

        elif fragmento["type"] == "WordBoundary":
            inicio = fragmento["offset"] / 10000000
            duracion = fragmento["duration"] / 10000000

            palabras.append({
                "texto": fragmento["text"],
                "inicio": inicio,
                "fin": inicio + duracion,
            })

    if not audio:
        raise RuntimeError(
            "La voz IA no devolvió audio."
        )

    with open(ruta, "wb") as archivo:
        archivo.write(audio)

    return palabras


# ==========================================================
# SUBTÍTULOS DINÁMICOS
# ==========================================================

def crear_imagen_subtitulo(
    palabras,
    numero,
    formato,
    acento
):
    ancho = formato["ancho"]
    alto = formato["alto"]

    imagen = Image.new(
        "RGBA",
        (ancho, alto),
        (0, 0, 0, 0)
    )

    dibujo = ImageDraw.Draw(imagen)

    frase = " ".join(
        palabra["texto"]
        for palabra in palabras
    )

    tamano = int(ancho * 0.044)
    font = fuente(tamano, True)

    lineas = dividir_lineas(
        dibujo,
        frase,
        font,
        int(ancho * 0.82)
    )[:3]

    alto_linea = int(tamano * 1.45)
    caja_alto = len(lineas) * alto_linea + 65

    if formato["nombre"] == "vertical":
        centro_y = int(alto * 0.78)
    else:
        centro_y = int(alto * 0.78)

    superior = centro_y - caja_alto // 2
    inferior = centro_y + caja_alto // 2

    dibujo.rounded_rectangle(
        (
            int(ancho * 0.055),
            superior,
            int(ancho * 0.945),
            inferior
        ),
        radius=30,
        fill=(0, 0, 0, 205),
        outline=(*color_rgb(acento), 245),
        width=4
    )

    y = centro_y - (len(lineas) * alto_linea) // 2

    for linea in lineas:
        dibujo.text(
            (ancho // 2, y),
            linea,
            font=font,
            fill="white",
            anchor="mm",
            stroke_width=3,
            stroke_fill="#000000"
        )

        y += alto_linea

    ruta = RECURSOS / f"caption_{numero:04d}.png"
    imagen.save(ruta)

    return str(ruta)


def crear_subtitulos(
    palabras,
    duracion,
    numero,
    formato,
    acento
):
    grupos = []
    grupo = []

    for palabra in palabras:
        grupo.append(palabra)

        texto = " ".join(
            p["texto"] for p in grupo
        )

        if len(grupo) >= 5 or len(texto) >= 32:
            grupos.append(grupo)
            grupo = []

    if grupo:
        grupos.append(grupo)

    resultado = []

    for indice, grupo in enumerate(grupos):
        inicio = max(0, grupo[0]["inicio"])

        fin = min(
            duracion,
            grupo[-1]["fin"] + 0.18
        )

        if fin <= inicio:
            continue

        ruta = crear_imagen_subtitulo(
            grupo,
            numero * 100 + indice,
            formato,
            acento
        )

        resultado.append({
            "archivo": ruta,
            "inicio": inicio,
            "fin": fin,
        })

    return resultado


# ==========================================================
# MOVIMIENTO DE CÁMARA Y TRANSICIONES
# ==========================================================

def crear_toma(
    ffmpeg,
    imagen,
    destino,
    duracion,
    numero,
    formato
):
    ancho = formato["ancho"]
    alto = formato["alto"]

    escala_ancho = int(ancho * 1.15)
    escala_alto = int(alto * 1.15)

    movimientos = [
        (
            "min(zoom+0.0010,1.20)",
            "iw/2-(iw/zoom/2)",
            "ih/2-(ih/zoom/2)"
        ),
        (
            "min(zoom+0.0012,1.22)",
            "iw/2-(iw/zoom/2)+on*0.12",
            "ih/2-(ih/zoom/2)"
        ),
        (
            "min(zoom+0.0010,1.18)",
            "iw/2-(iw/zoom/2)",
            "ih/2-(ih/zoom/2)+on*0.10"
        ),
        (
            "max(zoom-0.0007,1.0)",
            "iw/2-(iw/zoom/2)-on*0.08",
            "ih/2-(ih/zoom/2)"
        ),
    ]

    zoom, x, y = movimientos[numero % len(movimientos)]

    salida_filtro = (
        f"zoompan=z='{zoom}':"
        f"x='{x}':"
        f"y='{y}':"
        "d=1:"
        f"s={ancho}x{alto}:"
        f"fps={FPS},"
        "setsar=1,"
        "format=yuv420p,"
        "fade=t=in:st=0:d=0.25,"
        f"fade=t=out:st={max(0, duracion - 0.30):.3f}:d=0.30"
    )

    filtro = (
        f"scale={escala_ancho}:{escala_alto}:"
        "force_original_aspect_ratio=increase,"
        f"crop={escala_ancho}:{escala_alto},"
        + salida_filtro
    )

    ejecutar([
        ffmpeg,
        "-y",
        "-loop", "1",
        "-framerate", str(FPS),
        "-i", imagen,
        "-vf", filtro,
        "-t", f"{duracion:.3f}",
        "-an",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", CRF,
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        str(destino)
    ])


# ==========================================================
# UNIÓN DE TOMAS
# ==========================================================

def concatenar(ffmpeg, archivos, destino, lista):
    with open(lista, "w", encoding="utf-8") as archivo:
        for elemento in archivos:
            ruta = Path(elemento).resolve()
            archivo.write(
                "file '" + str(ruta).replace("'", "'\\''") + "'\n"
            )

    ejecutar([
        ffmpeg,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(lista),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", CRF,
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        str(destino)
    ])


# ==========================================================
# MEZCLA DE AUDIO ORIGINAL
# ==========================================================

def crear_musica(ffmpeg, duracion):
    ruta = RECURSOS / "musica_ambiente.wav"

    frecuencia = 22050

    # Música ambiental original, sin utilizar canciones comerciales.
    tono_a = array("h")
    tono_b = array("h")

    for i in range(int(frecuencia * duracion)):
        t = i / frecuencia

        modulacion = (
            0.65
            + 0.35 * math.sin(2 * math.pi * 0.035 * t)
        )

        sonido = (
            math.sin(2 * math.pi * 110 * t) * 0.28
            + math.sin(2 * math.pi * 164.81 * t) * 0.20
            + math.sin(2 * math.pi * 220 * t) * 0.12
        )

        valor = int(
            32767 * 0.055 * modulacion * sonido
        )

        tono_a.append(valor)
        tono_b.append(valor)

    with wave.open(str(ruta), "wb") as archivo:
        archivo.setnchannels(2)
        archivo.setsampwidth(2)
        archivo.setframerate(frecuencia)
        archivo.writeframes(
            tono_a.tobytes() + b""
        )

    # Construcción correcta del audio estéreo intercalado.
    datos = array("h")

    for i in range(len(tono_a)):
        datos.append(tono_a[i])
        datos.append(tono_b[i])

    with wave.open(str(ruta), "wb") as archivo:
        archivo.setnchannels(2)
        archivo.setsampwidth(2)
        archivo.setframerate(frecuencia)
        archivo.writeframes(datos.tobytes())

    return str(ruta)


def mezclar_audio(
    ffmpeg,
    video,
    musica,
    destino
):
    ejecutar([
        ffmpeg,
        "-y",
        "-i", str(video),
        "-stream_loop", "-1",
        "-i", str(musica),
        "-filter_complex",
        (
            "[1:a]volume=0.12[musica];"
            "[0:a]volume=1.0[voz];"
            "[voz][musica]"
            "amix=inputs=2:duration=first:"
            "dropout_transition=3[audio]"
        ),
        "-map", "0:v:0",
        "-map", "[audio]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(destino)
    ])


# ==========================================================
# CRÉDITOS DE FOTOGRAFÍAS
# ==========================================================

def guardar_creditos(fuentes):
    ruta = OUTPUT / "creditos_imagenes.txt"

    with open(ruta, "w", encoding="utf-8") as archivo:
        archivo.write(
            "FUENTES VISUALES - FORTALEZA MEDIA AI 5.0\n\n"
        )

        for elemento in fuentes:
            archivo.write(
                f"Autor: {elemento['autor']}\n"
                f"Licencia: {elemento['licencia']}\n"
                f"Fuente: {elemento['url']}\n\n"
            )

    return str(ruta)


# ==========================================================
# PRODUCCIÓN PRINCIPAL
# ==========================================================

async def crear_video():
    preparar_carpetas()

    guion_path = Path("guion.json")

    if not guion_path.exists():
        raise FileNotFoundError(
            "No se encontró guion.json"
        )

    with open(
        guion_path,
        encoding="utf-8"
    ) as archivo:
        guion = json.load(archivo)

    titulo = str(
        guion.get(
            "titulo",
            "Una historia sorprendente"
        )
    )

    escenas = [
        escena
        for escena in guion.get("escenas", [])
        if str(escena.get("narracion", "")).strip()
    ][:MAX_ESCENAS]

    if not escenas:
        raise ValueError(
            "El guion no contiene narraciones."
        )

    formato = seleccionar_formato(guion)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    print("=" * 60)
    print("FORTALEZA MEDIA AI 5.0")
    print("FORMATO:", formato["nombre"])
    print("RESOLUCIÓN:", formato["ancho"], "x", formato["alto"])
    print("ESCENAS:", len(escenas))
    print("=" * 60)

    clips = []
    fuentes = []

    # ------------------------------------------------------
    # PRODUCCIÓN DE ESCENAS
    # ------------------------------------------------------

    for numero, escena in enumerate(escenas):
        narracion = str(
            escena["narracion"]
        ).strip()

        titulo_escena = str(
            escena.get("titulo", titulo)
        )

        print(
            f"\n[ESCENA {numero + 1}/{len(escenas)}]"
        )

        # Fotografías.
        fotografias = buscar_fotografias(
            titulo_escena,
            narracion,
            numero
        )

        fuentes.extend(fotografias)

        if fotografias:
            imagenes = [
                foto["archivo"]
                for foto in fotografias
            ]
        else:
            respaldo = RECURSOS / f"respaldo_{numero:02d}.jpg"

            crear_fondo(
                numero,
                formato["ancho"],
                formato["alto"]
            ).save(respaldo, quality=92)

            imagenes = [str(respaldo)]

        # Portada de la escena.
        portada = crear_escena(
            titulo_escena if numero == 0 else "",
            numero,
            len(escenas),
            imagenes[0],
            formato
        )

        imagenes[0] = portada

        # Voz.
        audio = RECURSOS / f"voz_{numero:02d}.mp3"

        palabras = await crear_voz(
            narracion,
            str(audio)
        )

        duracion = duracion_audio(
            ffmpeg,
            audio
        )

        if duracion <= 0:
            raise RuntimeError(
                "La duración de la voz es inválida."
            )

        # Subtítulos.
        acento = PALETAS[
            numero % len(PALETAS)
        ][2]

        subtitulos = crear_subtitulos(
            palabras,
            duracion,
            numero,
            formato,
            acento
        )

        # Tomas visuales.
        duracion_toma = duracion / len(imagenes)
        tomas = []

        for indice, imagen in enumerate(imagenes):
            toma = RECURSOS / (
                f"toma_{numero:02d}_{indice:02d}.mp4"
            )

            crear_toma(
                ffmpeg,
                imagen,
                toma,
                duracion_toma,
                numero + indice,
                formato
            )

            tomas.append(str(toma))

        # Unir tomas.
        visual = RECURSOS / f"visual_{numero:02d}.mp4"

        concatenar(
            ffmpeg,
            tomas,
            visual,
            RECURSOS / f"lista_visual_{numero:02d}.txt"
        )

        # Añadir subtítulos.
        comando = [
            ffmpeg,
            "-y",
            "-i", str(visual),
            "-i", str(audio)
        ]

        for subtitulo in subtitulos:
            comando.extend([
                "-loop", "1",
                "-framerate", str(FPS),
                "-i", subtitulo["archivo"]
            ])

        filtros = []
        actual = "[0:v]"

        for indice, subtitulo in enumerate(subtitulos):
            entrada = indice + 2
            salida = f"[v{indice + 1}]"

            filtros.append(
                f"{actual}[{entrada}:v]"
                "overlay=0:0:"
                "eof_action=pass:"
                f"enable='between(t\\,{subtitulo['inicio']:.3f}\\,{subtitulo['fin']:.3f})'"
                f"{salida}"
            )

            actual = salida

        if filtros:
            filtro_final = ";".join(filtros)
        else:
            filtro_final = "[0:v]null[vfinal]"
            actual = "[vfinal]"

        escena_final = RECURSOS / f"escena_final_{numero:02d}.mp4"

        comando.extend([
            "-filter_complex",
            filtro_final,
            "-map", actual,
            "-map", "1:a",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", CRF,
            "-pix_fmt", "yuv420p",
            "-r", str(FPS),
            "-c:a", "aac",
            "-b:a", "160k",
            "-shortest",
            "-movflags", "+faststart",
            str(escena_final)
        ])

        ejecutar(comando)

        clips.append(str(escena_final))

        print(
            "[ESCENA] Terminada:",
            round(duracion, 2),
            "segundos"
        )

    # ------------------------------------------------------
    # UNIÓN DE TODAS LAS ESCENAS
    # ------------------------------------------------------

    print("\n[FINAL] Uniendo escenas...")

    video_base = OUTPUT / "video_base.mp4"

    concatenar(
        ffmpeg,
        clips,
        video_base,
        OUTPUT / "lista_final.txt"
    )

    duracion_total = duracion_audio(
        ffmpeg,
        video_base
    )

    # ------------------------------------------------------
    # MÚSICA Y MEZCLA
    # ------------------------------------------------------

    print("[AUDIO] Creando música ambiental...")

    musica = crear_musica(
        ffmpeg,
        max(10, int(duracion_total) + 5)
    )

    if formato["nombre"] == "horizontal":
        destino = OUTPUT / "fortaleza_largo.mp4"
    else:
        destino = OUTPUT / "fortaleza_short.mp4"

    print("[FINAL] Mezclando audio...")

    mezclar_audio(
        ffmpeg,
        video_base,
        musica,
        destino
    )

    # ------------------------------------------------------
    # CRÉDITOS Y METADATOS
    # ------------------------------------------------------

    guardar_creditos(fuentes)

    if fuentes:
        creditos = "\n\nFUENTES VISUALES:\n"

        for elemento in fuentes:
            creditos += (
                f"{elemento['autor']} | "
                f"{elemento['licencia']} | "
                f"{elemento['url']}\n"
            )

        guion["descripcion"] = (
            guion.get("descripcion", "") + creditos
        )

        with open(
            guion_path,
            "w",
            encoding="utf-8"
        ) as archivo:
            json.dump(
                guion,
                archivo,
                ensure_ascii=False,
                indent=4
            )

    # ------------------------------------------------------
    # COMPATIBILIDAD CON EL SISTEMA ACTUAL
    # ------------------------------------------------------

    alias_short = OUTPUT / "fortaleza_short.mp4"

    if destino != alias_short:
        shutil.copy2(
            destino,
            alias_short
        )

    # ------------------------------------------------------
    # VALIDACIÓN FINAL
    # ------------------------------------------------------

    for archivo in {destino, alias_short}:
        if not archivo.exists():
            raise FileNotFoundError(
                f"No se generó: {archivo}"
            )

        tamano = archivo.stat().st_size

        if tamano <= 100_000:
            raise RuntimeError(
                "El MP4 generado está vacío o incompleto."
            )

        if tamano > MAX_MB * 1024 * 1024:
            raise RuntimeError(
                f"El video supera el límite de {MAX_MB} MB."
            )

        with archivo.open("rb") as entrada:
            cabecera = entrada.read(16)

        if b"ftyp" not in cabecera:
            raise RuntimeError(
                "El archivo no contiene una cabecera MP4 válida."
            )

    estado = {
        "version": "5.0",
        "titulo": titulo,
        "formato": formato["nombre"],
        "resolucion": (
            f"{formato['ancho']}x{formato['alto']}"
        ),
        "escenas": len(escenas),
        "fotografias": len(fuentes),
        "duracion_segundos": round(duracion_total, 2),
        "archivo": str(destino),
        "tamano_mb": round(
            destino.stat().st_size / 1048576,
            2
        ),
        "validado": True,
    }

    with open(
        OUTPUT / "estado_produccion.json",
        "w",
        encoding="utf-8"
    ) as archivo:
        json.dump(
            estado,
            archivo,
            ensure_ascii=False,
            indent=4
        )

    print("\n" + "=" * 60)
    print("FORTALEZA MEDIA AI 5.0")
    print("PRODUCCIÓN TERMINADA")
    print("=" * 60)
    print(json.dumps(
        estado,
        ensure_ascii=False,
        indent=4
    ))
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(crear_video())
