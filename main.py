import asyncio
import json
import sys
from pathlib import Path

try:
    from video_engine import guardar_guion
    from render_video import crear_video
except ImportError as e:
    print(f"[ERROR FATAL] No se pudieron importar los motores: {e}")
    sys.exit(1)

ARCHIVO_GUION = Path("guion.json")
CARPETA_OUTPUT = Path("output")
ARCHIVO_PRODUCCION = CARPETA_OUTPUT / "produccion.json"
MAX_MB = 500

def validar_guion(guion):
    if not guion:
        raise ValueError("El guion está vacío.")
    if not guion.get("titulo"):
        raise ValueError("El guion no tiene título.")
    
    # VALIDACIÓN ACTUALIZADA PARA EL STORYBOARD DEL DIRECTOR
    notas = guion.get("director_notes", {})
    storyboard = notas.get("storyboard", [])
    
    if not storyboard:
        raise ValueError("El guion no contiene un storyboard válido en 'director_notes'.")
        
    for i, beat in enumerate(storyboard):
        if not str(beat.get("narracion", "")).strip():
            raise ValueError(f"El beat {i+1} del storyboard no tiene narración.")
            
    return True

async def main():
    print("============================================================")
    print("FORTALEZA MEDIA AI — CONTROLADOR PRINCIPAL")
    print("============================================================")

    CARPETA_OUTPUT.mkdir(exist_ok=True)

    print("\n[PASO 1] Generando guion...")
    try:
        guardar_guion()
    except Exception as e:
        print(f"[ERROR FATAL] Falló la generación del guion: {e}")
        sys.exit(1)

    print("\n[PASO 2] Validando guion...")
    try:
        with open(ARCHIVO_GUION, "r", encoding="utf-8") as f:
            guion = json.load(f)
        validar_guion(guion)
        beats = guion.get("director_notes", {}).get("storyboard", [])
        print(f"  -> Título: {guion['titulo']}")
        print(f"  -> Beats en Storyboard: {len(beats)}")
    except Exception as e:
        print(f"[ERROR FATAL] Guion inválido: {e}")
        sys.exit(1)

    print("\n[PASO 3] Renderizando video (esto tardará varios minutos)...")
    try:
        resultado = await crear_video()
    except Exception as e:
        print(f"[ERROR FATAL] Falló la renderización del video: {e}")
        sys.exit(1)

    print("\n[PASO 4] Verificando archivo de salida...")
    ruta_video = None
    if isinstance(resultado, dict):
        ruta_video = resultado.get("archivo")
    elif isinstance(resultado, (str, Path)):
        ruta_video = resultado

    if not ruta_video or not Path(ruta_video).exists():
        opciones = [CARPETA_OUTPUT / "fortaleza_final.mp4", CARPETA_OUTPUT / "fortaleza_short.mp4"]
        for opcion in opciones:
            if opcion.exists() and opcion.stat().st_size > 100_000:
                ruta_video = opcion
                break

    if not ruta_video or not Path(ruta_video).exists():
        print("[ERROR FATAL] No se encontró ningún archivo MP4 válido.")
        sys.exit(1)

    ruta_video = Path(ruta_video)
    tamano_mb = ruta_video.stat().st_size / (1024 * 1024)

    if tamano_mb > MAX_MB:
        print(f"[ERROR FATAL] El archivo pesa {tamano_mb:.2f} MB y supera el límite.")
        sys.exit(1)

    print(f"  -> Archivo verificado: {ruta_video.name} ({tamano_mb:.2f} MB)")
    print("\n✅ PRODUCCIÓN COMPLETADA CON ÉXITO")

if __name__ == "__main__":
    asyncio.run(main())