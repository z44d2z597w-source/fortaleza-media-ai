import asyncio
import os
import subprocess
import textwrap

import edge_tts
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ANCHO = 1080
ALTO = 1920

def crear_imagen(titulo, narracion):
    imagen = Image.new("RGB", (ANCHO, ALTO), "#101827")
    dibujo = ImageDraw.Draw(imagen)

    titulo_font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 76
    )
    texto_font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 43
    )

    dibujo.text((90, 400), "FORTALEZA MEDIA AI",
                fill="#55C8FF", font=texto_font)

    dibujo.multiline_text(
        (90, 550),
        textwrap.fill(titulo, width=22),
        fill="white",
        font=titulo_font,
        spacing=25
    )

    dibujo.multiline_text(
        (90, 950),
        textwrap.fill(narracion, width=32),
        fill="#DCE6F2",
        font=texto_font,
        spacing=25
    )

    os.makedirs("output", exist_ok=True)
    imagen.save("output/escena.png")


async def crear_video():
    if not os.path.exists("guion.json"):
        raise FileNotFoundError("No se encontró guion.json")

    import json

    with open("guion.json", encoding="utf-8") as archivo:
        guion = json.load(archivo)

    titulo = guion["titulo"]
    narracion = " ".join(
        escena["narracion"] for escena in guion["escenas"]
    )

    crear_imagen(titulo, narracion)

    voz = edge_tts.Communicate(
        narracion,
        voice="es-MX-DaliaNeural"
    )

    await voz.save("output/voz.mp3")

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    comando = [
        ffmpeg, "-y",
        "-loop", "1",
        "-i", "output/escena.png",
        "-i", "output/voz.mp3",
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "output/fortaleza_short.mp4"
    ]

    subprocess.run(comando, check=True)

    print("VIDEO CREADO CORRECTAMENTE")


if __name__ == "__main__":
    asyncio.run(crear_video())