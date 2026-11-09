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

# --- GENERADORES VISUALES ---
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

# --- AUDIO ---
async def generar_voz(texto, ruta, voz_elegida):
    for voz in [voz_elegida, "es-MX-DaliaNeural", "es-MX-JorgeNeural"]:
        try:
            tts = edge_tts.Communicate(texto, voice=voz, rate="+10%") # Un poco más rápido para energía
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

# --- TIPOGRAFÍA CINÉTICA (El secreto de la retención) ---
def crear_subtitulos_cineticos(marcas, dur_voz):
    grupos = []
    # Agrupamos las palabras de 1 en 1 o de 2 en 2 para que aparezcan rápido
    grupo_actual = []
    for p in marcas:
        grupo_actual.append(p)
        if len(grupo_actual) >= 2 or len(p["texto"]) > 8:
            grupos.append(grupo_actual)
            grupo_actual = []
    if grupo_actual: grupos.append(grupo_actual)

    imgs = []
    for i, g in enumerate(grupos):
        inicio = max(0, g[0]["inicio"])
        fin = min(dur_voz, g[-1]["fin"] + 0.1)
        if fin <= inicio: continue
        
        texto = " ".join(x["texto"] for x in g).upper()
        
        # Creamos una imagen para el texto con estilo (amarillo, negrita, borde negro)
        img = Image.new("RGBA", (FORMATO["ancho"], FORMATO["alto"]), (0,0,0,0))
        d = ImageDraw.Draw(img)
        font = obtener_fuente(int(FORMATO["ancho"] * 0.08), True)
        
        # Efecto de rebote (la primera imagen es más pequeña, la segunda normal)
        if i % 2 == 0:
            font = obtener_fuente(int(FORMATO["ancho"] * 0.06), True)
        else:
            font = obtener_fuente(int(FORMATO["ancho"] * 0.09), True)
            
        y = int(FORMATO["alto"] * 0.5) # En el centro de la pantalla
        
        # Sombra y borde para que resalte sobre el gameplay
        d.text((FORMATO["ancho"]//2, y), texto, font=font, fill="black", anchor="mm", stroke_width=8, stroke_fill="black")
        d.text((FORMATO["ancho"]//2, y), texto, font=font, fill="#FFD700", anchor="mm") # Amarillo
        
        ruta = RECURSOS / f"sub_cinetico_{i}.png"
        img.save(ruta)
        imgs.append({"archivo": str(ruta), "inicio": inicio, "fin": fin})
    return imgs

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
    
    # Generar Fondo y Whoosh
    video_fondo = obtener_video_fondo()
    whoosh_audio = generar_whoosh(RECURSOS / "whoosh.wav")
    
    # Generar Subtítulos Cinéticos
    subtitulos = crear_subtitulos_cineticos(marcas, dur_voz)
    
    # Generar Imágenes de Impacto (una cada 3 cortes para cambiar el visual)
    imagenes_ia = []
    for i in range(0, len(subtitulos), 3):
        img = generar_imagen_ia(gancho[:100], random.randint(1, 9999))
        if img: imagenes_ia.append({"img": img, "start_idx": i})
        
    # --- COMPOSICIÓN DEL VIDEO ---
    cmd = [ffmpeg, "-y"]
    
    # Input 0: Fondo Gameplay (o gradiente si falla)
    if video_fondo: cmd.extend(["-stream_loop", "-1", "-i", video_fondo])
    else: cmd.extend(["-f", "lavfi", "-i", f"color=c=#071426:s={FORMATO['ancho']}x{FORMATO['alto']}:r={FPS}"])
        
    # Input 1: Voz
    cmd.extend(["-i", str(ruta_voz)])
    
    # Input 2: Whoosh
    cmd.extend(["-i", whoosh_audio])
    
    # Añadir Subtítulos e Imágenes como inputs
    idx_input = 3
    for sub in subtitulos:
        cmd.extend(["-loop", "1", "-framerate", str(FPS), "-i", sub["archivo"]])
        
    for img_data in imagenes_ia:
        cmd.extend(["-loop", "1", "-framerate", str(FPS), "-i", img_data["img"]])

    # --- FILTROS ---
    filtros = []
    
    # 1. Fondo
    filtros.append(f"[0:v]scale={FORMATO['ancho']}:{FORMATO['alto']}:force_original_aspect_ratio=increase,crop={FORMATO['ancho']}:{FORMATO['alto']},eq=brightness=-0.2:saturation=1.5[bg]")
    
    # 2. Superponer Imágenes de Impacto (aparecen de fondo)
    actual = "[bg]"
    img_input_start = idx_input + len(subtitulos)
    for k, img_data in enumerate(imagenes_ia):
        # La imagen aparece por 2 segundos
        start_time = subtitulos[img_data["start_idx"]]["inicio"]
        end_time = start_time + 2.0
        filtros.append(f"[{img_input_start + k}:v]scale=1080:1920[img_{k}]")
        filtros.append(f"{actual}[img_{k}]overlay=0:0:enable='between(t,{start_time:.2f},{end_time:.2f})'[v_img_{k}]")
        actual = f"[v_img_{k}]"
        
    # 3. Superponer Subtítulos Cinéticos
    for i, sub in enumerate(subtitulos):
        filtros.append(f"{actual}[{idx_input + i}:v]overlay=0:0:enable='between(t\\,{sub['inicio']:.3f}\\,{sub['fin']:.3f})'[v_sub_{i}]")
        actual = f"[v_sub_{i}]"
        
    # 4. Barra de Progreso
    filtros.append(f"{actual}drawbox=x=0:y=h-10:w='iw*t/{dur_voz}':h=10:color=red@0.9:t=fill[v_final]")
    
    # 5. Audio (Voz + Whoosh en cada corte)
    audio_filter = "[1:a]volume=1.0[voz];"
    # Mezclar whoosh solo en los primeros 0.3 segundos de cada subtítulo
    # (Esto es complejo en FFmpeg, así que lo hacemos simple: un whoosh general)
    audio_filter += f"[2:a]volume=0.5[whoosh];[voz][whoosh]amix=inputs=2:duration=first[audio_final]"

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