
import asyncio
import html
import json
import math
import os
import random
import re
import subprocess
import wave

from array import array
from io import BytesIO
from pathlib import Path

import requests
import edge_tts
import imageio_ffmpeg

from PIL import (
    Image,
    ImageDraw,
    ImageFont,
    ImageEnhance,
    ImageFilter,
    ImageOps
)


# ==========================================================
# FORTALEZA MEDIA AI 4.0
# MOTOR VISUAL CINEMATOGRÁFICO
# ==========================================================

ANCHO = 1080
ALTO = 1920
FPS = 30

VOZ = "es-MX-DaliaNeural"
VELOCIDAD_VOZ = "+5%"

OUTPUT = Path("output")
RECURSOS = OUTPUT / "recursos"

IMAGENES_POR_ESCENA = 4
MAX_ESCENAS = 12

CALIDAD = "medium"
CRF = "21"

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

CABECERAS = {
    "User-Agent": "FORTALEZA-MEDIA-AI/4.0 (video production)",
}


# ==========================================================
# UTILIDADES
# ==========================================================

def preparar_carpetas():

    OUTPUT.mkdir(exist_ok=True)
    RECURSOS.mkdir(exist_ok=True)


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
            "ERROR FFmpeg:\n" + resultado.stderr[-5000:]
        )


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
            "No se pudo leer la duración del audio."
        )

    horas, minutos, segundos = coincidencia.groups()

    return (
        int(horas) * 3600
        + int(minutos) * 60
        + float(segundos)
    )


def limpiar_html(texto):

    texto = re.sub(r"<[^>]+>", "", str(texto))

    return html.unescape(texto).strip()


# ==========================================================
# BÚSQUEDA DE IMÁGENES REALES
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
        "gsrlimit": 20,
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

        print("[VISUAL] Error de búsqueda:", error)

        return []

    resultados = []
    urls_vistas = set()

    for pagina in paginas.values():

        informacion = pagina.get("imageinfo", [])

        if not informacion:
            continue

        info = informacion[0]

        tipo = info.get("mime", "")

        if not tipo.startswith("image/"):
            continue

        imagen_url = (
            info.get("thumburl")
            or info.get("url")
        )

        if not imagen_url or imagen_url in urls_vistas:
            continue

        urls_vistas.add(imagen_url)

        try:

            descarga = requests.get(
                imagen_url,
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
                f"escena_{numero:02d}_"
                f"{len(resultados):02d}.jpg"
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
                "descriptionurl", imagen_url
            )

            resultados.append({
                "archivo": str(ruta),
                "autor": autor,
                "licencia": licencia,
                "url": pagina_url,
            })

            print(
                "[VISUAL] Imagen descargada:",
                len(resultados)
            )

            if len(resultados) >= IMAGENES_POR_ESCENA:
                break

        except Exception as error:

            print("[VISUAL] Imagen omitida:", error)

    return resultados


# ==========================================================
# FONDOS CINEMATOGRÁFICOS
# ==========================================================

def color_rgb(color):

    color = color.lstrip("#")

    return tuple(
        int(color[i:i + 2], 16)
        for i in (0, 2, 4)
    )


def crear_fondo(numero):

    oscuro, medio, acento = PALETAS[
        numero % len(PALETAS)
    ]

    gradiente = Image.linear_gradient("L").resize(
        (ANCHO, ALTO)
    )

    imagen = ImageOps.colorize(
        gradiente,
        black=oscuro,
        white=medio
    ).convert("RGB")

    dibujo = ImageDraw.Draw(imagen, "RGBA")

    rgb = color_rgb(acento)

    for i in range(12):

        radio = 100 + i * 85

        x = 800 - (numero * 95) % 350
        y = 250 + i * 145

        dibujo.ellipse(
            (
                x - radio,
                y - radio,
                x + radio,
                y + radio
            ),
            outline=(*rgb, max(12, 65 - i * 4)),
            width=4
        )

    return imagen


def preparar_fotografia(ruta, numero):

    imagen = Image.open(ruta).convert("RGB")

    imagen = ImageOps.fit(
        imagen,
        (ANCHO, ALTO),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5)
    )

    imagen = ImageEnhance.Color(imagen).enhance(1.25)
    imagen = ImageEnhance.Contrast(imagen).enhance(1.15)
    imagen = ImageEnhance.Brightness(imagen).enhance(0.78)

    # Viñeta suave para mejorar el contraste.
    mascara = Image.new(
        "L",
        (ANCHO, ALTO),
        0
    )

    dibujo = ImageDraw.Draw(mascara)

    dibujo.ellipse(
        (-250, -200, ANCHO + 250, ALTO + 200),
        fill=255
    )

    mascara = mascara.filter(
        ImageFilter.GaussianBlur(120)
    )

    sombra = Image.new(
        "RGB",
        (ANCHO, ALTO),
        (0, 0, 0)
    )

    imagen = Image.composite(
        imagen,
        sombra,
        mascara
    )

    return imagen


# ==========================================================
# DISEÑO DE ESCENAS Y TÍTULOS
# ==========================================================

def dividir_lineas(dibujo, texto, font, ancho):

    lineas = []
    actual = ""

    for palabra in texto.split():

        prueba = (actual + " " + palabra).strip()

        if dibujo.textbbox(
            (0, 0),
            prueba,
            font=font
        )[2] <= ancho:

            actual = prueba

        else:

            if actual:
                lineas.append(actual)

            actual = palabra

    if actual:
        lineas.append(actual)

    return lineas


def crear_escena(titulo, numero, total, fotografia=None):

    if fotografia and os.path.exists(fotografia):

        imagen = preparar_fotografia(
            fotografia,
            numero
        )

    else:

        imagen = crear_fondo(numero)

    dibujo = ImageDraw.Draw(imagen)

    acento = PALETAS[numero % len(PALETAS)][2]

    # Marca de agua.
    dibujo.text(
        (65, 90),
        "FORTALEZA MEDIA AI",
        font=fuente(30, True),
        fill="white",
        stroke_width=1,
        stroke_fill="#000000"
    )

    dibujo.rounded_rectangle(
        (65, 145, 315, 156),
        radius=5,
        fill=acento
    )

    dibujo.text(
        (ANCHO - 65, 90),
        f"{numero + 1:02d}/{total:02d}",
        font=fuente(30, True),
        fill=acento,
        anchor="ra"
    )

    if numero == 0:

        titulo_visual = titulo.upper()

        font = fuente(78, True)

        lineas = dividir_lineas(
            dibujo,
            titulo_visual,
            font,
            930
        )[:3]

        dibujo.multiline_text(
            (ANCHO // 2, 350),
            "\n".join(lineas),
            font=font,
            fill="white",
            anchor="mm",
            align="center",
            spacing=24,
            stroke_width=4,
            stroke_fill="#000000"
        )

    ruta = OUTPUT / f"visual_{numero:02d}.png"

    imagen.save(ruta)

    return str(ruta)


# ==========================================================
# VOZ Y SINCRONIZACIÓN
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
            "No se recibió audio de la voz."
        )

    with open(ruta, "wb") as archivo:
        archivo.write(audio)

    return palabras


# ==========================================================
# SUBTÍTULOS DINÁMICOS
# ==========================================================

def crear_imagen_subtitulo(palabras, numero, acento):

    imagen = Image.new(
        "RGBA",
        (ANCHO, 400),
        (0, 0, 0, 0)
    )

    dibujo = ImageDraw.Draw(imagen)

    frase = " ".join(
        palabra["texto"]
        for palabra in palabras
    )

    font = fuente(53, True)

    dibujo.rounded_rectangle(
        (40, 45, 1040, 350),
        radius=38,
        fill=(0, 0, 0, 195),
        outline=(*color_rgb(acento), 240),
        width=4
    )

    lineas = dividir_lineas(
        dibujo,
        frase,
        font,
        880
    )[:3]

    alto = len(lineas) * 75

    y = 195 - alto // 2

    for indice, linea in enumerate(lineas):

        dibujo.text(
            (ANCHO // 2, y + indice * 80),
            linea,
            font=font,
            fill="white",
            anchor="mm",
            stroke_width=3,
            stroke_fill="#000000"
        )

    dibujo.rounded_rectangle(
        (390, 370, 690, 380),
        radius=5,
        fill=acento
    )

    ruta = OUTPUT / f"caption_{numero:04d}.png"

    imagen.save(ruta)

    return str(ruta)


def crear_subtitulos(palabras, duracion, numero, acento):

    grupos = []
    grupo = []

    for palabra in palabras:

        grupo.append(palabra)

        texto = " ".join(
            p["texto"] for p in grupo
        )

        if len(grupo) >= 5 or len(texto) >= 30:

            grupos.append(grupo)
            grupo = []

    if grupo:
        grupos.append(grupo)

    resultado = []

    for indice, grupo in enumerate(grupos):

        inicio = max(
            0,
            grupo[0]["inicio"]
        )

        fin = min(
            duracion,
            grupo[-1]["fin"] + 0.15
        )

        if fin <= inicio:
            continue

        archivo = crear_imagen_subtitulo(
            grupo,
            numero * 100 + indice,
            acento
        )

        resultado.append({
            "archivo": archivo,
            "inicio": inicio,
            "fin": fin,
        })

    return resultado


# ==========================================================
# MOVIMIENTO DE CÁMARA
# ==========================================================

def crear_toma(ffmpeg, imagen, destino, duracion, numero):

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

    filtro = (
        "scale=1200:2134:force_original_aspect_ratio=increase,"
        "crop=1200:2134,"
        "zoompan="
        f"z='{zoom}':"
        f"x='{x}':"
        f"y='{y}':"
        "d=1:"
        "s=1080x1920:"
        "fps=30,"
        "setsar=1,"
        "format=yuv420p"
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
        destino
    ])


# ==========================================================
# MÚSICA AMBIENTAL ORIGINAL
# ==========================================================

def crear_musica(duracion=180):

    ruta = OUTPUT / "musica_ambiente.wav"

    frecuencia = 22050

    datos = array("h")

    for i in range(frecuencia * duracion):

        t = i / frecuencia

        modulacion = (
            0.60
            + 0.40 * math.sin(
                2 * math.pi * 0.035 * t
            )
        )

        sonido = (
            math.sin(2 * math.pi * 110 * t) * 0.28
            + math.sin(2 * math.pi * 164.81 * t) * 0.20
            + math.sin(2 * math.pi * 220 * t) * 0.12
        )

        valor = int(
            32767 * 0.055 * modulacion * sonido
        )

        datos.append(valor)
        datos.append(valor)

    with wave.open(str(ruta), "wb") as archivo:

        archivo.setnchannels(2)
        archivo.setsampwidth(2)
        archivo.setframerate(frecuencia)
        archivo.writeframes(datos.tobytes())

    return str(ruta)


# ==========================================================
# CRÉDITOS VISUALES
# ==========================================================

def guardar_creditos(fuentes):

    ruta = OUTPUT / "creditos_imagenes.txt"

    with open(
        ruta,
        "w",
        encoding="utf-8"
    ) as archivo:

        archivo.write(
            "FUENTES VISUALES - FORTALEZA MEDIA AI\n\n"
        )

        for elemento in fuentes:

            archivo.write(
                f"Autor: {elemento['autor']}\n"
            )

            archivo.write(
                f"Licencia: {elemento['licencia']}\n"
            )

            archivo.write(
                f"Fuente: {elemento['url']}\n\n"
            )

    return str(ruta)


# ==========================================================
# PRODUCCIÓN PRINCIPAL
# ==========================================================

async def crear_video():

    preparar_carpetas()

    if not Path("guion.json").exists():

        raise FileNotFoundError(
            "No se encontró guion.json"
        )

    with open(
        "guion.json",
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
        if str(
            escena.get("narracion", "")
        ).strip()
    ][:MAX_ESCENAS]

    if not escenas:
        raise ValueError(
            "El guion no contiene narraciones."
        )

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    clips = []
    todas_las_fuentes = []

    print("=" * 55)
    print("FORTALEZA MEDIA AI 4.0")
    print("MOTOR CINEMATOGRÁFICO")
    print("=" * 55)

    # ------------------------------------------------------
    # PRODUCCIÓN DE CADA ESCENA
    # ------------------------------------------------------

    for numero, escena in enumerate(escenas):

        narracion = str(
            escena["narracion"]
        ).strip()

        print(
            f"\n[PRODUCCIÓN] Escena "
            f"{numero + 1}/{len(escenas)}"
        )

        # 1. Buscar imágenes.
        fotografias = buscar_fotografias(
            titulo,
            narracion,
            numero
        )

        todas_las_fuentes.extend(fotografias)

        # 2. Generar narración.
        audio = OUTPUT / f"voz_{numero:02d}.mp3"

        palabras = await crear_voz(
            narracion,
            str(audio)
        )

        duracion = duracion_audio(
            ffmpeg,
            str(audio)
        )

        if duracion <= 0:
            raise RuntimeError(
                "La narración tiene duración inválida."
            )

        # 3. Preparar visuales.
        if fotografias:

            imagenes = [
                foto["archivo"]
                for foto in fotografias
            ]

        else:

            imagenes = [
                str(
                    crear_fondo(numero).save(
                        RECURSOS / f"respaldo_{numero:02d}.jpg"
                    ) or RECURSOS / f"respaldo_{numero:02d}.jpg"
                )
            ]

        # Diseñar una portada visual.
        imagen_portada = crear_escena(
            titulo,
            numero,
            len(escenas),
            imagenes[0]
        )

        imagenes[0] = imagen_portada

        # 4. Subtítulos sincronizados.
        acento = PALETAS[
            numero % len(PALETAS)
        ][2]

        subtitulos = crear_subtitulos(
            palabras,
            duracion,
            numero,
            acento
        )

        # 5. Dividir el tiempo entre las fotografías.
        duracion_toma = duracion / len(imagenes)

        tomas = []

        for indice, imagen in enumerate(imagenes):

            clip_toma = (
                OUTPUT
                / f"toma_{numero:02d}_{indice:02d}.mp4"
            )

            crear_toma(
                ffmpeg,
                imagen,
                str(clip_toma),
                duracion_toma,
                numero + indice
            )

            tomas.append(str(clip_toma))

        # 6. Unir las tomas visuales.
        lista_tomas = OUTPUT / f"lista_tomas_{numero:02d}.txt"

        with open(
            lista_tomas,
            "w",
            encoding="utf-8"
        ) as archivo:

            for toma in tomas:

                archivo.write(
                    f"file '{Path(toma).name}'\n"
                )

        video_visual = OUTPUT / f"visual_final_{numero:02d}.mp4"

        ejecutar([
            ffmpeg,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(lista_tomas),
            "-c", "copy",
            str(video_visual)
        ])

        # 7. Añadir subtítulos.
        comando = [
            ffmpeg,
            "-y",
            "-i", str(video_visual),
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
                "overlay=0:1320:"
                f"enable='between(t\\,{subtitulo['inicio']:.3f}\\,{subtitulo['fin']:.3f})'"
                f"{salida}"
            )

            actual = salida

        if filtros:

            filtro_final = ";".join(filtros)

        else:

            filtro_final = "[0:v]null[vfinal]"
            actual = "[vfinal]"

        clip_final = OUTPUT / f"escena_final_{numero:02d}.mp4"

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
            str(clip_final)
        ])

        ejecutar(comando)

        clips.append(str(clip_final))

        print(
            f"[PRODUCCIÓN] Escena terminada: "
            f"{duracion:.1f} segundos"
        )

    # ------------------------------------------------------
    # UNIÓN FINAL
    # ------------------------------------------------------

    print("\n[FINAL] Uniendo escenas...")

    lista_final = OUTPUT / "lista_final.txt"

    with open(
        lista_final,
        "w",
        encoding="utf-8"
    ) as archivo:

        for clip in clips:

            archivo.write(
                f"file '{Path(clip).name}'\n"
            )

    video_base = OUTPUT / "video_base.mp4"

    ejecutar([
        ffmpeg,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(lista_final),
        "-c", "copy",
        str(video_base)
    ])

    # ------------------------------------------------------
    # MÚSICA Y MEZCLA
    # ------------------------------------------------------

    print("[FINAL] Mezclando música y narración...")

    musica = crear_musica()

    destino = OUTPUT / "fortaleza_short.mp4"

    ejecutar([
        ffmpeg,
        "-y",
        "-stream_loop", "-1",
        "-i", musica,
        "-i", str(video_base),
        "-filter_complex",
        (
            "[0:a]volume=0.10[musica];"
            "[1:a]volume=1.0[voz];"
            "[voz][musica]"
            "amix=inputs=2:duration=first:"
            "dropout_transition=2[audio]"
        ),
        "-map", "1:v:0",
        "-map", "[audio]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(destino)
    ])

    # ------------------------------------------------------
    # CRÉDITOS Y DESCRIPCIÓN
    # ------------------------------------------------------

    guardar_creditos(todas_las_fuentes)

    creditos = "\n\nFUENTES VISUALES:\n"

    for elemento in todas_las_fuentes:

        creditos += (
            f"{elemento['autor']} | "
            f"{elemento['licencia']} | "
            f"{elemento['url']}\n"
        )

    if todas_las_fuentes:

        guion["descripcion"] = (
            guion.get("descripcion", "")
            + creditos
        )

        with open(
            "guion.json",
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
    # VALIDACIÓN FINAL
    # ------------------------------------------------------

    if not destino.exists():

        raise FileNotFoundError(
            "No se generó el video final."
        )

    tamano = destino.stat().st_size

    if tamano <= 0:

        raise RuntimeError(
            "El video final está vacío."
        )

    if tamano > 90 * 1024 * 1024:

        raise RuntimeError(
            "El video supera el límite de 90 MB."
        )

    with destino.open("rb") as archivo:

        cabecera = archivo.read(16)

    if b"ftyp" not in cabecera:

        raise RuntimeError(
            "El archivo final no tiene una cabecera MP4 válida."
        )

    print("\n" + "=" * 55)
    print("FORTALEZA MEDIA AI 4.0")
    print("PRODUCCIÓN FINALIZADA")
    print("=" * 55)
    print("Archivo:", destino)
    print("Tamaño:", round(tamano / 1048576, 2), "MB")
    print("Fotografías:", len(todas_las_fuentes))
    print("Escenas:", len(escenas))
    print("=" * 55)


# ==========================================================
# EJECUCIÓN DIRECTA
# ==========================================================

if __name__ == "__main__":

    asyncio.run(crear_video())
