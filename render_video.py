
import asyncio
import json
import math
import os
import subprocess
import wave
import textwrap
from array import array

import edge_tts
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageOps

ANCHO = 1080
ALTO = 1920
FPS = 30
VOZ = "es-MX-DaliaNeural"

OUTPUT = "output"
MAX_ESCENAS = 12

PALETAS = [
    ("#071426", "#123D60", "#39B8D8"),
    ("#180D2C", "#43205E", "#B56CFF"),
    ("#111B18", "#245B43", "#65D6A0"),
    ("#29100D", "#74301F", "#FFAD64"),
    ("#10152C", "#293D75", "#82A7FF"),
    ("#25152B", "#63344E", "#FF83AE"),
]


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


def texto_centrado(dibujo, texto, y, font, color, ancho=850):
    palabras = texto.split()
    lineas = []
    actual = ""

    for palabra in palabras:
        prueba = (actual + " " + palabra).strip()
        if dibujo.textbbox((0, 0), prueba, font=font)[2] <= ancho:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = palabra

    if actual:
        lineas.append(actual)

    texto_final = "\n".join(lineas)

    dibujo.multiline_text(
        (ANCHO // 2, y),
        texto_final,
        font=font,
        fill=color,
        anchor="mm",
        align="center",
        spacing=24,
        stroke_width=2,
        stroke_fill="#101010"
    )


def crear_fondo(numero):
    oscuro, medio, acento = PALETAS[numero % len(PALETAS)]

    gradiente = Image.linear_gradient("L").resize((ANCHO, ALTO))
    imagen = ImageOps.colorize(
        gradiente,
        black=oscuro,
        white=medio
    ).convert("RGB")

    dibujo = ImageDraw.Draw(imagen, "RGBA")

    # Formas geométricas decorativas
    desplazamiento = (numero * 137) % 500

    for i in range(7):
        radio = 100 + i * 65
        x = 820 - desplazamiento // 3
        y = 330 + i * 180

        dibujo.ellipse(
            (x - radio, y - radio, x + radio, y + radio),
            outline=(*ImageColor(acento), max(15, 65 - i * 6)),
            width=5
        )

    dibujo.rounded_rectangle(
        (55, 170, 1025, 1750),
        radius=48,
        outline=(255, 255, 255, 45),
        width=3
    )

    return imagen


def ImageColor(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(
        int(hex_color[i:i + 2], 16)
        for i in (0, 2, 4)
    )


def crear_escena(titulo, narracion, numero, total):
    imagen = crear_fondo(numero)
    dibujo = ImageDraw.Draw(imagen)

    dibujo.text(
        (ANCHO // 2, 235),
        "FORTALEZA MEDIA AI",
        font=fuente(34, True),
        fill="#FFFFFF",
        anchor="mm"
    )

    dibujo.rounded_rectangle(
        (390, 315, 690, 325),
        radius=5,
        fill="#55C8FF"
    )

    if numero == 0:
        texto_centrado(
            dibujo,
            titulo.upper(),
            650,
            fuente(76, True),
            "#FFFFFF"
        )

        texto_centrado(
            dibujo,
            narracion,
            1120,
            fuente(49, True),
            "#E4F5FF"
        )
    else:
        texto_centrado(
            dibujo,
            narracion,
            920,
            fuente(61, True),
            "#FFFFFF"
        )

    dibujo.text(
        (ANCHO // 2, 1580),
        f"ESCENA {numero + 1:02d} / {total:02d}",
        font=fuente(30, True),
        fill="#55C8FF",
        anchor="mm"
    )

    dibujo.text(
        (ANCHO // 2, 1660),
        "DESCUBRE • EXPLORA • COMPARTE",
        font=fuente(24),
        fill="#D6E2F0",
        anchor="mm"
    )

    ruta = f"{OUTPUT}/escena_{numero:02d}.png"
    imagen.save(ruta)
    return ruta


def crear_musica():
    ruta = f"{OUTPUT}/ambiente.wav"
    frecuencia = 44100
    duracion = 30
    cantidad = frecuencia * duracion

    datos = array("h")

    for i in range(cantidad):
        t = i / frecuencia

        modulacion = 0.65 + 0.35 * math.sin(
            2 * math.pi * 0.035 * t
        )

        sonido = (
            math.sin(2 * math.pi * 110 * t) * 0.28
            + math.sin(2 * math.pi * 164.81 * t) * 0.20
            + math.sin(2 * math.pi * 220 * t) * 0.12
        )

        valor = int(32767 * 0.055 * modulacion * sonido)

        datos.append(valor)
        datos.append(valor)

    with wave.open(ruta, "wb") as archivo:
        archivo.setnchannels(2)
        archivo.setsampwidth(2)
        archivo.setframerate(frecuencia)
        archivo.writeframes(datos.tobytes())

    return ruta


async def crear_voz(texto, ruta):
    comunicacion = edge_tts.Communicate(
        texto,
        voice=VOZ,
        rate="+3%",
        pitch="+0Hz"
    )

    await comunicacion.save(ruta)


def ejecutar(comando):
    subprocess.run(
        comando,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE
    )


async def crear_video():
    os.makedirs(OUTPUT, exist_ok=True)

    if not os.path.exists("guion.json"):
        raise FileNotFoundError("No se encontró guion.json")

    with open("guion.json", encoding="utf-8") as archivo:
        guion = json.load(archivo)

    titulo = str(guion.get("titulo", "Una historia sorprendente"))

    escenas = guion.get("escenas", [])

    escenas = [
        escena for escena in escenas
        if str(escena.get("narracion", "")).strip()
    ][:MAX_ESCENAS]

    if not escenas:
        raise ValueError("El guion no contiene escenas con narración.")

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    clips = []

    print("FORTALEZA MEDIA AI")
    print("Preparando escenas...")

    for numero, escena in enumerate(escenas):
        narracion = str(escena["narracion"]).strip()

        print(f"Creando escena {numero + 1}/{len(escenas)}")

        imagen = crear_escena(
            titulo,
            narracion,
            numero,
            len(escenas)
        )

        audio = f"{OUTPUT}/voz_{numero:02d}.mp3"
        clip = f"{OUTPUT}/clip_{numero:02d}.mp4"

        await crear_voz(narracion, audio)

        comando = [
            ffmpeg,
            "-y",
            "-loop", "1",
            "-framerate", str(FPS),
            "-i", imagen,
            "-i", audio,
            "-vf",
            (
                "zoompan="
                "z='min(zoom+0.0005,1.08)':"
                "x='iw/2-(iw/zoom/2)':"
                "y='ih/2-(ih/zoom/2)':"
                "d=1800:"
                "s=1080x1920:"
                "fps=30,"
                "format=yuv420p"
            ),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "160k",
            "-ar", "44100",
            "-shortest",
            "-movflags", "+faststart",
            clip
        ]

        ejecutar(comando)
        clips.append(clip)

    # Unir todas las escenas
    lista = f"{OUTPUT}/lista.txt"

    with open(lista, "w", encoding="utf-8") as archivo:
        for clip in clips:
            archivo.write(f"file '{os.path.basename(clip)}'\n")

    video_base = f"{OUTPUT}/video_base.mp4"

    ejecutar([
        ffmpeg,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", lista,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "160k",
        "-pix_fmt", "yuv420p",
        video_base
    ])

    # Crear ambiente musical original y mezclarlo con la voz
    musica = crear_musica()
    destino = f"{OUTPUT}/fortaleza_short.mp4"

    ejecutar([
        ffmpeg,
        "-y",
        "-stream_loop", "-1",
        "-i", musica,
        "-i", video_base,
        "-filter_complex",
        "[0:a]volume=0.12[musica];"
        "[1:a]volume=1.0[voz];"
        "[voz][musica]amix=inputs=2:duration=first:dropout_transition=2[audio]",
        "-map", "1:v:0",
        "-map", "[audio]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        destino
    ])

    print("VIDEO CREADO CORRECTAMENTE")
    print("Archivo:", destino)


if __name__ == "__main__":
    asyncio.run(crear_video())
