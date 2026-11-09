import asyncio
from video_engine import guardar_guion
from render_video import crear_video

async def iniciar_fortaleza():
    print("FORTALEZA MEDIA AI")
    print("Preparando producción...")

    tema = "Misterios del océano"

    guion = guardar_guion(tema)
    print("Guion creado:", guion["titulo"])

    await crear_video()

    print("Producción finalizada.")

if __name__ == "__main__":
    asyncio.run(iniciar_fortaleza())