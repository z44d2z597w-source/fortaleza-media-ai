import asyncio
import json
import math
import os
import random
import re
import shutil
import subprocess
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
# FORTALEZA MEDIA AI 21.0 — EDICIÓN DINÁMICA Y ORIGINAL
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

def dividir_texto(dibujo, texto, font, ancho_max):
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = (actual + " " + palabra).strip()
        if dibujo.textbbox((0, 0), prueba, font=font)[2] <= ancho_max: actual = prueba
        else:
            if actual: lineas.append(actual)
            actual = palabra
    if actual: lineas.append(actual)
    return lineas

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
            if c - cortes[-1] >= 1.2: cortes.append(c) # Cortes ultrarrápidos al inicio
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

def generar_imagen_ia(prompt, num_escena, num_toma, formato, estilo_visual):
    print(f"[IA VISUAL] Generando imagen {num_escena}-{num_toma} estilo: {estilo_visual}...")
    # Mezclamos el estilo visual elegido por el cerebro con la narración
    prompt_completo = f"{estilo_visual}, vertical 9:16, {prompt}"
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt_completo)}?width={formato['ancho']}&height={formato['alto']}&nologo=true&model=flux"
    try:
        resp = requests.get(url, timeout=60)
        ruta = RECURSOS / f"ia_{num_escena:02d}_{num_toma:02d}.jpg"
        with open(ruta, "wb") as f: f.write(resp.content)
        Image.open(ruta).verify()
        return str(ruta)
    except Exception as e:
        print(f"[IA VISUAL] Error: {e}")
        return None

async def generar_voz(texto, ruta, voz_elegida):
    print(f"[VOZ] Generando audio con: {voz_elegida}")
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

def crear_toma(ffmpeg, ruta_img, destino, duracion, idx, formato, es_impacto):
    ancho, alto = formato["ancho"], formato["alto"]
    
    # 10 Movimientos de cámara para que NUNCA se vea estático
    movimientos = [
        ("min(zoom+0.0015,1.3)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"), # Zoom In
        ("min(zoom+0.0025,1.4)", "iw/2-(iw/zoom/2)+on*0.15", "ih/2-(ih/zoom/2)"), # Zoom + Paneo Der
        ("max(zoom-0.0010,1.0)", "iw/2-(iw/zoom/2)-on*0.10", "ih/2-(ih/zoom/2)"), # Zoom Out + Paneo Izq
        ("min(zoom+0.0015,1.3)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)+on*0.15"), # Zoom + Paneo Abajo
        ("min(zoom+0.0020,1.35)", "iw/2-(iw/zoom/2)+on*0.20", "ih/2-(ih/zoom/2)"), # Paneo Rápido Der
        ("max(zoom-0.0015,1.0)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)-on*0.15"), # Zoom Out + Paneo Arriba
        ("min(zoom+0.0012,1.25)", "iw/2-(iw/zoom/2)-on*0.10", "ih/2-(ih/zoom/2)-on*0.10"), # Diagonal
        ("min(zoom+0.0030,1.5)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"), # Zoom Rápido
    ]
    zoom, x, y = movimientos[idx % len(movimientos)]

    if es_impacto:
        # Efecto de golpe visual (Zoom punch)
        zoompan = f"zoompan=z='if(lt(on,15),1.6-on/25,1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={ancho}x{alto}:fps={FPS}"
    else:
        zoompan = f"zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s={ancho}x{alto}:fps={FPS}"

    filtros = [
        f"scale={int(ancho*1.3)}:{int(alto*1.3)}:force_original_aspect_ratio=increase",
        f"crop={int(ancho*1.3)}:{int(alto*1.3)}",
        zoompan,
        "eq=contrast=1.15:brightness=-0.02:saturation=1.25",
        "unsharp=5:5:0.8:5:5:0.0"
    ]
    
    if es_impacto:
        filtros.append("rgbashift=rh=10:bh=-10:enable='lt(t,0.25)'")
        
    filtros.extend(["setsar=1", "format=yuv420p"])
    
    cmd = [ffmpeg, "-y", "-loop", "1", "-framerate", str(FPS), "-i", ruta_img, "-vf", ",".join(filtros), "-t", f"{duracion:.3f}", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p", "-r", str(FPS), str(destino)]
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
    voz_elegida = str(guion.get("voz", "es-MX-DaliaNeural")) # Leemos la voz
    estilo_visual = str(guion.get("estilo_visual", "Cinematic 8k")) # Leemos el estilo
    
    escenas = [e for e in guion.get("escenas", []) if str(e.get("narracion", "")).strip()][:MAX_ESCENAS]
    formato = {"nombre": "vertical", "ancho": 1080, "alto": 1920}
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    
    escenas_finales, duraciones_finales = [], []
    whoosh = generar_whoosh(RECURSOS / "whoosh.wav")
    scroll = crear_scroll_stopper(formato)

    print("============================================================")
    print(f"FORTALEZA MEDIA AI 21.0 — PRODUCIENDO: {titulo}")
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
            
            # Generamos imagen IA con el estilo elegido
            img_ia = generar_imagen_ia(narracion[:120], num_escena, i, formato, estilo_visual)
            if img_ia:
                crear_toma(ffmpeg, img_ia, ruta_toma, dur, num_escena*10+i, formato, (i==0))
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
    
    print("\n============================================================")
    print("✅ PRODUCCIÓN 21.0 COMPLETADA CON ÉXITO")
    print("============================================================")
    return str(destino)

if __name__ == "__main__":
    asyncio.run(crear_video())