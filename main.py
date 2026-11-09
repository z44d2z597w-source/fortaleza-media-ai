import asyncio
import sys
from video_engine import obtener_guion_hoy
from render_short import renderizar_short

async def main():
    print("=========================================")
    print("FORTALEZA MEDIA AI — PUBLICADOR DIARIO")
    print("=========================================")
    
    try:
        print("[PASO 1] Obteniendo guion del día...")
        guion = obtener_guion_hoy()
        print(f"  -> Serie: {guion['titulo_serie']} | Parte: {guion['parte']}")
        
        print("[PASO 2] Renderizando el Short...")
        await renderizar_short()
        
        print("\n✅ PROCESO COMPLETADO")
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())