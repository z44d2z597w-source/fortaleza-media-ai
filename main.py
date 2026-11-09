import asyncio, json, sys
from pathlib import Path
try:
    from video_engine import guardar_guion
    from render_short import crear_shorts
    from render_long import crear_long
except ImportError as e:
    print(f"[ERROR FATAL] {e}"); sys.exit(1)

async def main():
    print("FORTALEZA MEDIA AI — MODO INFINITO Y MINI-SERIES")
    try:
        guardar_guion()
        await crear_shorts()
        # await crear_long() # (Lo activamos cuando quieras el video de 40 min)
        print("\n✅ PROCESO COMPLETADO")
    except Exception as e:
        print(f"[ERROR] {e}"); sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())