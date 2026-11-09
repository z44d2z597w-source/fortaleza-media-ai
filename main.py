import asyncio
import json
import sys
from pathlib import Path

try:
    from video_engine import guardar_guion
    from render_short import crear_short
    from render_long import crear_long
except ImportError as e:
    print(f"[ERROR FATAL] No se pudieron importar los motores: {e}")
    sys.exit(1)

ARCHIVO_GUION = Path("guion.json")
CARPETA_OUTPUT = Path("output")

def validar_guion(guion):
    if not guion: raise ValueError("El guion está vacío.")
    if not guion.get("titulo"): raise ValueError("Falta el título.")
    if not guion.get("gancho_corto"): raise ValueError("Falta el gancho_corto.")
    
    # VALIDACIÓN ACTUALIZADA: Buscamos en director_notes.storyboard
    notas = guion.get("director_notes", {})
    storyboard = notas.get("storyboard", [])
    if not storyboard: raise ValueError("Falta el storyboard en director_notes.")
    
    return True

async def main():
    print("============================================================")
    print("FORTALEZA MEDIA AI — CONTROLADOR DUAL")
    print("============================================================")

    CARPETA_OUTPUT.mkdir(exist_ok=True)

    print("\n[PASO 1] Generando guion dual...")
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
        print(f"  -> Título: {guion['titulo']}")
        print(f"  -> Beats del storyboard: {len(guion['director_notes']['storyboard'])}")
    except Exception as e:
        print(f"[ERROR FATAL] Guion inválido: {e}")
        sys.exit(1)

    print("\n[PASO 3] Renderizando el Short (TikTok/Shorts)...")
    try:
        await crear_short()
    except Exception as e:
        print(f"[ERROR FATAL] Falló el Short: {e}")
        sys.exit(1)

    print("\n[PASO 4] Renderizando el Video Largo (YouTube)...")
    try:
        await crear_long()
    except Exception as e:
        print(f"[ERROR FATAL] Falló el Video Largo: {e}")
        sys.exit(1)
    
    print("\n✅ PROCESO COMPLETADO: SHORT Y VIDEO LARGO LISTOS.")
    return True

if __name__ == "__main__":
    asyncio.run(main())