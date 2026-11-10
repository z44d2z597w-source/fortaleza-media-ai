
import asyncio
import json
import sys
import traceback
from pathlib import Path

from video_engine import (
    obtener_guion_hoy,
    registrar_guion_completado,
)
from render_short import renderizar_short


CARPETA_SALIDA = Path("output")
CARPETA_TEMP = Path("temp")


async def main():
    print("==========================================")
    print("       FORTALEZA MEDIA AI")
    print("       GENERADOR DE YOUTUBE SHORTS")
    print("==========================================")

    try:
        CARPETA_SALIDA.mkdir(exist_ok=True)
        CARPETA_TEMP.mkdir(exist_ok=True)

        print("\n[PASO 1] Generando historia original...")

        guion = obtener_guion_hoy()

        print(f"[SERIE] {guion['titulo_serie']}")
        print(f"[EPISODIO] {guion['parte']} de 5")
        print(f"[TÍTULO] {guion['titulo']}")
        print(f"[ESTILO] {guion['estilo_visual']}")

        print("\n[PASO 2] Guardando información del guion...")

        archivo_guion = CARPETA_TEMP / "guion_actual.json"

        with open(
            archivo_guion,
            "w",
            encoding="utf-8",
        ) as archivo:
            json.dump(
                guion,
                archivo,
                ensure_ascii=False,
                indent=2,
            )

        print("\n[PASO 3] Creando video...")

        video = await renderizar_short(guion)

        if not video:
            raise RuntimeError(
                "El renderizador no devolvió una ruta de video."
            )

        ruta_video = Path(video)

        if not ruta_video.exists():
            raise RuntimeError(
                "No se encontró el video terminado."
            )

        if ruta_video.stat().st_size < 100000:
            raise RuntimeError(
                "El archivo generado es demasiado pequeño."
            )

        print("\n[PASO 4] Registrando episodio completado...")

        registrar_guion_completado(guion)

        print("\n==========================================")
        print("       PROCESO COMPLETADO")
        print("==========================================")
        print(f"TÍTULO: {guion['titulo']}")
        print(f"VIDEO: {ruta_video}")
        print("Episodio registrado correctamente.")

    except Exception as error:
        print("\n==========================================")
        print("       ERROR EN EL PROCESO")
        print("==========================================")
        print(str(error))
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
