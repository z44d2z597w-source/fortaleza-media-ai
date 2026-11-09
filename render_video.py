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
# FORTALEZA MEDIA AI 28.0 — ECOSISTEMA DE ASIGNACIÓN DINÁMICA
# TODAS LAS IAs TRABAJAN EN EQUIPO POR ESCENA
# ==========================================================

FPS = 30
OUTPUT = Path("output")
RECURSOS = OUTPUT / "recursos"
CONFIG_DEFECTO = {"corte_min": 1.5, "corte_max": 3.5}

def preparar_entorno():
    OUTPUT.mkdir(exist_ok=True)
    RECURSOS.mkdir(exist_ok=True)
    for f in RECURSOS.iterdir():
        if f.is_file(): f.unlink()

def obtener_duracion(ffmpeg, archivo):
    res = subprocess.run([ffmpeg, "-i", str(archivo)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", res.stderr)
    if not m: raise RuntimeError(f"Error de duración: {archivo}")
    h, mi, s = m.groups(); return int(h)*3600 + int(mi)*60 + float(s)

def calcular_cortes(palabras, duracion_total):
    c_min, c_max = CONFIG_DEFECTO["corte_min"], CONFIG_DEFECTO["corte_max"]
    if duracion_total <= 0: return [0.0, duracion_total]
    puntos = [(palabras[i-1]["fin"] + palabras[i]["inicio"])/2 for i in range(1, len(palabras)) if palabras[i]["inicio"] - palabras[i-1]["fin"] >= 0.25]
    puntos += [p["fin"] + 0.05 for p in palabras if p["texto"].strip().endswith((".", "?", "!"))]
    puntos = sorted(set(round(c, 3) for c in puntos))
    cortes = [0.0]
    for c in puntos:
        if (c < 5.0 and c - cortes[-1] >= 1.2) or (c >= 5.0 and c - cortes[-1] >= c_min and duracion_total - c >= c_min):
            cortes.append(c)
    resultado = [0.0]
    for c in cortes[1:]:
        while c - resultado[-1] > c_max: resultado.append(resultado[-1] + c_max)
        resultado.append(c)
    while duracion_total - resultado[-1] > c_max: resultado.append(resultado[-1] + c_max)
    if resultado[-1] < duracion_total: resultado.append(duracion_total)
    else: resultado[-1] = duracion_total
    return resultado

# ==========================================================
# DEFINICIÓN DE LOS MOTORES (Cada uno devuelve (ruta, es_video))
# ==========================================================

def intentar_agnes(prompt, duracion, escena, toma):
    key = os.environ.get("AGNES_API_KEY")
    if not key: return None
    try:
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {"model": "agnes-video-2.5-flash", "prompt": prompt, "duration": min(5, int(duracion)+1), "aspect_ratio": "9:16"}
        resp = requests.post("https://apihub.agnes-ai.cn/v1/video/generations", headers=headers, json=payload, timeout=30)
        task_id = resp.json().get("id") or resp.json().get("task_id")
        if task_id:
            for _ in range(15): # Timeout más corto para no colgar el sistema
                time.sleep(8)
                poll = requests.get(f"https://apihub.agnes-ai.cn/v1/video/generations/{task_id}", headers=headers).json()
                if poll.get("status") == "succeeded":
                    url = poll.get("output", {}).get("video_url")
                    if url:
                        ruta = RECURSOS / f"agnes_{escena}_{toma}.mp4"
                        with requests.get(url, stream=True, timeout=60) as r:
                            r.raise_for_status()
                            with open(ruta, "wb") as f:
                                for chunk in r.iter_content(8192): f.write(chunk)
                        print(f"    -> [AGNES] Video IA generado.")
                        return str(ruta), True
                elif poll.get("status") == "failed": break
    except Exception: pass
    return None

def intentar_magichour(prompt, duracion, escena, toma):
    key = os.environ.get("MAGIC_HOUR_API_KEY")
    if not key: return None
    try:
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {"prompt": prompt, "model": "wan-2.2", "duration_seconds": min(5, int(duracion)+1), "resolution": "480p", "aspect_ratio": "9:16"}
        resp = requests.post("https://api.magichour.ai/v1/text-to-video", headers=headers, json=payload, timeout=30)
        url = resp.json().get("video_url")
        if url:
            ruta = RECURSOS / f"mh_{escena}_{toma}.mp4"
            with requests.get(url, stream=True, timeout=60) as r:
                with open(ruta, "wb") as f:
                    for chunk in r.iter_content(8192): f.write(chunk)
            print(f"    -> [MAGIC HOUR] Video IA generado.")
            return str(ruta), True
    except Exception: pass
    return None

def intentar_pixabay(prompt, escena, toma):
    key = os.environ.get("PIXABAY_API_KEY")
    if not key: return None
    try:
        query = " ".join(re.findall(r"[a-zA-Z]{4,}", prompt)[:3])
        resp = requests.get("https://pixabay.com/api/videos/", params={"key": key, "q": query, "orientation": "vertical", "per_page": 3}, timeout=15).json()
        for hit in resp.get("hits", []):
            url = hit.get("videos", {}).get("medium", {}).get("url")
            if url:
                ruta = RECURSOS / f"pixabay_{escena}_{toma}.mp4"
                with requests.get(url, stream=True, timeout=20) as r:
                    with open(ruta, "wb") as f:
                        for chunk in r.iter_content(8192): f.write(chunk)
                if os.path.getsize(ruta) > 15000:
                    print(f"    -> [PIXABAY] Video de stock generado.")
                    return str(ruta), True
    except Exception: pass
    return None

def intentar_pollinations(prompt, escena, toma, formato):
    try:
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width={formato['ancho']}&height={formato['alto']}&nologo=true"
        resp = requests.get(url, timeout=45)
        img = Image.open(BytesIO(resp.content)); img.verify()
        ruta = RECURSOS / f"poll_{escena}_{toma}.jpg"
        with open(ruta, "wb") as f: f.write(resp.content)
        print(f"    -> [POLLINATIONS] Imagen IA generada.")
        return str(ruta), False
    except Exception: pass
    return None

def intentar_fondo_premium(escena, toma, formato):
    ancho, alto = formato["ancho"], formato["alto"]
    img = ImageOps.colorize(Image.linear_gradient("L").resize((ancho, alto)), black="#071426", white="#123D60").convert("RGB")
    ruta = RECURSOS / f"fondo_{escena}_{toma}.jpg"
    img.save(ruta)
    print(f"    -> [EMERGENCIA] Fondo premium generado.")
    return str(ruta), False

# ==========================================================
# ASIGNACIÓN DINÁMICA POR ESCENA
# ==========================================================

def obtener_material_visual(prompt, escena_idx, toma_idx, duracion, formato, tipo_escena):
    """
    Aquí es donde el equipo trabaja junto. 
    Dependiendo de la escena, asignamos un orden de prioridad diferente.
    """
    if tipo_escena == "gancho":
        # Para el gancho queremos VIDEO IA a toda costa
        orden = [intentar_agnes, intentar_magichour, intentar_pixabay, intentar_pollinations]
    elif tipo_escena == "contexto":
        # Para el contexto queremos STOCK rápido
        orden = [intentar_pixabay, intentar_pollinations, intentar_agnes]
    elif tipo_escena in ["desarrollo", "climax"]:
        # Para el desarrollo queremos IMAGEN IA (Pollinations) o Agnes
        orden = [intentar_pollinations, intentar_agnes, intentar_pixabay]
    else: # cierre
        orden = [intentar_pixabay, intentar_pollinations, intentar_agnes]

    # El equipo se pasa la pelota
    for motor in orden:
        if motor in [intentar_agnes, intentar_magichour]:
            res = motor(prompt, duracion, escena_idx, toma_idx)
        elif motor == intentar_pixabay:
            res = motor(prompt, escena_idx, toma_idx)
        else:
            res = motor(prompt, escena_idx, toma_idx, formato)
            
        if res: return res # Si tiene éxito, se devuelve y pasamos a la siguiente toma

    # Si todos fallan, entra el fondo de emergencia
    return intentar_fondo_premium(escena_idx, toma_idx, formato)

# ==========================================================
# AUDIO Y RENDERIZADO
# ==========================================================

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

def crear_toma(ffmpeg, ruta, destino, duracion, idx, formato, es_video):
    ancho, alto = formato["ancho"], formato["alto"]
    if es_video:
        filtros = [f"scale={ancho}:{alto}:force_original_aspect_ratio=increase", f"crop={ancho}:{alto}", "setsar=1", "format=yuv420p"]
        cmd = [ffmpeg, "-y", "-stream_loop", "-1", "-i", ruta, "-vf", ",".join(filtros), "-t", f"{duracion:.3f}", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-r", str(FPS), str(destino)]
    else:
        movs = [("min(zoom+0.0015,1.3)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"), ("min(zoom+0.0025,1.4)", "iw/2-(iw/zoom/2)+on*0.15", "ih/2-(ih/zoom/2)")]
        zoom, x, y = movs[idx % len(movs)]
        filtros = [f"scale={int(ancho*1.2)}:{int(alto*1.2)}:force_original_aspect_ratio=increase", f"crop={int(ancho*1.2)}:{int(alto*1.2)}", f"zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s={ancho}x{alto}:fps={FPS}", "eq=contrast=1.15:saturation=1.25", "setsar=1", "format=yuv420p"]
        cmd = [ffmpeg, "-y", "-loop", "1", "-framerate", str(FPS), "-i", ruta, "-vf", ",".join(filtros), "-t", f"{duracion:.3f}", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-r", str(FPS), str(destino)]
    subprocess.run(cmd, check=True, capture_output=True)

async def crear_video():
    preparar_entorno()
    with open("guion.json", encoding="utf-8") as f: guion = json.load(f)
    titulo, voz, estilo = guion.get("titulo", "Viral"), guion.get("voz", "es-MX-DaliaNeural"), guion.get("estilo_visual", "Cinematic")
    escenas = guion.get("escenas", [])
    formato = {"ancho": 1080, "alto": 1920}
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    clips, duraciones = [], []

    print(f"--- PRODUCIENDO: {titulo} | VOZ: {voz} ---")
    for i, escena in enumerate(escenas):
        tipo = escena.get("tipo", "desarrollo")
        print(f"\n[ESCENA {i+1}/{len(escenas)} - {tipo.upper()}]")
        narracion = escena["narracion"]
        ruta_voz = RECURSOS / f"voz_{i}.mp3"
        marcas = await generar_voz(narracion, ruta_voz, voz)
        dur = obtener_duracion(ffmpeg, ruta_voz)
        cortes = calcular_cortes(marcas, dur)
        tomas = []
        
        for j in range(len(cortes)-1):
            d_toma = cortes[j+1] - cortes[j]
            if d_toma <= 0.4: continue
            prompt = f"{estilo}, vertical 9:16, {narracion[:100]}"
            
            # EL EQUIPO TRABAJA EN CONJUNTO SEGÚN LA ESCENA
            recurso, es_video = obtener_material_visual(prompt, i, j, d_toma, formato, tipo)
            
            ruta_toma = RECURSOS / f"toma_{i}_{j}.mp4"
            crear_toma(ffmpeg, recurso, ruta_toma, d_toma, i*10+j, formato, es_video)
            tomas.append(str(ruta_toma))
        
        ruta_vis = RECURSOS / f"vis_{i}.mp4"
        with open(RECURSOS / f"list_{i}.txt", "w") as f:
            for t in tomas: f.write(f"file '{Path(t).resolve()}'\n")
        subprocess.run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(RECURSOS / f"list_{i}.txt"), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p", "-r", str(FPS), "-an", str(ruta_vis)], check=True, capture_output=True)
        
        ruta_final = RECURSOS / f"final_{i}.mp4"
        subprocess.run([ffmpeg, "-y", "-i", str(ruta_vis), "-i", str(ruta_voz), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.3f}", str(ruta_final)], check=True, capture_output=True)
        clips.append(str(ruta_final)); duraciones.append(dur)

    video_unido = OUTPUT / "base.mp4"
    if len(clips) > 1:
        filtros, last_v, last_a, offset = [], "[v0]", "[a0]", 0.0
        for i in range(len(clips)):
            filtros.extend([f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS[v{i}]", f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]"])
        for i in range(1, len(clips)):
            offset += duraciones[i-1] - 0.4
            filtros.extend([f"{last_v}[v{i}]xfade=transition='smoothleft':duration=0.4:offset={offset:.3f}[vx{i}]", f"{last_a}[a{i}]acrossfade=d=0.4[ax{i}]"])
            last_v, last_a = f"[vx{i}]", f"[ax{i}]"
        cmd = [ffmpeg, "-y"] + sum([["-i", e] for e in clips], []) + ["-filter_complex", ";".join(filtros), "-map", last_v, "-map", last_a, "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(video_unido)]
        subprocess.run(cmd, check=True, capture_output=True)
    else:
        shutil.copy2(clips[0], video_unido)

    dur_total = obtener_duracion(ffmpeg, video_unido)
    destino = OUTPUT / "fortaleza_final.mp4"
    shutil.copy2(video_unido, destino)
    shutil.copy2(destino, OUTPUT / "fortaleza_short.mp4")
    print("\n✅ PRODUCCIÓN COMPLETADA CON TRABAJO EN EQUIPO")
    return str(destino)

if __name__ == "__main__":
    asyncio.run(crear_video())