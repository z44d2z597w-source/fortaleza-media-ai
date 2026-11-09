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

def generar_imagen_ia(prompt, seed):
    try:
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1080&height=1920&nologo=true&seed={seed}"
        resp = requests.get(url, timeout=45)
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        ruta = RECURSOS / f"img_beat_{seed}.jpg"
        img.save(ruta)
        return str(ruta)
    except Exception: return None

def obtener_video_fondo():
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
                    if os.path.getsize(ruta) > 50000: return str(ruta)
        except Exception: pass
    return None

async def generar_voz(texto, ruta, voz_elegida):
    for voz in [voz_elegida, "es-MX-DaliaNeural", "es-MX-JorgeNeural"]:
        try:
            tts = edge_tts.Communicate(texto, voice=voz, rate="+10%")
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
    raise RuntimeError("Fallo de audio")

def generar_whoosh(ruta):
    frec, dur = 44100, 0.3
    datos = array("h")
    for i in range(int(frec * dur)):
        t = i / frec
        vol = (t / dur) * (1 - t / dur) * 4
        datos.append(int(32767 * 0.2 * vol * random.uniform(-1, 1)))
        datos.append(int(32767 * 0.2 * vol * random.uniform(-1, 1)))
    with wave.open(str(ruta), "wb") as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(frec)
        f.writeframes(datos.tobytes())
    return str(ruta)

# --- SUBTÍTULOS CINÉTICOS AVANZADOS (ASS con animaciones de rebote y escala) ---
def generar_ass_cinetico(marcas, dur_voz, ruta_ass):
    grupos = []
    grupo_actual = []
    for p in marcas:
        grupo_actual.append(p)
        if len(grupo_actual) >= 2 or len(p["texto"]) > 8:
            grupos.append(grupo_actual)
            grupo_actual = []
    if grupo_actual: grupos.append(grupo_actual)

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Kinetic, DejaVu Sans, 120, &H0000FFFF, &H000000FF, &H00000000, &H00000000, -1, 0, 0, 0, 100, 100, 0, 0, 1, 8, 0, 5, 10, 10, 0, 1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lineas = []
    for i, g in enumerate(grupos):
        inicio = max(0, g[0]["inicio"])
        fin = min(dur_voz, g[-1]["fin"] + 0.1)
        if fin <= inicio: continue
        texto = " ".join(x["texto"] for x in g).upper()
        
        # Animación: Aparece desde abajo con rebote (Spring Bounce) y escala
        animacion = r"{\move(540,1200,540,960,0,250)\t(0,150,\fscx115\fscy115)\t(150,250,\fscx100\fscy100)}"
        
        lineas.append(f"Dialogue: 0,{inicio:.2f},{fin:.2f},Kinetic,,0,0,0,,{animacion}{texto}")

    with open(ruta_ass, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(lineas))
    return ruta_ass

async def crear_short():
    preparar_entorno()
    with open("guion.json", encoding="utf-8") as f: guion = json.load(f)
    
    voz = guion.get("voz", "es-MX-DaliaNeural")
    gancho = guion.get("gancho_corto", "")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    
    print(f"--- GENERANDO SHORT VIRAL: {guion['titulo']} ---")
    
    ruta_voz = RECURSOS / "voz_gancho.mp3"
    marcas = await generar_voz(gancho, ruta_voz, voz)
    dur_voz = obtener_duracion(ffmpeg, ruta_voz)
    
    video_fondo = obtener_video_fondo()
    whoosh_audio = generar_whoosh(RECURSOS / "whoosh.wav")
    ruta_ass = generar_ass_cinetico(marcas, dur_voz, RECURSOS / "subs.ass")
    
    # Generar 3 imágenes de impacto para intercalar (Pattern Interrupts)
    storyboard = guion.get("director_notes", {}).get("storyboard", [])
    imagenes_ia = []
    for i in range(3):
        prompt = storyboard[i]["prompt_visual"] if i < len(storyboard) else gancho[:100]
        img = generar_imagen_ia(prompt, random.randint(1, 9999))
        if img: imagenes_ia.append(img)

    # --- COMPOSICIÓN DEL VIDEO ---
    cmd = [ffmpeg, "-y"]
    if video_fondo: cmd.extend(["-stream_loop", "-1", "-i", video_fondo])
    else: cmd.extend(["-f", "lavfi", "-i", f"color=c=#071426:s={FORMATO['ancho']}x{FORMATO['alto']}:r={FPS}"])
        
    cmd.extend(["-i", str(ruta_voz)])
    cmd.extend(["-i", whoosh_audio])
    
    for img in imagenes_ia:
        cmd.extend(["-loop", "1", "-framerate", str(FPS), "-i", img])

    # Filtros: Fondo -> Imágenes IA (con zoom) -> Subtítulos ASS -> Barra
    filtros = []
    filtros.append(f"[0:v]scale={FORMATO['ancho']}:{FORMATO['alto']}:force_original_aspect_ratio=increase,crop={FORMATO['ancho']}:{FORMATO['alto']},eq=brightness=-0.15:saturation=1.3[bg]")
    
    actual = "[bg]"
    for k, img in enumerate(imagenes_ia):
        start = k * 2.0 # Aparecen cada 2 segundos
        end = start + 2.0
        # Añadir un ligero zoom a la imagen para que no se vea estática
        filtros.append(f"[{3 + k}:v]scale=1080:1920,zoompan=z='min(zoom+0.001,1.2)':d=1:s=1080x1920:fps={FPS}[img_{k}]")
        filtros.append(f"{actual}[img_{k}]overlay=0:0:enable='between(t,{start},{end})'[v_img_{k}]")
        actual = f"[v_img_{k}]"

    # Quemar subtítulos ASS
    filtros.append(f"{actual}ass={ruta_ass}[v_subs]")
    # Barra de progreso (roja para urgencia)
    filtros.append(f"[v_subs]drawbox=x=0:y=h-10:w='iw*t/{dur_voz}':h=10:color=red@0.9:t=fill[v_final]")

    # Audio: Voz + Whoosh (pattern interrupt)
    audio_filter = f"[1:a]volume=1.0[voz];[2:a]volume=0.5[whoosh];[voz][whoosh]amix=inputs=2:duration=first[audio_final]"

    destino = OUTPUT / "fortaleza_short.mp4"
    cmd.extend([
        "-filter_complex", ";".join(filtros) + ";" + audio_filter, 
        "-map", "[v_final]", "-map", "[audio_final]", 
        "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p", 
        "-c:a", "aac", "-b:a", "192k", "-t", f"{dur_voz:.3f}", str(destino)
    ])
    
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"✅ SHORT VIRAL COMPLETADO ({dur_voz:.1f} segundos)")
    return str(destino)

if __name__ == "__main__":
    asyncio.run(crear_short())