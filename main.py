
import asyncio
import json
import os

from topic_engine import descubrir_tema
from render_video import crear_video


def guardar_guion_inteligente():
    print("=" * 50)
    print("FORTALEZA MEDIA AI 4.0")
    print("MOTOR INTELIGENTE DE CONTENIDO")
    print("=" * 50)

    print("Buscando un tema nuevo...")

    guion = descubrir_tema()

    if not guion or not guion.get("escenas"):
        raise RuntimeError("No se pudo crear un guion válido.")

    os.makedirs("output", exist_ok=True)

    with open("guion.json", "w", encoding="utf-8") as archivo:
        json.dump(
            guion,
            archivo,
            ensure_ascii=False,
            indent=4
        )

    print("Tema seleccionado:", guion["titulo"])
    print("Escenas:", len(guion["escenas"]))
    print("Fuente:", guion.get("fuente_informacion", "No disponible"))

    return guion


async def iniciar_fortaleza():
    guion = guardar_guion_inteligente()

    print("-" * 50)
    print("INICIANDO RENDERIZADO")
    print("-" * 50)

    await crear_video()

    archivo = "output/fortaleza_short.mp4"

    if not os.path.isfile(archivo):
        raise FileNotFoundError("No se generó el video.")

    tamano = os.path.getsize(archivo)

    if tamano == 0:
        raise RuntimeError("El video generado está vacío.")

    print("=" * 50)
    print("PRODUCCIÓN FINALIZADA")
    print("Tema:", guion["titulo"])
    print("Archivo:", archivo)
    print("Tamaño:", round(tamano / (1024 * 1024), 2), "MB")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(iniciar_fortaleza())
