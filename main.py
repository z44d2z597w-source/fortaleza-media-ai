
import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path
from datetime import datetime, timezone

from video_engine import guardar_guion
from render_video import crear_video


# ==========================================================
# FORTALEZA MEDIA AI
# CONTROLADOR PRINCIPAL DE PRODUCCIÓN
# ==========================================================

NOMBRE = "FORTALEZA MEDIA AI"
VERSION = "4.0"

ARCHIVO_GUION = Path("guion.json")
CARPETA_OUTPUT = Path("output")
ARCHIVO_VIDEO = CARPETA_OUTPUT / "fortaleza_short.mp4"
ARCHIVO_ESTADO = CARPETA_OUTPUT / "estado_produccion.json"

# Límite preventivo para evitar archivos demasiado grandes
# antes de enviarlos al sistema de publicación.
MAX_MB = float(os.getenv("FORTALEZA_MAX_MB", "85"))
MAX_BYTES = int(MAX_MB * 1024 * 1024)

IDIOMA_PERMITIDO = "es-MX"


# ==========================================================
# REGISTRO DE PRODUCCIÓN
# ==========================================================

def registrar(mensaje, nivel="INFO"):
    hora = datetime.now().strftime("%H:%M:%S")
    print(f"[{hora}] [{nivel}] {mensaje}", flush=True)


def guardar_estado(estado, detalles=None):
    CARPETA_OUTPUT.mkdir(parents=True, exist_ok=True)

    informacion = {
        "proyecto": NOMBRE,
        "version": VERSION,
        "estado": estado,
        "actualizado": datetime.now(timezone.utc).isoformat(),
        "detalles": detalles or {}
    }

    ARCHIVO_ESTADO.write_text(
        json.dumps(
            informacion,
            ensure_ascii=False,
            indent=4
        ),
        encoding="utf-8"
    )


# ==========================================================
# VALIDACIÓN DEL GUION
# ==========================================================

def cargar_y_validar_guion(guion_generado=None):

    if not ARCHIVO_GUION.exists():
        raise FileNotFoundError(
            "No se encontró guion.json después de generar el guion."
        )

    with ARCHIVO_GUION.open("r", encoding="utf-8") as archivo:
        guion = json.load(archivo)

    if not isinstance(guion, dict):
        raise ValueError("El guion debe ser un objeto JSON.")

    titulo = str(guion.get("titulo", "")).strip()

    if len(titulo) < 5:
        raise ValueError("El título del video está vacío o es demasiado corto.")

    escenas = guion.get("escenas", [])

    if not isinstance(escenas, list) or not escenas:
        raise ValueError("El guion no contiene escenas válidas.")

    escenas_validas = []

    for numero, escena in enumerate(escenas, start=1):

        if not isinstance(escena, dict):
            continue

        narracion = str(
            escena.get("narracion", "")
        ).strip()

        if not narracion:
            continue

        escenas_validas.append({
            **escena,
            "numero": numero,
            "narracion": narracion
        })

    if not escenas_validas:
        raise ValueError("No hay narraciones utilizables.")

    guion["titulo"] = titulo
    guion["idioma"] = guion.get(
        "idioma",
        IDIOMA_PERMITIDO
    )

    guion["escenas"] = escenas_validas

    if not isinstance(guion.get("descripcion"), str):
        guion["descripcion"] = (
            f"{titulo}\n\n"
            "Descubre más curiosidades con FORTALEZA MEDIA AI."
        )

    if not isinstance(guion.get("hashtags"), list):
        guion["hashtags"] = [
            "#Curiosidades",
            "#Ciencia",
            "#FORTALEZAMEDIA"
        ]

    # Guardar la versión validada.
    ARCHIVO_GUION.write_text(
        json.dumps(
            guion,
            ensure_ascii=False,
            indent=4
        ),
        encoding="utf-8"
    )

    return guion


# ==========================================================
# PREPARACIÓN DEL ENTORNO
# ==========================================================

def preparar_entorno():

    CARPETA_OUTPUT.mkdir(
        parents=True,
        exist_ok=True
    )

    (CARPETA_OUTPUT / "recursos").mkdir(
        parents=True,
        exist_ok=True
    )

    registrar("Entorno de producción preparado.")


# ==========================================================
# GENERACIÓN DEL CONTENIDO
# ==========================================================

def generar_guion():

    registrar("Seleccionando tema automáticamente...")

    resultado = guardar_guion()

    guion = cargar_y_validar_guion(resultado)

    registrar(f"Tema seleccionado: {guion['titulo']}")
    registrar(f"Idioma: {guion['idioma']}")
    registrar(f"Formato: {guion.get('formato', 'No especificado')}")
    registrar(f"Escenas: {len(guion['escenas'])}")

    return guion


# ==========================================================
# MOTOR DE RENDERIZADO
# ==========================================================

async def producir_video():

    registrar("Iniciando motor de renderizado...")

    # Evitar confundir un video anterior con uno nuevo.
    if ARCHIVO_VIDEO.exists():
        ARCHIVO_VIDEO.unlink()
        registrar("Archivo anterior retirado.")

    inicio = time.time()

    await crear_video()

    tiempo = round(time.time() - inicio, 2)

    if not ARCHIVO_VIDEO.exists():
        raise FileNotFoundError(
            "El motor terminó, pero no generó el video esperado: "
            f"{ARCHIVO_VIDEO}"
        )

    tamano = ARCHIVO_VIDEO.stat().st_size

    if tamano <= 0:
        raise RuntimeError("El archivo de video está vacío.")

    if tamano > MAX_BYTES:
        raise RuntimeError(
            f"El video pesa {tamano / 1048576:.2f} MB. "
            f"Supera el límite preventivo de {MAX_MB:.0f} MB."
        )

    # Comprobar que el archivo tiene estructura básica MP4.
    with ARCHIVO_VIDEO.open("rb") as archivo:
        cabecera = archivo.read(16)

    if b"ftyp" not in cabecera:
        raise RuntimeError(
            "El archivo generado no parece ser un MP4 válido."
        )

    registrar("Renderizado completado correctamente.")
    registrar(f"Duración del proceso: {tiempo} segundos.")
    registrar(f"Tamaño final: {tamano / 1048576:.2f} MB")

    return {
        "archivo": str(ARCHIVO_VIDEO),
        "tamano_mb": round(tamano / 1048576, 2),
        "tiempo_segundos": tiempo
    }


# ==========================================================
# CONTROL DE CALIDAD
# ==========================================================

def control_calidad(guion, resultado):

    if not ARCHIVO_VIDEO.exists():
        raise RuntimeError("No existe el video para control de calidad.")

    if len(guion["escenas"]) == 0:
        raise RuntimeError("El guion no contiene escenas.")

    if not guion["titulo"].strip():
        raise RuntimeError("El título no es válido.")

    if resultado["tamano_mb"] <= 0:
        raise RuntimeError("El tamaño del video no es válido.")

    registrar("Control de calidad básico aprobado.")

    return True


# ==========================================================
# PRODUCCIÓN COMPLETA
# ==========================================================

async def iniciar_fortaleza():

    inicio = time.time()

    print("\n" + "=" * 58)
    print(f"       {NOMBRE} — MOTOR {VERSION}")
    print("       PRODUCCIÓN AUTOMÁTICA DE CONTENIDO")
    print("=" * 58 + "\n")

    guardar_estado("iniciando")

    try:

        preparar_entorno()

        # 1. Generar contenido.
        guion = generar_guion()

        guardar_estado(
            "guion_generado",
            {
                "titulo": guion["titulo"],
                "escenas": len(guion["escenas"])
            }
        )

        # 2. Crear el video.
        resultado = await producir_video()

        # 3. Revisar el resultado.
        control_calidad(
            guion,
            resultado
        )

        tiempo_total = round(
            time.time() - inicio,
            2
        )

        # 4. Registrar producción terminada.
        guardar_estado(
            "completado",
            {
                "titulo": guion["titulo"],
                "archivo": resultado["archivo"],
                "tamano_mb": resultado["tamano_mb"],
                "tiempo_total": tiempo_total,
                "escenas": len(guion["escenas"])
            }
        )

        print("\n" + "=" * 58)
        print("       PRODUCCIÓN FINALIZADA")
        print("=" * 58)
        print(f"Título: {guion['titulo']}")
        print(f"Archivo: {resultado['archivo']}")
        print(f"Tamaño: {resultado['tamano_mb']} MB")
        print(f"Tiempo: {tiempo_total} segundos")
        print("=" * 58 + "\n")

        registrar("FORTALEZA MEDIA AI terminó correctamente.")

        return True

    except Exception as error:

        guardar_estado(
            "error",
            {
                "mensaje": str(error),
                "tipo": type(error).__name__
            }
        )

        registrar(str(error), "ERROR")

        traceback.print_exc()

        raise


# ==========================================================
# PUNTO DE ENTRADA
# ==========================================================

if __name__ == "__main__":

    try:
        asyncio.run(iniciar_fortaleza())

    except KeyboardInterrupt:
        registrar("Producción interrumpida.", "WARNING")
        sys.exit(130)

    except Exception:
        registrar(
            "La producción terminó con errores.",
            "ERROR"
        )
        sys.exit(1)
