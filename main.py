
import asyncio
import json
import sys
from pathlib import Path

from video_engine import obtener_guion_hoy
from render_short import renderizar_short


CARPETA_TEMP = Path("temp")
CARPETA_TEMP.mkdir(exist_ok=True)


def guardar_guion_actual(guion):
    archivo = CARPETA_TEMP / "guion_actual.json"

    temporal = CARPETA_TEMP / "guion_actual.tmp"

    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(
            guion,
            f,
            ensure_ascii=False,
            indent=2
        )

    temporal.replace(archivo)

    print(f"[GUION] Guardado en {archivo}")


async def main():
    print("==========================================")
    print("       FORTALEZA MEDIA AI")
    print("       SISTEMA DE SHORTS 3.0")
    print("==========================================")

    try:
        print("\n[PASO 1] Generando historia...")

        guion = obtener_guion_hoy()

        if not guion:
            raise RuntimeError("No se pudo generar el guion.")

        print(f"[SERIE] {guion['titulo_serie']}")
        print(f"[TITULO] {guion['titulo']}")
        print(f"[EPISODIO] {guion['parte']} de 5")
        print(f"[ESTILO] {guion['estilo_visual']}")

        guardar_guion_actual(guion)

        print("\n[PASO 2] Preparando narración y fondos...")

        video = await renderizar_short(guion)

        if not video:
            raise RuntimeError("El editor no devolvió un video.")

        if not Path(video).exists():
            raise RuntimeError(
                f"No se encontró el video generado: {video}"
            )

        print("\n==========================================")
        print("[ÉXITO] SHORT GENERADO")
        print(f"[VIDEO] {video}")
        print(f"[ESTILO] {guion['estilo_visual']}")
        print("==========================================")

    except Exception as error:
        print("\n[ERROR] EL PROCESO NO PUDO COMPLETARSE")
        print(str(error))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
