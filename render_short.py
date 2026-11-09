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

def generar_imagen_ia(prompt, num):
    try:
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1080&height=1080&nologo=true&seed={random.randint(1,9999)}"
        resp = requests.get(url, timeout=45)
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        # Hacerla cuadrada con bordes redondeados
        img = ImageOps.fit(img, (900, 900), method=Image.Resampling.LANCZOS)
        mask = Image.new("L", (900, 900), 0)
        d = ImageDraw.Draw(mask)
        d.rounded_rectangle((0, 0, 900, 900), radius=40, fill=255)
        
        ruta = RECURSOS / f"story_img_{num}.png"
        img.putalpha(mask)
        img.save(ruta)
        print(f"    -> [IA] Imagen de historia generada.")
        return str(ruta)
    except Exception as e:
        print(f"    -> [IA] Error: {e}")
        return None

def obtener_video_fondo(ffmpeg):
    pixabay_key = os.environ.get("PIXABAY_API_KEY")
    if pixabay_key:
        try:
            query = random.choice(["subway surfers", "minecraft parkour", "gameplay"])
            resp = requests.get("https://pixabay.com/api/videos/", params={"key": pixabay_key, "q": query, "orientation": "vertical", "per_page": 3}, timeout=15).json()
            for hit in resp.get("hits", []):
                url = hit.get("videos", {}).get("large", {}).get("url") or hit.get("videos", {}).get("medium", {}).get("url")
                if url:
                    ruta = RECURSOS / "fondo_gameplay.mp4"
                    with requests.get(url, stream=True, timeout=20) as r:
                        with open(ruta, "wb") as f:
                            for chunk in r.iter_content(8192): f.write(chunk)
                    if os.path.getsize(ruta) > 50000:
                        return str(ruta)
        except Exception: pass
    return None

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

def generar_musica(duracion):
    ruta = RECURSOS / "musica.wav"
    frec = 22050
    datos = array("h")
    for i in range(int(frec * duracion)):
        t = i / frec
        modulacion = 0.65 + 0.35 * math.sin(2 * math.pi * 0.035 * t)
        sonido = (math.sin(2*math.pi*110*t)*0.26 + math.sin(2*math.pi*164.81*t)*0.18) * modulacion
        datos.append(int(32767 * 0.05 * sonido)); datos.append(int(32767 * 0.05 * sonido))
    with wave.open(str(ruta), "wb") as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(frec)
        f.writeframes(datos.tobytes())
    return str(ruta)

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
        font = obtener_fuente(int(FORMATO["ancho"] * 0.06), True)
        texto = " ".join(x["texto"] for x in g).upper()
        
        y = int(FORMATO["alto"] * 0.82)
        bbox = d.textbbox((0, 0), texto, font=font)
        ancho_texto = bbox[2] - bbox[0]
        alto_texto = bbox[3] - bbox[1]
        d.rectangle([(FORMATO["ancho"] - ancho_texto) // 2 - 15, y - alto_texto // 2 - 10, (FORMATO["ancho"] + ancho_texto) // 2 + 15, y + alto_texto // 2 + 10], fill=(0,0,0,200))
        d.text((FORMATO["ancho"]//2, y), texto, font=font, fill="yellow", anchor="mm", stroke_width=4, stroke_fill="#000000")
        
        ruta = RECURSOS / f"sub_{i}.png"
        img.save(ruta)
        imgs.append({"archivo": str(ruta), "inicio": inicio, "fin": fin})
    return imgs

async def crear_short():
    preparar_entorno()
    with open("guion.json", encoding="utf-8") as f: guion = json.load(f)
    
    voz = guion.get("voz", "es-MX-DaliaNeural")
    gancho = guion.get("gancho_corto", "")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    
    print(f"--- GENERANDO SHORT ÉPICO: {guion['titulo']} ---")
    
    ruta_voz = RECURSOS / "voz_gancho.mp3"
    marcas = await generar_voz(gancho, ruta_voz, voz)
    dur_voz = obtener_duracion(ffmpeg, ruta_voz)
    
    # 1. Generar Imagen de Historia
    img_historia = generar_imagen_ia(gancho[:100], 1)
    
    # 2. Generar Video de Fondo
    video_fondo = obtener_video_fondo(ffmpeg)
    
    # 3. Generar Música
    musica = generar_musica(int(dur_voz) + 2)
    
    # 4. Subtítulos
    subtitulos = crear_subtitulos(marcas, dur_voz)
    
    # 5. Componer Video
    cmd = [ffmpeg, "-y"]
    if video_fondo:
        cmd.extend(["-stream_loop", "-1", "-i", video_fondo]) # Input 0: Gameplay
    else:
        # Si no hay fondo, usar la imagen como fondo completo
        cmd.extend(["-loop", "1", "-framerate", str(FPS), "-i", img_historia])
        
    cmd.extend(["-i", str(ruta_voz)]) # Input 1: Voz
    cmd.extend(["-stream_loop", "-1", "-i", musica]) # Input 2: Música
    
    idx_in = 3
    if video_fondo and img_historia:
        cmd.extend(["-loop", "1", "-framerate", str(FPS), "-i", img_historia]) # Input 3: Imagen
        
    for sub in subtitulos: 
        cmd.extend(["-loop", "1", "-framerate", str(FPS), "-i", sub["archivo"]])
        idx_in += 1

    # Filtros
    filtros = []
    
    # Filtro de Fondo (Gameplay)
    if video_fondo:
        filtros.append(f"[0:v]scale={FORMATO['ancho']}:{FORMATO['alto']}:force_original_aspect_ratio=increase,crop={FORMATO['ancho']}:{FORMATO['alto']}[bg]")
    else:
        filtros.append(f"[0:v]scale={FORMATO['ancho']}:{FORMATO['alto']}:force_original_aspect_ratio=increase,crop={FORMATO['ancho']}:{FORMATO['alto']}[bg]")

    # Filtro de Imagen sobre Gameplay
    actual = "[bg]"
    if video_fondo and img_historia:
        # Poner la imagen en el centro con un poco de zoom
        filtros.append(f"[3:v]zoompan=z='min(zoom+0.001,1.2)':d=1:s=900x900:fps={FPS}[img]")
        filtros.append(f"[{actual}][img]overlay=(W-w)/2:(H-h)/2-100:enable='between(t,0,{dur_voz})'[v_img]")
        actual = "[v_img]"
        
    # Filtro de Subtítulos
    for i, sub in enumerate(subtitulos):
        entrada_idx = (4 if (video_fondo and img_historia) else 3) + i
        filtros.append(f"{actual}[{entrada_idx}:v]overlay=0:0:enable='between(t\\,{sub['inicio']:.3f}\\,{sub['fin']:.3f})'[v_sub_{i}]")
        actual = f"[v_sub_{i}]"

    filtros.append(f"{actual}format=yuv420p[vout]")

    # Audio (Voz + Música)
    filtros.append("[1:a]volume=1.0[voz];[2:a]volume=0.15[musica];[voz][musica]amix=inputs=2:duration=first[audio_mixed]")

    destino = OUTPUT / "fortaleza_short.mp4"
    cmd.extend([
        "-filter_complex", ";".join(filtros), 
        "-map", "[vout]", "-map", "[audio_mixed]", 
        "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-pix_fmt", "yuv420p", 
        "-c:a", "aac", "-b:a", "192k", "-t", f"{dur_voz:.3f}", str(destino)
    ])
    
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"✅ SHORT COMPLETADO ({dur_voz:.1f} segundos)")
    return str(destino)

if __name__ == "__main__":
    asyncio.run(crear_short())