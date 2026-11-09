import asyncio
import json
import math
import os
import random
import re
import shutil
import subprocess
import time
import urllib.parse
import wave
from array import array
from io import BytesIO
from pathlib import Path

import requests
import edge_tts
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageOps

FPS = 30
OUTPUT = Path("output")
RECURSOS = OUTPUT / "recursos_short"
FORMATO = {"ancho": 1080, "alto": 1920}

def preparar_entorno():
    OUTPUT.mkdir(exist_ok=True)
    RECURSOS.mkdir(exist_ok=True)
    for f in RECURSOS.iterdir():
        if f.is_file(): f.unlink()

def obtener_fuente(tamano, negrita=False):
    rutas = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if negrita else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if negrita else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for r in rutas:
        if os.path.exists(r): return ImageFont.truetype(r, tamano)
    return ImageFont.load_default()

def obtener_duracion(ffmpeg, archivo):
    res = subprocess.run([ffmpeg, "-i", str(archivo)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", res.stderr)
    if not m: raise RuntimeError(f"Error de duración: {archivo}")
    h, mi, s = m.groups(); return int(h)*3600 + int(mi)*60 + float(s)

def obtener_video_fondo(ffmpeg):
    pixabay_key = os.environ.get("PIXABAY_API_KEY")
    if pixabay_key:
        try:
            query = random.choice(["gameplay", "subway surfers", "minecraft parkour"])
            resp = requests.get("https://pixabay.com/api/videos/", params={"key": pixabay_key, "q": query, "orientation": "vertical", "per_page": 3}, timeout=15).json()
            for hit in resp.get("hits", []):
                url = hit.get("videos", {}).get("large", {}).get("url") or hit.get("videos", {}).get("medium", {}).get("url")
                if url:
                    ruta = RECURSOS / "fondo_gameplay.mp4"
                    with requests.get(url, stream=True, timeout=20) as r:
                        with open(ruta, "wb") as f:
                            for chunk in r.iter_content(8192): f.write(chunk)
                    if os.path.getsize(ruta) > 50000:
                        print("[FONDO] Gameplay obtenido vía Pixabay.")
                        return str(ruta)
        except Exception as e:
            print(f"[FONDO] Error con Pixabay: {e}")

    print("[FONDO] Usando fondo de gradiente de emergencia.")
    img = ImageOps.colorize(Image.linear_gradient("L").resize((FORMATO["ancho"], FORMATO["alto"])), black="#071426", white="#123D60").convert("RGB")
    ruta = RECURSOS / "fondo_emergencia.jpg"
    img.save(ruta)
    video_path = RECURSOS / "fondo_gameplay.mp4"
    subprocess.run([ffmpeg, "-y", "-loop", "1", "-i", str(ruta), "-c:v", "libx264", "-t", "60", "-pix_fmt", "yuv420p", "-r", str(FPS), str(video_path)], check=True, capture_output=True)
    return str(video_path)

async def generar_voz(texto, ruta, voz_elegida):
    for voz in [voz_elegida, "es-MX-DaliaNeural", "es-MX-JorgeNeural"]:
        try:
            tts = edge_tts.Communicate(texto, voice=voz, rate="+8%")
            audio, marcas = bytearray(), []
            async for f in tts.stream():
                if f["type"] == "audio": audio.extend(f["data"])
                elif f["type"] == "WordBoundary":
                    inicio = f["offset"] / 10000000
                    marcas.append({"texto": f["text"], "inicio": inicio, "fin": inicio + (f["duration"] / 10000000)})
            if len(audio) > 1000:
                with open(ruta, "wb") as f: f.write(audio)
                return marcas
        except Exception: pass
    raise RuntimeError("Fallo total de audio.")

def crear_subtitulos(marcas, dur_voz):
    grupos, grupo = [], []
    for p in marcas:
        grupo.append(p)
        if len(grupo) >= 4 or len(" ".join(x["texto"] for x in grupo)) >= 25:
            grupos.append(grupo); grupo = []
    if grupo: grupos.append(grupo)

    imgs = []
    for i, g in enumerate(grupos):
        inicio, fin = max(0, g[0]["inicio"]), min(dur_voz, g[-1]["fin"] + 0.15)
        if fin <= inicio: continue
        img = Image.new("RGBA", (FORMATO["ancho"], FORMATO["alto"]), (0,0,0,0))
        d = ImageDraw.Draw(img)
        font = obtener_fuente(int(FORMATO["ancho"] * 0.055), True)
        texto = " ".join(x["texto"] for x in g)
        
        y = int(FORMATO["alto"] * 0.82)
        bbox = d.textbbox((0, 0), texto, font=font)
        ancho_texto = bbox[2] - bbox[0]
        alto_texto = bbox[3] - bbox[1]
        d.rectangle([(FORMATO["ancho"] - ancho_texto) // 2 - 15, y - alto_texto // 2 - 10, (FORMATO["ancho"] + ancho_texto) // 2 + 15, y + alto_texto // 2 + 10], fill=(0,0,0,180))
        d.text((FORMATO["ancho"]//2, y), texto, font=font, fill="white", anchor="mm", stroke_width=3, stroke_fill="#000000")
        
        ruta = RECURSOS / f"sub_{i}.png"
        img.save(ruta)
        imgs.append({"archivo": str(ruta), "inicio": inicio, "fin": fin})
    return imgs

def crear_scroll_stopper():
    img = Image.new("RGBA", (FORMATO["ancho"], FORMATO["alto"]), (0,0,0,0))
    d = ImageDraw.Draw(img)
    font = obtener_fuente(int(FORMATO["ancho"] * 0.12), True)
    d.rectangle((0, int(FORMATO["alto"]*0.35), FORMATO["ancho"], int(FORMATO["alto"]*0.55)), fill=(220, 20, 20, 230))
    d.text((FORMATO["ancho"]//2, int(FORMATO["alto"]*0.45)), "¡NO LO VAS\nA CREER!", font=font, fill="white", anchor="mm", align="center", stroke_width=6, stroke_fill="#000000")
    ruta = RECURSOS / "scroll.png"
    img.save(ruta)
    return str(ruta)

async def crear_short():
    preparar_entorno()
    with open("guion.json", encoding="utf-8") as f: guion = json.load(f)
    
    voz = guion.get("voz", "es-MX-DaliaNeural")
    gancho = guion.get("gancho_corto", "")
    
    if not gancho:
        print("[ERROR] No hay gancho_corto en el guion.")
        return None

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe() # <--- AQUÍ OBTENEMOS LA RUTA CORRECTA
    video_fondo = obtener_video_fondo(ffmpeg)
    
    print(f"--- GENERANDO SHORT: {guion['titulo']} ---")
    
    ruta_voz = RECURSOS / "voz_gancho.mp3"
    marcas = await generar_voz(gancho, ruta_voz, voz)
    dur_voz = obtener_duracion(ffmpeg, ruta_voz)
    
    subtitulos = crear_subtitulos(marcas, dur_voz)
    scroll_img = crear_scroll_stopper()
    
    cmd_comp = [ffmpeg, "-y", "-stream_loop", "-1", "-i", video_fondo, "-i", str(ruta_voz)]
    for sub in subtitulos: cmd_comp.extend(["-loop", "1", "-framerate", str(FPS), "-i", sub["archivo"]])
    cmd_comp.extend(["-loop", "1", "-framerate", str(FPS), "-i", scroll_img])
    
    filtros, actual, idx = [], "[0:v]", 2
    
    for sub in subtitulos:
        filtros.append(f"{actual}[{idx}:v]overlay=0:0:enable='between(t\\,{sub['inicio']:.3f}\\,{sub['fin']:.3f})'[v{idx}]")
        actual = f"[v{idx}]"; idx += 1
        
    filtros.append(f"{actual}[{idx}:v]overlay=0:0:enable='between(t\\,0\\,3)'[vfinal]")
    actual = "[vfinal]"
    
    destino = OUTPUT / "fortaleza_short.mp4"
    cmd_comp.extend([
        "-filter_complex", ";".join(filtros), 
        "-map", actual, "-map", "1:a", 
        "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-pix_fmt", "yuv420p", 
        "-c:a", "aac", "-b:a", "192k", "-t", f"{dur_voz:.3f}", str(destino)
    ])
    
    subprocess.run(cmd_comp, check=True, capture_output=True)
    
    dur_total = obtener_duracion(ffmpeg, destino)
    destino_final = OUTPUT / "fortaleza_short_final.mp4"
    filtro_barra = f"[0:v]drawbox=x=0:y=h-10:w='iw*t/{dur_total}':h=10:color=red@0.9:t=fill[vout]"
    subprocess.run([ffmpeg, "-y", "-i", str(destino), "-filter_complex", filtro_barra, "-map", "[vout]", "-map", "0:a", "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-c:a", "copy", str(destino_final)], check=True, capture_output=True)
    
    print(f"✅ SHORT COMPLETADO ({dur_total:.1f} segundos)")
    return str(destino_final)

if __name__ == "__main__":
    asyncio.run(crear_short())