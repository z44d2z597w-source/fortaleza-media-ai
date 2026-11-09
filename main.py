
import asyncio
import os
from video_engine import guardar_guion
from render_video import crear_video


async def iniciar_fortaleza():
    print("=" * 45)
    print("       FORTALEZA MEDIA AI")
    print("=" * 45)

    print("Iniciando producción automática...")

    # Seleccionar automáticamente el tema del día
    guion = guardar_guion()

    print("Guion creado:", guion["titulo"])
    print("Idioma:", guion["idioma"])
    print("Formato:", guion["formato"])

    # Generar el video
    await crear_video()

    archivo = "output/fortaleza_short.mp4"

    if not os.path.exists(archivo):
        raise FileNotFoundError(
            "No se generó el archivo de video."
        )

    tamano = os.path.getsize(archivo)

    if tamano == 0:
        raise RuntimeError("El video está vacío.")

    print("-" * 45)
    print("PRODUCCIÓN FINALIZADA")
    print("Archivo:", archivo)
    print("Tamaño:", round(tamano / (1024 * 1024), 2), "MB")
    print("=" * 45)


if __name__ == "__main__":
    asyncio.run(iniciar_fortaleza())
