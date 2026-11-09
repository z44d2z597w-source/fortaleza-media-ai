import asyncio
import json
import sys
from pathlib import Path

try:
    from video_engine import guardar_guion
    from render_short import crear_short
except ImportError as e:
    print(f"[ERROR FATAL] No se pudieron importar los motores: {e}")
    sys.exit(1)

ARCHIVO_GUION = Path("guion.json")
CARPETA_OUTPUT = Path("output")
MAX_MB = 500

def validar_guion(guion):
    if not guion: raise ValueError("El guion está vacío.")
    if not guion.get("titulo"): raise ValueError("Falta el título.")
    if not guion.get("gancho_corto"): raise ValueError("Falta el gancho_corto.")
    if not guion.get("guion_largo"): raise ValueError("Falta el guion_largo.")
    return True

async def main():
    print("============================================================")
    print("FORTALEZA MEDIA AI — CONTROLADOR DUAL")
    print("============================================================")

    CARPETA_OUTPUT.mkdir(exist_ok=True)

    print("\n[PASO 1] Generando guion dual (Corto + Largo)...")
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
        print(f"  -> Capítulos del video largo: {len(guion['guion_largo'])}")
    except Exception as e:
        print(f"[ERROR FATAL] Guion inválido: {e}")
        sys.exit(1)

    print("\n[PASO 3] Renderizando el Short (TikTok / YouTube Shorts)...")
    try:
        resultado_short = await crear_short()
    except Exception as e:
        print(f"[ERROR FATAL] Falló el renderizado del Short: {e}")
        sys.exit(1)

    # (En el Paso 3 agregaremos la llamada para el video largo)
    
    print("\n✅ PROCESO FINALIZADO: SHORT LISTO.")
    return resultado_short

if __name__ == "__main__":
    asyncio.run(main())