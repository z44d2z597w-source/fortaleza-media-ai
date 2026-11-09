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

# ==========================================================
# FORTALEZA MEDIA AI 37.0 — MOTOR DE VIDEO LARGO (YOUTUBE)
# ==========================================================

FPS = 30
OUTPUT = Path("output")
RECURSOS = OUTPUT / "recursos_long"
FORMATO = {"ancho": 1080, "alto": 1920} # Mantenemos vertical por si acaso, o 16:9 si prefieres

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

def obtener_video_fondo():
    # Buscamos un video de fondo largo o gameplay
    pixabay_key = os.environ.get("PIXABAY_API_KEY")
    if pixabay_key:
        try:
            query = random.choice(["gameplay", "nature loop", "abstract background"])
            resp = requests.get("https://pixabay.com/api/videos/", params={"key": pixabay_key, "q": query, "orientation": "vertical", "per_page": 3}, timeout=15).json()
            for hit in resp.get("hits", []):
                url = hit.get("videos", {}).get("large", {}).get("url") or hit.get("videos", {}).get("medium", {}).get("url")
                if url:
                    ruta = RECURSOS / "fondo_largo.mp4"
                    with requests.get(url, stream=True, timeout=20) as r:
                        with open(ruta, "wb") as f:
                            for chunk in r.iter_content(8192): f.write(chunk)
                    if os.path.getsize(ruta) > 50000:
                        print("[FONDO] Video de fondo obtenido.")
                        return str(ruta)
        except Exception: pass

    print("[FONDO] Usando gradiente de emergencia.")
    img = ImageOps.colorize(Image.linear_gradient("L").resize((FORMATO["ancho"], FORMATO["alto"])), black="#071426", white="#123D60").convert("RGB")
    ruta = RECURSOS / "fondo_emergencia.jpg"
    img.save(ruta)
    video_path = RECURSOS / "fondo_largo.mp4"
    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(ruta), "-c:v", "libx264", "-t", "3600", "-pix_fmt", "yuv420p", "-r", str(FPS), str(video_path)], check=True, capture_output=True)
    return str(video_path)

async def generar_voz(texto, ruta, voz_elegida):
    for voz in [voz_elegida, "es-MX-DaliaNeural", "es-MX-JorgeNeural"]:
        try:
            tts = edge_tts.Communicate(texto, voice=voz, rate="+5%")
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

def crear_subtitulos(marcas, dur_voz, idx_cap):
    grupos, grupo = [], []
    for p in marcas:
        grupo.append(p)
        if len(grupo) >= 5 or len(" ".join(x["texto"] for x in grupo)) >= 30:
            grupos.append(grupo); grupo = []
    if grupo: grupos.append(grupo)

    imgs = []
    for i, g in enumerate(grupos):
        inicio, fin = max(0, g[0]["inicio"]), min(dur_voz, g[-1]["fin"] + 0.15)
        if fin <= inicio: continue
        img = Image.new("RGBA", (FORMATO["ancho"], FORMATO["alto"]), (0,0,0,0))
        d = ImageDraw.Draw(img)
        font = obtener_fuente(int(FORMATO["ancho"] * 0.04), True)
        texto = " ".join(x["texto"] for x in g)
        
        y = int(FORMATO["alto"] * 0.85)
        bbox = d.textbbox((0, 0), texto, font=font)
        ancho_texto = bbox[2] - bbox[0]
        alto_texto = bbox[3] - bbox[1]
        d.rectangle([(FORMATO["ancho"] - ancho_texto) // 2 - 15, y - alto_texto // 2 - 10, (FORMATO["ancho"] + ancho_texto) // 2 + 15, y + alto_texto // 2 + 10], fill=(0,0,0,180))
        d.text((FORMATO["ancho"]//2, y), texto, font=font, fill="white", anchor="mm", stroke_width=3, stroke_fill="#000000")
        
        ruta = RECURSOS / f"sub_{idx_cap}_{i}.png"
        img.save(ruta)
        imgs.append({"archivo": str(ruta), "inicio": inicio, "fin": fin})
    return imgs

async def crear_long():
    preparar_entorno()
    with open("guion.json", encoding="utf-8") as f: guion = json.load(f)
    
    voz = guion.get("voz", "es-MX-DaliaNeural")
    capitulos = guion.get("guion_largo", [])
    
    if not capitulos:
        print("[ERROR] No hay guion_largo.")
        return None

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    video_fondo = obtener_video_fondo()
    clips_capitulos = []

    print(f"--- GENERANDO VIDEO LARGO: {guion['titulo']} ---")
    
    for idx, cap in enumerate(capitulos):
        print(f"\n[CAPÍTULO {idx+1}/{len(capitulos)}] {cap['titulo_capitulo']}")
        narracion = cap["narracion"]
        
        # 1. Audio del Capítulo
        ruta_voz = RECURSOS / f"voz_cap_{idx}.mp3"
        marcas = await generar_voz(narracion, ruta_voz, voz)
        dur_voz = obtener_duracion(ffmpeg, ruta_voz)
        
        # 2. Subtítulos
        subtitulos = crear_subtitulos(marcas, dur_voz, idx)
        
        # 3. Componer Capítulo
        cmd_comp = [ffmpeg, "-y", "-stream_loop", "-1", "-i", video_fondo, "-i", str(ruta_voz)]
        for sub in subtitulos: cmd_comp.extend(["-loop", "1", "-framerate", str(FPS), "-i", sub["archivo"]])
        
        filtros, actual, idx_f = [], "[0:v]", 2
        for sub in subtitulos:
            filtros.append(f"{actual}[{idx_f}:v]overlay=0:0:enable='between(t\\,{sub['inicio']:.3f}\\,{sub['fin']:.3f})'[v{idx_f}]")
            actual = f"[v{idx_f}]"; idx_f += 1
            
        if not filtros: filtros = ["[0:v]null[vfinal]"]; actual = "[vfinal]"
        
        ruta_cap = RECURSOS / f"cap_{idx}.mp4"
        cmd_comp.extend([
            "-filter_complex", ";".join(filtros), 
            "-map", actual, "-map", "1:a", 
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-pix_fmt", "yuv420p", 
            "-c:a", "aac", "-b:a", "128k", "-t", f"{dur_voz:.3f}", str(ruta_cap)
        ])
        subprocess.run(cmd_comp, check=True, capture_output=True)
        clips_capitulos.append(str(ruta_cap))
        print(f"  -> Capítulo {idx+1} renderizado ({dur_voz/60:.1f} min).")

    # 4. Unir todos los capítulos
    print("\n[UNIENDO CAPÍTULOS]...")
    destino = OUTPUT / "fortaleza_largo.mp4"
    with open(OUTPUT / "lista_largo.txt", "w") as f:
        for c in clips_capitulos: f.write(f"file '{Path(c).resolve()}'\n")
        
    subprocess.run([
        ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(OUTPUT / "lista_largo.txt"),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", str(destino)
    ], check=True, capture_output=True)
    
    dur_total = obtener_duracion(ffmpeg, destino)
    print(f"✅ VIDEO LARGO COMPLETADO: {dur_total/60:.2f} minutos")
    return str(destino)

if __name__ == "__main__":
    asyncio.run(crear_long())