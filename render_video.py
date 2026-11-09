
import asyncio
import html
import json
import math
import os
import re
import subprocess
import wave
from array import array
from io import BytesIO

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

# ==========================================
# FORTALEZA MEDIA AI 3.0
# MOTOR CINEMATOGRAFICO AUTOMATICO
# ==========================================

ANCHO = 1080
ALTO = 1920
FPS = 30

VOZ = "es-MX-DaliaNeural"
VELOCIDAD_VOZ = "+3%"

OUTPUT = "output"
RECURSOS = "output/recursos"

IMAGENES_POR_ESCENA = 3
MAX_ESCENAS = 12

PALETAS = [
    ("#071426", "#123D60", "#39B8D8"),
    ("#180D2C", "#43205E", "#B56CFF"),
    ("#111B18", "#245B43", "#65D6A0"),
    ("#29100D", "#74301F", "#FFAD64"),
    ("#10152C", "#293D75", "#82A7FF"),
    ("#25152B", "#63344E", "#FF83AE")
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
    "que", "sus", "sus", "hay", "más", "muy",
    "hoy", "sobre", "nuestro", "nuestra"
}


# ==========================================
# UTILIDADES
# ==========================================

def fuente(tamano, negrita=False):

    rutas = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if negrita else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",

        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if negrita else
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
    ]

    for ruta in rutas:
        if os.path.exists(ruta):
            return ImageFont.truetype(ruta, tamano)

    return ImageFont.load_default()


def color_rgb(color):

    color = color.lstrip("#")

    return tuple(
        int(color[i:i + 2], 16)
        for i in (0, 2, 4)
    )


def ejecutar(comando):

    resultado = subprocess.run(
        comando,
        capture_output=True,
        text=True
    )

    if resultado.returncode != 0:

        raise RuntimeError(
            "ERROR DE FFmpeg:\n"
            + resultado.stderr[-4000:]
        )


def duracion_audio(ffmpeg, archivo):

    resultado = subprocess.run(
        [ffmpeg, "-i", archivo],
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


# ==========================================
# BUSQUEDA AUTOMATICA DE FOTOGRAFIAS
# WIKIMEDIA COMMONS
# ==========================================

def limpiar_html(texto):

    texto = re.sub(r"<[^>]+>", "", str(texto))

    return html.unescape(texto).strip()


def crear_busqueda(titulo, narracion):

    palabras = re.findall(
        r"[a-zA-ZáéíóúÁÉÍÓÚñÑ]{4,}",
        titulo + " " + narracion
    )

    palabras = [
        palabra for palabra in palabras
        if palabra.lower() not in STOPWORDS
    ]

    resultado = []

    for palabra in palabras:
        if palabra.lower() not in [
            x.lower() for x in resultado
        ]:
            resultado.append(palabra)

    return " ".join(resultado[:9])


def buscar_fotografias(titulo, narracion, numero):

    os.makedirs(RECURSOS, exist_ok=True)

    consulta = crear_busqueda(titulo, narracion)

    print("Buscando imágenes:", consulta)

    url_api = "https://commons.wikimedia.org/w/api.php"

    parametros = {
        "action": "query",
        "generator": "search",
        "gsrsearch": consulta,
        "gsrnamespace": 6,
        "gsrlimit": 12,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 1600,
        "format": "json"
    }

    encabezados = {
        "User-Agent": "FortalezaMediaAI/3.0 (video production)"
    }

    try:

        respuesta = requests.get(
            url_api,
            params=parametros,
            headers=encabezados,
            timeout=30
        )

        respuesta.raise_for_status()

        paginas = respuesta.json().get(
            "query", {}
        ).get("pages", {})

    except Exception as error:

        print("No fue posible buscar imágenes:", error)

        return []

    resultados = []

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

        if not imagen_url:
            continue

        try:

            descarga = requests.get(
                imagen_url,
                headers=encabezados,
                timeout=35
            )

            descarga.raise_for_status()

            imagen = Image.open(
                BytesIO(descarga.content)
            ).convert("RGB")

            if imagen.width < 500 or imagen.height < 400:
                continue

            ruta = (
                f"{RECURSOS}/escena_{numero:02d}_"
                f"{len(resultados):02d}.jpg"
            )

            imagen.save(
                ruta,
                "JPEG",
                quality=91
            )

            metadatos = info.get("extmetadata", {})

            autor = limpiar_html(
                metadatos.get("Artist", {}).get("value", "Autor no indicado")
            )

            licencia = limpiar_html(
                metadatos.get("LicenseShortName", {}).get(
                    "value", "Licencia no indicada"
                )
            )

            pagina_url = info.get(
                "descriptionurl", imagen_url
            )

            resultados.append({
                "archivo": ruta,
                "autor": autor,
                "licencia": licencia,
                "url": pagina_url
            })

            print("Fotografía descargada:", len(resultados))

            if len(resultados) >= IMAGENES_POR_ESCENA:
                break

        except Exception as error:

            print("Imagen omitida:", error)

    return resultados


# ==========================================
# FONDOS Y DISEÑO VISUAL
# ==========================================

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

    for i in range(10):

        radio = 100 + i * 75

        x = 800 - (numero * 95) % 350
        y = 250 + i * 175

        dibujo.ellipse(
            (
                x - radio,
                y - radio,
                x + radio,
                y + radio
            ),
            outline=(*rgb, max(12, 65 - i * 5)),
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

    imagen = ImageEnhance.Color(imagen).enhance(1.18)

    imagen = ImageEnhance.Contrast(imagen).enhance(1.12)

    imagen = ImageEnhance.Brightness(imagen).enhance(0.72)

    # Oscurecer bordes para mejorar la lectura
    capa = Image.new(
        "RGBA",
        (ANCHO, ALTO),
        (0, 0, 0, 0)
    )

    dibujo = ImageDraw.Draw(capa)

    dibujo.rectangle(
        (0, 0, ANCHO, 400),
        fill=(0, 0, 0, 85)
    )

    dibujo.rectangle(
        (0, 1250, ANCHO, ALTO),
        fill=(0, 0, 0, 115)
    )

    imagen = Image.alpha_composite(
        imagen.convert("RGBA"),
        capa
    ).convert("RGB")

    return imagen


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

    # Marca
    dibujo.text(
        (70, 105),
        "FORTALEZA MEDIA AI",
        font=fuente(29, True),
        fill="white"
    )

    dibujo.rounded_rectangle(
        (70, 155, 300, 165),
        radius=5,
        fill=acento
    )

    # Título inicial
    if numero == 0:

        palabras = titulo.upper().split()

        lineas = []
        actual = ""

        for palabra in palabras:

            prueba = (actual + " " + palabra).strip()

            if dibujo.textbbox(
                (0, 0),
                prueba,
                font=fuente(75, True)
            )[2] < 900:

                actual = prueba

            else:

                if actual:
                    lineas.append(actual)

                actual = palabra

        if actual:
            lineas.append(actual)

        dibujo.multiline_text(
            (ANCHO // 2, 330),
            "\n".join(lineas),
            font=fuente(75, True),
            fill="white",
            anchor="mm",
            align="center",
            spacing=22,
            stroke_width=3,
            stroke_fill="#000000"
        )

    # Indicador de escenas
    dibujo.text(
        (ANCHO - 75, 105),
        f"{numero + 1:02d}/{total:02d}",
        font=fuente(30, True),
        fill=acento,
        anchor="ra"
    )

    ruta = f"{OUTPUT}/visual_{numero:02d}.png"

    imagen.save(
        ruta,
        quality=95
    )

    return ruta


# ==========================================
# VOZ Y SINCRONIZACION DE PALABRAS
# ==========================================

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
                "fin": inicio + duracion
            })

    if not audio:
        raise RuntimeError("No se recibió audio de la voz.")

    with open(ruta, "wb") as archivo:
        archivo.write(audio)

    return palabras


# ==========================================
# SUBTITULOS ANIMADOS POR FRASES
# ==========================================

def crear_imagen_subtitulo(palabras, numero, acento):

    imagen = Image.new(
        "RGBA",
        (ANCHO, 430),
        (0, 0, 0, 0)
    )

    dibujo = ImageDraw.Draw(imagen)

    frase = " ".join(
        palabra["texto"]
        for palabra in palabras
    )

    font = fuente(55, True)

    # Fondo redondeado
    dibujo.rounded_rectangle(
        (45, 65, 1035, 365),
        radius=38,
        fill=(0, 0, 0, 175),
        outline=(*color_rgb(acento), 230),
        width=4
    )

    # Distribución en líneas
    palabras_texto = frase.split()

    lineas = []
    actual = ""

    for palabra in palabras_texto:

        prueba = (actual + " " + palabra).strip()

        if dibujo.textbbox(
            (0, 0),
            prueba,
            font=font
        )[2] <= 880:

            actual = prueba

        else:

            if actual:
                lineas.append(actual)

            actual = palabra

    if actual:
        lineas.append(actual)

    lineas = lineas[:3]

    alto = len(lineas) * 72

    y = 215 - alto // 2

    for indice, linea in enumerate(lineas):

        dibujo.text(
            (ANCHO // 2, y + indice * 78),
            linea,
            font=font,
            fill="white",
            anchor="mm",
            stroke_width=2,
            stroke_fill="#000000"
        )

    # Barra decorativa
    dibujo.rounded_rectangle(
        (390, 385, 690, 395),
        radius=5,
        fill=acento
    )

    ruta = (
        f"{OUTPUT}/caption_{numero:03d}.png"
    )

    imagen.save(ruta)

    return ruta


def crear_subtitulos(palabras, duracion, numero, acento):

    if not palabras:

        return []

    grupos = []

    grupo = []

    for palabra in palabras:

        grupo.append(palabra)

        texto_actual = " ".join(
            p["texto"] for p in grupo
        )

        if len(grupo) >= 5 or len(texto_actual) >= 29:

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
            grupo[-1]["fin"] + 0.12
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
            "fin": fin
        })

    return resultado


# ==========================================
# ANIMACION DE FOTOGRAFIAS
# ==========================================

def crear_toma(
    ffmpeg,
    imagen,
    destino,
    duracion,
    numero
):

    # Movimientos diferentes para cada toma
    if numero % 4 == 0:

        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"

    elif numero % 4 == 1:

        x = "iw/2-(iw/zoom/2)+on*0.12"
        y = "ih/2-(ih/zoom/2)"

    elif numero % 4 == 2:

        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)+on*0.10"

    else:

        x = "iw/2-(iw/zoom/2)-on*0.10"
        y = "ih/2-(ih/zoom/2)"

    filtro = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "zoompan="
        "z='min(zoom+0.0008,1.15)':"
        f"x='{x}':"
        f"y='{y}':"
        "d=1:"
        "s=1080x1920:"
        "fps=30,"
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
        "-crf", "21",
        "-pix_fmt", "yuv420p",
        destino
    ])


# ==========================================
# MUSICA AMBIENTAL ORIGINAL
# ==========================================

def crear_musica():

    ruta = f"{OUTPUT}/musica_ambiente.wav"

    frecuencia = 44100
    duracion = 120

    datos = array("h")

    for i in range(frecuencia * duracion):

        t = i / frecuencia

        modulacion = (
            0.65
            + 0.35 * math.sin(
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

    with wave.open(ruta, "wb") as archivo:

        archivo.setnchannels(2)
        archivo.setsampwidth(2)
        archivo.setframerate(frecuencia)
        archivo.writeframes(datos.tobytes())

    return ruta


# ==========================================
# CREDITOS DE IMAGENES
# ==========================================

def guardar_creditos(fuentes):

    ruta = f"{OUTPUT}/creditos_imagenes.txt"

    with open(ruta, "w", encoding="utf-8") as archivo:

        archivo.write(
            "FUENTES VISUALES - FORTALEZA MEDIA AI\n\n"
        )

        for fuente_imagen in fuentes:

            archivo.write(
                f"Autor: {fuente_imagen['autor']}\n"
            )

            archivo.write(
                f"Licencia: {fuente_imagen['licencia']}\n"
            )

            archivo.write(
                f"Fuente: {fuente_imagen['url']}\n\n"
            )

    return ruta


# ==========================================
# PRODUCCION PRINCIPAL
# ==========================================

async def crear_video():

    os.makedirs(OUTPUT, exist_ok=True)
    os.makedirs(RECURSOS, exist_ok=True)

    if not os.path.exists("guion.json"):

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
            "El guion no contiene narración."
        )

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    clips = []
    todas_las_fuentes = []

    print("=" * 45)
    print("FORTALEZA MEDIA AI 3.0")
    print("INICIANDO PRODUCCION CINEMATOGRAFICA")
    print("=" * 45)

    for numero, escena in enumerate(escenas):

        narracion = str(
            escena["narracion"]
        ).strip()

        print(
            f"\nESCENA {numero + 1}/{len(escenas)}"
        )

        # Buscar fotografías reales
        fotografias = buscar_fotografias(
            titulo,
            narracion,
            numero
        )

        todas_las_fuentes.extend(fotografias)

        # Crear respaldo visual si no hay fotografías
        if not fotografias:

            imagen = crear_escena(
                titulo,
                numero,
                len(escenas)
            )

            fotografias_archivos = [imagen]

        else:

            fotografias_archivos = [
                foto["archivo"]
                for foto in fotografias
            ]

            imagen = crear_escena(
                titulo,
                numero,
                len(escenas),
                fotografias_archivos[0]
            )

            fotografias_archivos[0] = imagen

        # Crear voz y obtener tiempos reales de palabras
        audio = f"{OUTPUT}/voz_{numero:02d}.mp3"

        palabras = await crear_voz(
            narracion,
            audio
        )

        duracion = duracion_audio(
            ffmpeg,
            audio
        )

        acento = PALETAS[
            numero % len(PALETAS)
        ][2]

        # Crear subtítulos sincronizados
        subtitulos = crear_subtitulos(
            palabras,
            duracion,
            numero,
            acento
        )

        # Distribuir fotografías durante la narración
        cantidad = len(fotografias_archivos)

        duracion_toma = duracion / cantidad

        tomas = []

        for indice, fotografia in enumerate(
            fotografias_archivos
        ):

            clip_toma = (
                f"{OUTPUT}/toma_{numero:02d}_"
                f"{indice:02d}.mp4"
            )

            crear_toma(
                ffmpeg,
                fotografia,
                clip_toma,
                duracion_toma,
                numero + indice
            )

            tomas.append(clip_toma)

        # Unir las tomas visuales de esta escena
        lista_tomas = (
            f"{OUTPUT}/lista_tomas_{numero:02d}.txt"
        )

        with open(
            lista_tomas,
            "w",
            encoding="utf-8"
        ) as archivo:

            for toma in tomas:

                archivo.write(
                    f"file '{os.path.basename(toma)}'\n"
                )

        video_visual = (
            f"{OUTPUT}/visual_final_{numero:02d}.mp4"
        )

        ejecutar([
            ffmpeg,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", lista_tomas,
            "-c", "copy",
            video_visual
        ])

        # Construir superposiciones de subtítulos
        comando = [
            ffmpeg,
            "-y",
            "-i", video_visual,
            "-i", audio
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

            inicio = subtitulo["inicio"]
            fin = subtitulo["fin"]

            filtros.append(
                f"{actual}[{entrada}:v]"
                "overlay=0:1320:"
                f"enable='between(t\\,{inicio:.3f}\\,{fin:.3f})'"
                f"{salida}"
            )

            actual = salida

        if filtros:

            filtro_final = ";".join(filtros)

        else:

            filtro_final = "[0:v]null[vfinal]"
            actual = "[vfinal]"

        clip_final = (
            f"{OUTPUT}/escena_final_{numero:02d}.mp4"
        )

        comando.extend([
            "-filter_complex",
            filtro_final,
            "-map", actual,
            "-map", "1:a",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "21",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "160k",
            "-shortest",
            "-movflags", "+faststart",
            clip_final
        ])

        ejecutar(comando)

        clips.append(clip_final)

    # ======================================
    # UNION FINAL
    # ======================================

    print("\nUniendo escenas...")

    lista = f"{OUTPUT}/lista_final.txt"

    with open(
        lista,
        "w",
        encoding="utf-8"
    ) as archivo:

        for clip in clips:

            archivo.write(
                f"file '{os.path.basename(clip)}'\n"
            )

    video_base = f"{OUTPUT}/video_base.mp4"

    ejecutar([
        ffmpeg,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", lista,
        "-c", "copy",
        video_base
    ])

    # Música ambiental
    musica = crear_musica()

    destino = f"{OUTPUT}/fortaleza_short.mp4"

    ejecutar([
        ffmpeg,
        "-y",
        "-stream_loop", "-1",
        "-i", musica,
        "-i", video_base,
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
        destino
    ])

    # Créditos
    guardar_creditos(todas_las_fuentes)

    # Incorporar créditos a la descripción de YouTube
    if todas_las_fuentes:

        creditos = "\n\nFUENTES DE IMAGENES:\n"

        for fuente_imagen in todas_las_fuentes:

            creditos += (
                f"{fuente_imagen['autor']} | "
                f"{fuente_imagen['licencia']} | "
                f"{fuente_imagen['url']}\n"
            )

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

    # Verificación final
    if not os.path.exists(destino):

        raise FileNotFoundError(
            "No se generó el video final."
        )

    tamano = os.path.getsize(destino)

    if tamano == 0:

        raise RuntimeError(
            "El video final está vacío."
        )

    print("\n" + "=" * 45)
    print("PRODUCCION FINALIZADA")
    print("Archivo:", destino)
    print(
        "Tamaño:",
        round(tamano / 1048576, 2),
        "MB"
    )
    print("Fotografías:", len(todas_las_fuentes))
    print("=" * 45)


if __name__ == "__main__":

    asyncio.run(crear_video())
