
import asyncio
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from video_engine import guardar_guion
from render_video import crear_video


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
GUION_FILE = BASE_DIR / "guion.json"
PRODUCCION_FILE = OUTPUT_DIR / "produccion.json"

ARCHIVOS_SALIDA = [
    OUTPUT_DIR / "fortaleza_final.mp4",
    OUTPUT_DIR / "fortaleza_short.mp4",
    OUTPUT_DIR / "fortaleza_video.mp4",
]


def imprimir_encabezado():
    print("=" * 60)
    print("             FORTALEZA MEDIA AI")
    print("          SISTEMA DE PRODUCCIÓN")
    print("=" * 60)


def cargar_y_validar_guion():
    if not GUION_FILE.exists():
        raise FileNotFoundError(
            "No se encontró guion.json después de ejecutar el motor editorial."
        )

    with GUION_FILE.open("r", encoding="utf-8") as archivo:
        guion = json.load(archivo)

    if not isinstance(guion, dict):
        raise ValueError("El guion generado no tiene una estructura válida.")

    titulo = str(guion.get("titulo", "")).strip()
    escenas = guion.get("escenas", [])

    if not titulo:
        raise ValueError("El guion no contiene un título.")

    if not isinstance(escenas, list) or not escenas:
        raise ValueError("El guion no contiene escenas para producir.")

    for numero, escena in enumerate(escenas, start=1):
        if not isinstance(escena, dict):
            raise ValueError(f"La escena {numero} tiene un formato inválido.")

        narracion = str(escena.get("narracion", "")).strip()

        if not narracion:
            raise ValueError(
                f"La escena {numero} no contiene narración."
            )

    return guion


def localizar_video(resultado=None):
    candidatos = []

    if isinstance(resultado, (str, Path)):
        candidatos.append(Path(resultado))

    elif isinstance(resultado, dict):
        for clave in ("archivo", "output", "path", "video"):
            valor = resultado.get(clave)
            if valor:
                candidatos.append(Path(valor))

    candidatos.extend(ARCHIVOS_SALIDA)

    for archivo in candidatos:
        if not archivo.is_absolute():
            archivo = BASE_DIR / archivo

        if archivo.is_file() and archivo.stat().st_size > 0:
            return archivo

    raise FileNotFoundError(
        "El renderizador terminó, pero no se encontró ningún MP4 válido "
        "en la carpeta output."
    )


def guardar_informe(guion, video):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    tamano = video.stat().st_size
    formato = str(guion.get("formato", "YouTube Shorts 9:16"))

    informe = {
        "proyecto": "FORTALEZA MEDIA AI",
        "estado": "produccion_completada",
        "titulo": guion.get("titulo", ""),
        "descripcion": guion.get("descripcion", ""),
        "idioma": guion.get("idioma", "es-MX"),
        "formato": formato,
        "escenas": len(guion.get("escenas", [])),
        "archivo": str(video.relative_to(BASE_DIR)),
        "tamano_bytes": tamano,
        "tamano_mb": round(tamano / (1024 * 1024), 2),
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "publicado": False,
    }

    temporal = PRODUCCION_FILE.with_suffix(".tmp")

    with temporal.open("w", encoding="utf-8") as archivo:
        json.dump(
            informe,
            archivo,
            ensure_ascii=False,
            indent=4
        )

    temporal.replace(PRODUCCION_FILE)

    return informe


async def iniciar_fortaleza():
    imprimir_encabezado()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("\n[1/5] Iniciando motor editorial...")

    guion_generado = guardar_guion()

    if guion_generado is None:
        print("El motor editorial no devolvió el guion.")
        guion = cargar_y_validar_guion()
    else:
        guion = guion_generado

    print("[2/5] Validando guion...")
    guion = cargar_y_validar_guion()

    print("\nTÍTULO:", guion["titulo"])
    print("IDIOMA:", guion.get("idioma", "es-MX"))
    print("FORMATO:", guion.get("formato", "No especificado"))
    print("ESCENAS:", len(guion["escenas"]))

    print("\n[3/5] Iniciando producción audiovisual...")
    resultado = await crear_video()

    print("\n[4/5] Verificando archivo de video...")
    video = localizar_video(resultado)

    tamano = video.stat().st_size

    if tamano < 1024:
        raise RuntimeError("El archivo generado es demasiado pequeño.")

    print("Video:", video)
    print("Tamaño:", round(tamano / (1024 * 1024), 2), "MB")

    print("\n[5/5] Guardando informe de producción...")
    informe = guardar_informe(guion, video)

    print("\n" + "=" * 60)
    print("          PRODUCCIÓN FINALIZADA")
    print("=" * 60)
    print("Título:", informe["titulo"])
    print("Formato:", informe["formato"])
    print("Archivo:", informe["archivo"])
    print("Peso:", informe["tamano_mb"], "MB")
    print("Publicado: NO")
    print("Informe:", PRODUCCION_FILE)
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(iniciar_fortaleza())

    except KeyboardInterrupt:
        print("\nProducción interrumpida.")
        sys.exit(130)

    except Exception as error:
        print("\nERROR EN FORTALEZA MEDIA AI")
        print(str(error))
        traceback.print_exc()
        sys.exit(1)
