import asyncio
import json
import sys
from pathlib import Path

# Importamos los motores con mensajes de error claros
try:
    from video_engine import guardar_guion
except ImportError as e:
    print(f"[ERROR FATAL] No se pudo importar 'guardar_guion' de video_engine.py. Detalle: {e}")
    sys.exit(1)

try:
    from render_video import crear_video
except ImportError as e:
    print(f"[ERROR FATAL] No se pudo importar 'crear_video' de render_video.py. Detalle: {e}")
    sys.exit(1)

ARCHIVO_GUION = Path("guion.json")
CARPETA_OUTPUT = Path("output")
ARCHIVO_PRODUCCION = CARPETA_OUTPUT / "produccion.json"

# Límite de seguridad aumentado a 500 MB
MAX_MB = 500

def validar_guion(guion):
    if not guion:
        raise ValueError("El guion está vacío.")
    if not guion.get("titulo") or not str(guion.get("titulo")).strip():
        raise ValueError("El guion no tiene un título válido.")
    escenas = guion.get("escenas", [])
    if not escenas:
        raise ValueError("El guion no contiene escenas.")
    for i, escena in enumerate(escenas):
        if not str(escena.get("narracion", "")).strip():
            raise ValueError(f"La escena {i+1} no tiene narración.")
    return True

async def main():
    print("=" * 60)
    print("FORTALEZA MEDIA AI — CONTROLADOR PRINCIPAL")
    print("=" * 60)

    CARPETA_OUTPUT.mkdir(exist_ok=True)

    # 1. Generar el guion
    print("\n[PASO 1] Generando guion con el motor editorial...")
    try:
        guardar_guion()
    except Exception as e:
        print(f"\n[ERROR FATAL] Falló la generación del guion: {e}")
        sys.exit(1)

    # 2. Validar
    print("\n[PASO 2] Validando guion generado...")
    if not ARCHIVO_GUION.exists():
        print(f"[ERROR FATAL] No se encontró {ARCHIVO_GUION}")
        sys.exit(1)

    try:
        with open(ARCHIVO_GUION, "r", encoding="utf-8") as f:
            guion = json.load(f)
        validar_guion(guion)
        print(f"  -> Título: {guion['titulo']}")
        print(f"  -> Formato: {guion.get('formato_legible', guion.get('formato', 'desconocido'))}")
        print(f"  -> Escenas: {len(guion['escenas'])}")
    except Exception as e:
        print(f"\n[ERROR FATAL] Guion inválido: {e}")
        sys.exit(1)

    # 3. Renderizar
    print("\n[PASO 3] Renderizando video (esto puede tardar varios minutos)...")
    try:
        resultado = await crear_video()
    except Exception as e:
        print(f"\n[ERROR FATAL] Falló la renderización del video: {e}")
        sys.exit(1)

    # 4. Verificar archivo final
    print("\n[PASO 4] Verificando archivo de salida...")
    ruta_video = None
    if isinstance(resultado, dict):
        ruta_video = resultado.get("archivo") or resultado.get("ruta")
    elif isinstance(resultado, (str, Path)):
        ruta_video = resultado

    if not ruta_video or not Path(ruta_video).exists():
        opciones = [CARPETA_OUTPUT / "fortaleza_final.mp4", CARPETA_OUTPUT / "fortaleza_short.mp4"]
        for opcion in opciones:
            if opcion.exists() and opcion.stat().st_size > 100_000:
                ruta_video = opcion
                break

    if not ruta_video or not Path(ruta_video).exists():
        print("[ERROR FATAL] No se encontró ningún archivo MP4 válido en output/")
        sys.exit(1)

    ruta_video = Path(ruta_video)
    tamano_bytes = ruta_video.stat().st_size
    tamano_mb = tamano_bytes / (1024 * 1024)

    if tamano_bytes < 100_000:
        print(f"[ERROR FATAL] El archivo {ruta_video.name} está vacío.")
        sys.exit(1)

    if tamano_mb > MAX_MB:
        print(f"[ERROR FATAL] El archivo pesa {tamano_mb:.2f} MB y supera el límite de {MAX_MB} MB.")
        sys.exit(1)

    print(f"  -> Archivo verificado: {ruta_video.name}")
    print(f"  -> Tamaño: {tamano_mb:.2f} MB")

    # 5. Registrar metadatos
    from datetime import datetime, timezone
    metadata = {
        "estado": "completado",
        "titulo": guion["titulo"],
        "descripcion": guion.get("descripcion", ""),
        "idioma": guion.get("idioma", "es-MX"),
        "formato": guion.get("formato", "vertical"),
        "escenas": len(guion["escenas"]),
        "archivo": ruta_video.name,
        "tamano_mb": round(tamano_mb, 2),
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "publicado": False
    }

    with open(ARCHIVO_PRODUCCION, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)

    print("\n" + "=" * 60)
    print("✅ PRODUCCIÓN COMPLETADA CON ÉXITO")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())