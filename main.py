import asyncio
import json
import os
import sys
import traceback
from pathlib import Path

from video_engine import obtener_guion_hoy
from render_short import renderizar_short


CARPETA_SALIDA = Path("output")
CARPETA_TEMP = Path("temp")


async def main():
    print("==========================================")
    print("       FORTALEZA MEDIA AI 2.0")
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

        print("\n[PASO 2] Guardando información del guion...")

        with open(
            CARPETA_TEMP / "guion_actual.json",
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

        if not video or not Path(video).exists():
            raise RuntimeError("No se encontró el video terminado.")

        print("\n[PASO 4] Verificando archivo...")

        if Path(video).stat().st_size < 100000:
            raise RuntimeError("El archivo generado es demasiado pequeño.")

        print("\n==========================================")
        print("       PROCESO COMPLETADO")
        print("==========================================")
        print(f"VIDEO: {video}")
        print("El video está listo para revisión.")

    except Exception as error:
        print("\n==========================================")
        print("       ERROR EN EL PROCESO")
        print("==========================================")
        print(str(error))
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())