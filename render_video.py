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
# FORTALEZA MEDIA AI 33.0 — EJECUTOR DE STORYBOARD
# ==========================================================

FPS = 30
OUTPUT = Path("output")
RECURSOS = OUTPUT / "recursos"
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

# --- GENERADORES VISUALES (Usando el prompt del director) ---
def buscar_video_stock(prompt_visual, escena, toma):
    key = os.environ.get("PIXABAY_API_KEY")
    if key:
        try:
            # Extraemos palabras clave del prompt en inglés para buscar en Pixabay
            palabras = re.findall(r"[a-zA-Z]{4,}", prompt_visual)
            # Filtramos palabras técnicas como 'Cinematic', 'Vertical'
            query = " ".join([p for p in palabras if p.lower() not in ["cinematic", "vertical", "shot", "slow", "dramatic"]][:4])
            print(f"    -> [STOCK] Buscando video: '{query}'")
            
            resp = requests.get("https://pixabay.com/api/videos/", params={"key": key, "q": query, "orientation": "vertical", "per_page": 3}, timeout=15).json()
            for hit in resp.get("hits", []):
                url = hit.get("videos", {}).get("medium", {}).get("url")
                if url:
                    ruta = RECURSOS / f"pixabay_{escena}_{toma}.mp4"
                    with requests.get(url, stream=True, timeout=20) as r:
                        with open(ruta, "wb") as f:
                            for chunk in r.iter_content(8192): f.write(chunk)
                    if os.path.getsize(ruta) > 15000:
                        return str(ruta), True
        except Exception: pass
    return None

def generar_imagen_ia(prompt_visual, escena, toma):
    try:
        # Usamos el prompt visual exacto que generó Groq, y una semilla aleatoria
        seed = random.randint(1, 999999)
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt_visual)}?width={FORMATO['ancho']}&height={FORMATO['alto']}&nologo=true&seed={seed}"
        print(f"    -> [POLLINATIONS] Imagen IA (Seed: {seed})")
        
        resp = requests.get(url, timeout=45)
        img = Image.open(BytesIO(resp.content)); img.verify()
        ruta = RECURSOS / f"poll_{escena}_{toma}.jpg"
        with open(ruta, "wb") as f: f.write(resp.content)
        return str(ruta), False
    except Exception: return None

def crear_fondo_premium(escena, toma):
    img = ImageOps.colorize(Image.linear_gradient("L").resize((FORMATO["ancho"], FORMATO["alto"])), black="#071426", white="#123D60").convert("RGB")
    ruta = RECURSOS / f"fondo_{escena}_{toma}.jpg"
    img.save(ruta)
    print("    -> [EMERGENCIA] Fondo premium.")
    return str(ruta), False

# --- AUDIO ---
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

# --- RENDERIZADO Y GRÁFICOS ---
def crear_toma(ffmpeg, ruta, destino, duracion, idx, es_video):
    if es_video:
        filtros = [f"scale={FORMATO['ancho']}:{FORMATO['alto']}:force_original_aspect_ratio=increase", f"crop={FORMATO['ancho']}:{FORMATO['alto']}", "setsar=1", "format=yuv420p"]
        cmd = [ffmpeg, "-y", "-stream_loop", "-1", "-i", ruta, "-vf", ",".join(filtros), "-t", f"{duracion:.3f}", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-r", str(FPS), str(destino)]
    else:
        # Zoom cinematográfico para imágenes
        movs = [
            ("min(zoom+0.0020,1.4)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
            ("min(zoom+0.0030,1.5)", "iw/2-(iw/zoom/2)+on*0.3", "ih/2-(ih/zoom/2)"),
            ("max(zoom-0.0015,1.0)", "iw/2-(iw/zoom/2)-on*0.2", "ih/2-(ih/zoom/2)")
        ]
        zoom, x, y = movs[idx % len(movs)]
        filtros = [f"scale={int(FORMATO['ancho']*1.2)}:{int(FORMATO['alto']*1.2)}:force_original_aspect_ratio=increase", f"crop={int(FORMATO['ancho']*1.2)}:{int(FORMATO['alto']*1.2)}", f"zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s={FORMATO['ancho']}x{FORMATO['alto']}:fps={FPS}", "eq=contrast=1.15:saturation=1.2", "setsar=1", "format=yuv420p"]
        cmd = [ffmpeg, "-y", "-loop", "1", "-framerate", str(FPS), "-i", ruta, "-vf", ",".join(filtros), "-t", f"{duracion:.3f}", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-r", str(FPS), str(destino)]
    subprocess.run(cmd, check=True, capture_output=True)

def crear_subtitulos(marcas, escena_idx, dur_voz):
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
        font = obtener_fuente(int(FORMATO["ancho"] * 0.045), True)
        texto = " ".join(x["texto"] for x in g)
        y = int(FORMATO["alto"] * 0.82)
        d.text((FORMATO["ancho"]//2, y), texto, font=font, fill="white", anchor="mm", stroke_width=4, stroke_fill="#000000")
        ruta = RECURSOS / f"sub_{escena_idx}_{i}.png"
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

# --- ORQUESTADOR PRINCIPAL ---
async def crear_video():
    preparar_entorno()
    with open("guion.json", encoding="utf-8") as f: guion = json.load(f)
    
    voz = guion.get("voz", "es-MX-DaliaNeural")
    storyboard = guion.get("director_notes", {}).get("storyboard", [])
    
    if not storyboard:
        print("[ERROR] No hay storyboard en el guion. Ejecuta el nuevo video_engine.py primero.")
        return
        
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    clips_finales = []
    scroll_img = crear_scroll_stopper()

    print(f"--- PRODUCIENDO: {guion['titulo']} | VOZ: {voz} ---")
    
    for i, beat in enumerate(storyboard):
        print(f"\n[BEAT {i+1}/{len(storyboard)}]")
        narracion = beat["narracion"]
        prompt_visual = beat["prompt_visual"]
        
        # 1. Generar Audio
        ruta_voz = RECURSOS / f"voz_{i}.mp3"
        marcas = await generar_voz(narracion, ruta_voz, voz)
        dur_voz = obtener_duracion(ffmpeg, ruta_voz)
        
        # 2. Generar Material Visual (1 toma por beat para mantener la coherencia)
        print(f"    -> Prompt Visual: {prompt_visual[:60]}...")
        res = buscar_video_stock(prompt_visual, i, 0)
        if not res: res = generar_imagen_ia(prompt_visual, i, 0)
        if not res: res = crear_fondo_premium(i, 0)
        
        recurso, es_video = res
        ruta_toma = RECURSOS / f"toma_{i}.mp4"
        
        # La toma dura exactamente lo que dura la voz de este beat
        crear_toma(ffmpeg, recurso, ruta_toma, dur_voz, i, es_video)
        
        # 3. Crear Subtítulos y Componer Beat
        subtitulos = crear_subtitulos(marcas, i, dur_voz)
        cmd_comp = [ffmpeg, "-y", "-i", str(ruta_toma), "-i", str(ruta_voz)]
        
        for sub in subtitulos: cmd_comp.extend(["-loop", "1", "-framerate", str(FPS), "-i", sub["archivo"]])
        if i == 0:
            cmd_comp.extend(["-loop", "1", "-framerate", str(FPS), "-i", scroll_img])
            
        filtros, actual, idx = [], "[0:v]", 2
        for sub in subtitulos:
            filtros.append(f"{actual}[{idx}:v]overlay=0:0:enable='between(t\\,{sub['inicio']:.3f}\\,{sub['fin']:.3f})'[v{idx}]")
            actual = f"[v{idx}]"; idx += 1
            
        if i == 0:
            filtros.append(f"{actual}[{idx}:v]overlay=0:0:enable='between(t\\,0\\,2)'[vfinal]")
            actual = "[vfinal]"; idx += 1
            
        if not filtros: filtros = ["[0:v]null[vfinal]"]; actual = "[vfinal]"
        
        ruta_final_escena = RECURSOS / f"final_{i}.mp4"
        cmd_comp.extend(["-filter_complex", ";".join(filtros), "-map", actual, "-map", "1:a", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", f"{dur_voz:.3f}", str(ruta_final_escena)])
        subprocess.run(cmd_comp, check=True, capture_output=True)
        clips_finales.append(str(ruta_final_escena))

    print("\n[RENDER] Uniendo todos los beats...")
    video_unido = OUTPUT / "base.mp4"
    with open(OUTPUT / "all.txt", "w") as f:
        for c in clips_finales: f.write(f"file '{Path(c).resolve()}'\n")
    subprocess.run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(OUTPUT / "all.txt"), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(video_unido)], check=True, capture_output=True)
    
    # Añadir barra de progreso final
    dur_total = obtener_duracion(ffmpeg, video_unido)
    destino = OUTPUT / "fortaleza_final.mp4"
    filtro_barra = f"[0:v]drawbox=x=0:y=h-10:w='iw*t/{dur_total}':h=10:color=red@0.9:t=fill[vout]"
    subprocess.run([ffmpeg, "-y", "-i", str(video_unido), "-filter_complex", filtro_barra, "-map", "[vout]", "-map", "0:a", "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-c:a", "copy", str(destino)], check=True, capture_output=True)
    
    shutil.copy2(destino, OUTPUT / "fortaleza_short.mp4")
    print("\n✅ PRODUCCIÓN DE STORYBOARD COMPLETADA")
    return str(destino)

if __name__ == "__main__":
    asyncio.run(crear_video())