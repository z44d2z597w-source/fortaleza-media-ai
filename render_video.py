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
from PIL import Image, ImageDraw, ImageFont

# ==========================================================
# FORTALEZA MEDIA AI 22.0 — CONECTADO A AGNES Y MAGIC HOUR
# ==========================================================

FPS = 30
OUTPUT = Path("output")
RECURSOS = OUTPUT / "recursos"
MAX_ESCENAS = 20

CONFIG_DEFECTO = {"corte_min": 1.5, "corte_max": 3.5}
PALABRAS_IMPACTO = ["increíble", "sorprendente", "misterio", "secreto", "peligro", "jamás", "nunca", "impactante", "aterrador", "asombroso", "oculto", "verdad", "ciencia", "descubrimiento", "tendencia", "viral", "drama", "historia", "enigma", "prohibido"]

def preparar_carpetas():
    OUTPUT.mkdir(exist_ok=True)
    RECURSOS.mkdir(exist_ok=True)
    for f in RECURSOS.iterdir():
        if f.is_file(): f.unlink()

def obtener_fuente_texto(tamano, negrita=False):
    rutas = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if negrita else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if negrita else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for r in rutas:
        if os.path.exists(r): return ImageFont.truetype(r, tamano)
    return ImageFont.load_default()

def ejecutar_ffmpeg(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0: raise RuntimeError(f"FFmpeg error:\n{res.stderr[-3000:]}")
    return res

def obtener_duracion(ffmpeg, archivo):
    res = subprocess.run([ffmpeg, "-i", str(archivo)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", res.stderr)
    if not m: raise RuntimeError(f"No se pudo leer duración de {archivo}")
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)

def calcular_cortes(palabras, duracion_total):
    if duracion_total <= 0: return [0.0, duracion_total]
    puntos = []
    for i in range(1, len(palabras)):
        if palabras[i]["inicio"] - palabras[i-1]["fin"] >= 0.25:
            puntos.append((palabras[i-1]["fin"] + palabras[i]["inicio"]) / 2)
    for p in palabras:
        if p["texto"].strip().endswith((".", "?", "!")): puntos.append(p["fin"] + 0.05)
    
    puntos = sorted(set(round(c, 3) for c in puntos))
    cortes = [0.0]
    for c in puntos:
        if c < 5.0:
            if c - cortes[-1] >= 1.2: cortes.append(c)
        else:
            if c - cortes[-1] >= CONFIG_DEFECTO["corte_min"] and duracion_total - c >= CONFIG_DEFECTO["corte_min"]: 
                cortes.append(c)
                
    resultado = [0.0]
    for c in cortes[1:]:
        while c - resultado[-1] > CONFIG_DEFECTO["corte_max"]: resultado.append(resultado[-1] + CONFIG_DEFECTO["corte_max"])
        resultado.append(c)
    while duracion_total - resultado[-1] > CONFIG_DEFECTO["corte_max"]: resultado.append(resultado[-1] + CONFIG_DEFECTO["corte_max"])
    if resultado[-1] < duracion_total: resultado.append(duracion_total)
    else: resultado[-1] = duracion_total
    return resultado

# --- GENERADORES DE VIDEO IA ---

def generar_video_agnes(prompt, duracion):
    api_key = os.environ.get("AGNES_API_KEY")
    if not api_key: return None
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": "agnes-video-v2.0", "prompt": prompt, "duration": min(5, int(duracion)+1), "aspect_ratio": "9:16"}
    try:
        resp = requests.post("https://apihub.agnes-ai.cn/v1/video/generations", headers=headers, json=payload, timeout=60)
        task_id = resp.json().get("id") or resp.json().get("task_id")
        if not task_id: return None
        
        for _ in range(60):
            time.sleep(10)
            poll = requests.get(f"https://apihub.agnes-ai.cn/v1/video/generations/{task_id}", headers=headers).json()
            if poll.get("status") == "succeeded":
                url = poll.get("output", {}).get("video_url")
                if url:
                    ruta = RECURSOS / f"agnes_{task_id}.mp4"
                    with requests.get(url, stream=True, timeout=120) as r:
                        r.raise_for_status()
                        with open(ruta, "wb") as f:
                            for chunk in r.iter_content(8192): f.write(chunk)
                    print("[AGNES] Video descargado con éxito.")
                    return str(ruta)
            elif poll.get("status") == "failed": return None
    except Exception as e:
        print(f"[AGNES] Error: {e}")
        return None

def generar_video_magichour(prompt, duracion):
    api_key = os.environ.get("MAGIC_HOUR_API_KEY")
    if not api_key: return None
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"prompt": prompt, "model": "wan-2.2", "duration_seconds": min(5, int(duracion)+1), "resolution": "480p", "aspect_ratio": "9:16"}
    try:
        resp = requests.post("https://api.magichour.ai/v1/text-to-video", headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        video_url = resp.json().get("video_url")
        if video_url:
            ruta = RECURSOS / f"magichour_{int(time.time())}.mp4"
            with requests.get(video_url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(ruta, "wb") as f:
                    for chunk in r.iter_content(8192): f.write(chunk)
            print("[MAGIC HOUR] Video descargado con éxito.")
            return str(ruta)
    except Exception as e:
        print(f"[MAGIC HOUR] Error: {e}")
        return None

def generar_imagen_pollinations(prompt, num_escena, num_toma, formato):
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width={formato['ancho']}&height={formato['alto']}&nologo=true&model=flux"
    try:
        resp = requests.get(url, timeout=60)
        ruta = RECURSOS / f"ia_{num_escena:02d}_{num_toma:02d}.jpg"
        with open(ruta, "wb") as f: f.write(resp.content)
        Image.open(ruta).verify()
        print("[POLLINATIONS] Imagen de respaldo generada.")
        return str(ruta)
    except Exception as e:
        print(f"[POLLINATIONS] Error: {e}")
        return None

async def generar_voz(texto, ruta, voz_elegida):
    tts = edge_tts.Communicate(texto, voice=voz_elegida, rate="+8%")
    audio, marcas = bytearray(), []
    async for f in tts.stream():
        if f["type"] == "audio": audio.extend(f["data"])
        elif f["type"] == "WordBoundary":
            inicio = f["offset"] / 10000000
            marcas.append({"texto": f["text"], "inicio": inicio, "fin": inicio + (f["duration"] / 10000000)})
    with open(ruta, "wb") as f: f.write(audio)
    return marcas

def generar_whoosh(ruta):
    frec, dur = 44100, 0.4
    datos = array("h")
    for i in range(int(frec * dur)):
        t = i / frec
        vol = (t / dur) * (1 - t / dur) * 4
        ruido = random.uniform(-1, 1)
        datos.append(int(32767 * 0.25 * vol * ruido)); datos.append(int(32767 * 0.25 * vol * ruido))
    with wave.open(str(ruta), "wb") as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(frec)
        f.writeframes(datos.tobytes())
    return str(ruta)

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

def crear_scroll_stopper(formato):
    ancho, alto = formato["ancho"], formato["alto"]
    img = Image.new("RGBA", (ancho, alto), (0,0,0,0))
    d = ImageDraw.Draw(img)
    font = obtener_fuente_texto(int(ancho * 0.12), True)
    d.rectangle((0, int(alto*0.35), ancho, int(alto*0.55)), fill=(220, 20, 20, 230))
    d.text((ancho//2, int(alto*0.45)), "¡NO LO VAS\nA CREER!", font=font, fill="white", anchor="mm", align="center", stroke_width=6, stroke_fill="#000000")
    ruta = RECURSOS / "scroll.png"
    img.save(ruta)
    return str(ruta)

def crear_toma_visual(ffmpeg, ruta_recurso, destino, duracion, idx, formato, es_video):
    ancho, alto = formato["ancho"], formato["alto"]
    
    if es_video:
        # Si es un video real de Agnes/Magic Hour, solo lo recortamos y ajustamos
        filtros = [f"scale={ancho}:{alto}:force_original_aspect_ratio=increase", f"crop={ancho}:{alto}", "setsar=1", "format=yuv420p"]
        cmd = [ffmpeg, "-y", "-stream_loop", "-1", "-i", ruta_recurso, "-vf", ",".join(filtros), "-t", f"{duracion:.3f}", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-r", str(FPS), str(destino)]
    else:
        # Si es imagen de Pollinations, le aplicamos zoom y movimientos
        movimientos = [
            ("min(zoom+0.0015,1.3)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
            ("min(zoom+0.0025,1.4)", "iw/2-(iw/zoom/2)+on*0.15", "ih/2-(ih/zoom/2)"),
            ("max(zoom-0.0010,1.0)", "iw/2-(iw/zoom/2)-on*0.10", "ih/2-(ih/zoom/2)"),
        ]
        zoom, x, y = movimientos[idx % len(movimientos)]
        zoompan = f"zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s={ancho}x{alto}:fps={FPS}"
        
        filtros = [
            f"scale={int(ancho*1.2)}:{int(alto*1.2)}:force_original_aspect_ratio=increase",
            f"crop={int(ancho*1.2)}:{int(alto*1.2)}",
            zoompan,
            "eq=contrast=1.15:saturation=1.25",
            "setsar=1", "format=yuv420p"
        ]
        cmd = [ffmpeg, "-y", "-loop", "1", "-framerate", str(FPS), "-i", ruta_recurso, "-vf", ",".join(filtros), "-t", f"{duracion:.3f}", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-r", str(FPS), str(destino)]
        
    ejecutar_ffmpeg(cmd)

def mezcla_final(ffmpeg, video, musica, whooshes, destino, duracion):
    f_vid = f"[0:v]vignette=PI/6,drawbox=x=0:y=h-10:w='iw*t/{duracion}':h=10:color=red@0.9:t=fill,format=yuv420p[vout]"
    f_aud = "[1:a]volume=0.15[musica];[0:a]volume=1.0[voz];[musica][voz]sidechaincompress=threshold=0.03:ratio=8:attack=200:release=1000[musica_duck];[voz][musica_duck]amix=inputs=2:duration=first[base];"
    if whooshes:
        labels = ""
        for i in range(len(whooshes)):
            f_aud += f"[{i+2}:a]volume=0.6[w{i}];"
            labels += f"[w{i}]"
        f_aud += f"[base]{labels}amix=inputs={len(whooshes)+1}:duration=first[audio_mixed];"
    else:
        f_aud += "[base]anull[audio_mixed];"
    f_aud += "[audio_mixed]alimiter=limit=0.95[audio]"

    cmd = [ffmpeg, "-y", "-i", video, "-stream_loop", "-1", "-i", musica]
    for w in whooshes: cmd.extend(["-i", w])
    cmd.extend(["-filter_complex", f_vid + ";" + f_aud, "-map", "[vout]", "-map", "[audio]", "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", f"{duracion:.3f}", "-movflags", "+faststart", destino])
    ejecutar_ffmpeg(cmd)

async def crear_video():
    preparar_carpetas()
    with open("guion.json", encoding="utf-8") as f: guion = json.load(f)
    
    titulo = str(guion.get("titulo", "Viral"))
    voz_elegida = str(guion.get("voz", "es-MX-DaliaNeural"))
    estilo_visual = str(guion.get("estilo_visual", "Cinematic 8k"))
    
    escenas = [e for e in guion.get("escenas", []) if str(e.get("narracion", "")).strip()][:MAX_ESCENAS]
    formato = {"nombre": "vertical", "ancho": 1080, "alto": 1920}
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    
    escenas_finales, duraciones_finales = [], []
    whoosh = generar_whoosh(RECURSOS / "whoosh.wav")
    scroll = crear_scroll_stopper(formato)

    print("============================================================")
    print(f"FORTALEZA MEDIA AI 22.0 — PRODUCIENDO: {titulo}")
    print(f"VOZ: {voz_elegida} | ESTILO: {estilo_visual}")
    print("============================================================")

    for num_escena, datos in enumerate(escenas):
        print(f"\n[ESCENA {num_escena + 1}/{len(escenas)}]")
        narracion = str(datos["narracion"]).strip()
        ruta_voz = RECURSOS / f"voz_{num_escena:02d}.mp3"
        
        marcas = await generar_voz(narracion, str(ruta_voz), voz_elegida)
        dur_voz = obtener_duracion(ffmpeg, ruta_voz)
        
        cortes = calcular_cortes(marcas, dur_voz)
        num_tomas = max(1, len(cortes) - 1)

        tomas_mp4 = []
        for i in range(num_tomas):
            dur = cortes[i+1] - cortes[i]
            if dur <= 0.4: continue
            
            ruta_toma = RECURSOS / f"toma_{num_escena:02d}_{i:02d}.mp4"
            prompt = f"{estilo_visual}, vertical 9:16, {narracion[:120]}"
            
            # 1. Intentar con Agnes
            video_ia = generar_video_agnes(prompt, dur)
            es_video = True
            
            # 2. Si falla, intentar con Magic Hour
            if not video_ia:
                print("[RESPALDO] Agnes falló. Intentando Magic Hour...")
                video_ia = generar_video_magichour(prompt, dur)
            
            # 3. Si ambos fallan, generar imagen con Pollinations
            if not video_ia:
                print("[RESPALDO] Magic Hour falló. Generando imagen...")
                video_ia = generar_imagen_pollinations(prompt, num_escena, i, formato)
                es_video = False
                
            if video_ia:
                crear_toma_visual(ffmpeg, video_ia, ruta_toma, dur, num_escena*10+i, formato, es_video)
                tomas_mp4.append(str(ruta_toma))

        ruta_visual = RECURSOS / f"vis_{num_escena:02d}.mp4"
        with open(RECURSOS / f"list_{num_escena:02d}.txt", "w") as f:
            for t in tomas_mp4: f.write(f"file '{Path(t).resolve()}'\n")
        ejecutar_ffmpeg([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(RECURSOS / f"list_{num_escena:02d}.txt"), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p", "-r", str(FPS), "-an", str(ruta_visual)])

        cmd_comp = [ffmpeg, "-y", "-i", str(ruta_visual), "-i", str(ruta_voz)]
        if num_escena == 0:
            cmd_comp.extend(["-loop", "1", "-framerate", str(FPS), "-i", scroll])
            cmd_comp.extend(["-filter_complex", f"[0:v][2:v]overlay=0:0:enable='between(t,0,2)'[vout]", "-map", "[vout]", "-map", "1:a"])
        else:
            cmd_comp.extend(["-map", "0:v", "-map", "1:a"])
        
        ruta_final_escena = RECURSOS / f"final_{num_escena:02d}.mp4"
        cmd_comp.extend(["-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", f"{dur_voz:.3f}", str(ruta_final_escena)])
        ejecutar_ffmpeg(cmd_comp)
        escenas_finales.append(str(ruta_final_escena))
        duraciones_finales.append(obtener_duracion(ffmpeg, ruta_final_escena))

    print("\n[RENDER] Uniendo escenas...")
    video_unido = OUTPUT / "base.mp4"
    if len(escenas_finales) > 1:
        filtros = []
        last_v, last_a, offset = "[v0]", "[a0]", 0.0
        for i in range(len(escenas_finales)):
            filtros.extend([f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS[v{i}]", f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]"])
        for i in range(1, len(escenas_finales)):
            offset += duraciones_finales[i-1] - 0.4
            filtros.extend([f"{last_v}[v{i}]xfade=transition='smoothleft':duration=0.4:offset={offset:.3f}[vx{i}]", f"{last_a}[a{i}]acrossfade=d=0.4[ax{i}]"])
            last_v, last_a = f"[vx{i}]", f"[ax{i}]"
        cmd = [ffmpeg, "-y"] + sum([["-i", e] for e in escenas_finales], []) + ["-filter_complex", ";".join(filtros), "-map", last_v, "-map", last_a, "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(video_unido)]
        ejecutar_ffmpeg(cmd)
    else:
        shutil.copy2(escenas_finales[0], video_unido)

    dur_total = obtener_duracion(ffmpeg, video_unido)
    musica = generar_musica(max(10, int(dur_total) + 5))
    whooshes = [whoosh] * int(dur_total // 2.5)
    destino = OUTPUT / "fortaleza_final.mp4"
    
    print("[RENDER] Mezclando audio y aplicando edición final...")
    mezcla_final(ffmpeg, str(video_unido), musica, whooshes, str(destino), dur_total)
    shutil.copy2(destino, OUTPUT / "fortaleza_short.mp4")
    
    print("\n✅ PRODUCCIÓN COMPLETADA")
    return str(destino)

if __name__ == "__main__":
    asyncio.run(crear_video())