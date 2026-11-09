import asyncio
import html
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
from PIL import (
    Image, ImageDraw, ImageFont, ImageEnhance,
    ImageFilter, ImageOps,
)

# ==========================================================
# FORTALEZA MEDIA AI 19.0 — AGNES VIDEO IA TOTAL
# ==========================================================

FPS = 30
VOZ = "es-MX-DaliaNeural"
VELOCIDAD_VOZ = "+8%"

OUTPUT = Path("output")
RECURSOS = OUTPUT / "recursos"
ARCHIVO_CONFIG = Path("config_edicion.json")
REPORTE_PRODUCCION = OUTPUT / "reporte_edicion.json"

MAX_ESCENAS = 20

CONFIG_DEFECTO = {
    "corte_min": 1.5,
    "corte_max": 3.5,
    "score_global": 0,
    "intentos": 0,
}

PALABRAS_IMPACTO = [
    "increíble", "sorprendente", "misterio", "secreto", "peligro", 
    "jamás", "nunca", "impactante", "aterrador", "asombroso", 
    "oculto", "verdad", "ciencia", "descubrimiento", "tendencia", 
    "viral", "drama", "historia", "enigma", "prohibido"
]

CABECERAS = {"User-Agent": "FortalezaMediaAI/19.0 python-requests"}

# --- CONFIGURACIÓN DE AGNES VIDEO ---
AGNES_API_KEY = "sk-wtQ84SRJzizAfKWm9m6hbzqYvg5S7rR2ZDlLKcHouC29ncpA"
AGNES_BASE_URL = "https://apihub.agnes-ai.cn/v1"
AGNES_MODEL = "agnes-video-v2.0"

PALETAS = [
    ("#071426", "#123D60", "#39B8D8"), ("#180D2C", "#43205E", "#B56CFF"),
    ("#111B18", "#245B43", "#65D6A0"), ("#29100D", "#74301F", "#FFAD64"),
    ("#10152C", "#293D75", "#82A7FF"), ("#25152B", "#63344E", "#FF83AE"),
]

def cargar_configuracion_evolutiva():
    if ARCHIVO_CONFIG.exists():
        try:
            with open(ARCHIVO_CONFIG, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return CONFIG_DEFECTO.copy()

def evaluar_y_mutar(config, metricas):
    print("\n[EVOLUCIÓN] Evaluando calidad...")
    score_pacing = 50
    if metricas["promedio_toma"] < 2.2: score_pacing += 35
    elif metricas["promedio_toma"] < 3.0: score_pacing += 20
    score_global = int((score_pacing + 80 + 80 + 50) / 4)
    config["score_global"] = score_global
    config["intentos"] = config.get("intentos", 0) + 1
    with open(ARCHIVO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    print(f"[EVOLUCIÓN] Score Final: {score_global}/100")
    return config

CONFIG = cargar_configuracion_evolutiva()

def preparar_carpetas_de_trabajo():
    OUTPUT.mkdir(exist_ok=True)
    RECURSOS.mkdir(exist_ok=True)
    for archivo in RECURSOS.iterdir():
        if archivo.is_file(): archivo.unlink()

def obtener_fuente_texto(tamano, negrita=False):
    rutas = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if negrita else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if negrita else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for ruta in rutas:
        if os.path.exists(ruta): return ImageFont.truetype(ruta, tamano)
    return ImageFont.load_default()

def ejecutar_comando_ffmpeg(comando):
    resultado = subprocess.run(comando, capture_output=True, text=True)
    if resultado.returncode != 0:
        raise RuntimeError(f"FALLO FFmpeg:\n{resultado.stderr[-6000:]}")
    return resultado

def obtener_duracion_media(ffmpeg, archivo):
    resultado = subprocess.run([ffmpeg, "-i", str(archivo)], capture_output=True, text=True)
    coincidencia = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", resultado.stderr)
    if not coincidencia: raise RuntimeError(f"Error duración: {archivo}")
    h, m, s = coincidencia.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)

def hex_a_rgb(codigo_hex):
    codigo_hex = codigo_hex.lstrip("#")
    return tuple(int(codigo_hex[i:i + 2], 16) for i in (0, 2, 4))

def dividir_texto_en_lineas(dibujo, texto, font, ancho_maximo):
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = (actual + " " + palabra).strip()
        if dibujo.textbbox((0, 0), prueba, font=font)[2] <= ancho_maximo:
            actual = prueba
        else:
            if actual: lineas.append(actual)
            actual = palabra
    if actual: lineas.append(actual)
    return lineas

def calcular_tiempos_de_corte(palabras, duracion_total):
    c_min, c_max = CONFIG.get("corte_min", 1.5), CONFIG.get("corte_max", 3.5)
    if duracion_total <= 0: return [0.0, duracion_total]
    puntos = []
    for i in range(1, len(palabras)):
        if palabras[i]["inicio"] - palabras[i - 1]["fin"] >= 0.25:
            puntos.append((palabras[i - 1]["fin"] + palabras[i]["inicio"]) / 2)
    for p in palabras:
        if p["texto"].strip().endswith((".", "?", "!")): puntos.append(p["fin"] + 0.05)
    puntos = sorted(set(round(c, 3) for c in puntos))
    cortes = [0.0]
    for c in puntos:
        if c < 5.0:
            if c - cortes[-1] >= 1.2: cortes.append(c)
        else:
            if c - cortes[-1] >= c_min and duracion_total - c >= c_min: cortes.append(c)
    resultado = [0.0]
    for c in cortes[1:]:
        while c - resultado[-1] > c_max: resultado.append(resultado[-1] + c_max)
        resultado.append(c)
    while duracion_total - resultado[-1] > c_max: resultado.append(resultado[-1] + c_max)
    if resultado[-1] < duracion_total: resultado.append(duracion_total)
    else: resultado[-1] = duracion_total
    return resultado

def ajustar_recursos(recursos, cantidad):
    if cantidad <= len(recursos): return recursos[:cantidad]
    return [recursos[i % len(recursos)] for i in range(cantidad)]

# --- GENERACIÓN DE VIDEO CON AGNES ---

def generar_video_agnes(prompt, duracion_sugerida=5):
    """Genera un video corto con Agnes Video 2.0."""
    print(f"[AGNES] Generando video: '{prompt[:60]}...'")
    
    headers = {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": AGNES_MODEL,
        "prompt": prompt,
        "duration": duracion_sugerida,
        "aspect_ratio": "9:16"
    }
    
    try:
        # 1. Enviar tarea
        resp = requests.post(f"{AGNES_BASE_URL}/video/generations", headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        task_id = data.get("id") or data.get("task_id")
        if not task_id:
            print("[AGNES] No se recibió ID de tarea.")
            return None
        
        # 2. Polling
        for intento in range(60):
            time.sleep(10)
            poll_resp = requests.get(f"{AGNES_BASE_URL}/video/generations/{task_id}", headers=headers, timeout=30)
            poll_data = poll_resp.json()
            estado = poll_data.get("status")
            if estado == "succeeded":
                video_url = poll_data.get("output", {}).get("video_url")
                if video_url:
                    ruta = RECURSOS / f"agnes_{task_id}.mp4"
                    with requests.get(video_url, stream=True, timeout=120) as r:
                        r.raise_for_status()
                        with open(ruta, "wb") as f:
                            for chunk in r.iter_content(8192): f.write(chunk)
                    print(f"[AGNES] Video descargado: {ruta}")
                    return str(ruta)
            elif estado == "failed":
                print(f"[AGNES] Tarea fallida: {poll_data}")
                return None
        print("[AGNES] Tiempo de espera agotado.")
        return None
    except Exception as e:
        print(f"[AGNES] Error: {e}")
        return None

def generar_imagen_ia(prompt, num_escena, num_toma, formato):
    """Respaldo: imagen generada con Pollinations."""
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width={formato['ancho']}&height={formato['alto']}&nologo=true&model=flux"
    try:
        respuesta = requests.get(url, timeout=60)
        ruta = RECURSOS / f"ia_{num_escena:02d}_{num_toma:02d}.jpg"
        with open(ruta, "wb") as f: f.write(respuesta.content)
        Image.open(ruta).verify()
        return str(ruta)
    except Exception: return None

# --- AUDIO Y GRÁFICOS ---

async def generar_voz(texto, ruta):
    tts = edge_tts.Communicate(texto, voice=VOZ, rate=VELOCIDAD_VOZ)
    audio, marcas = bytearray(), []
    async for f in tts.stream():
        if f["type"] == "audio": audio.extend(f["data"])
        elif f["type"] == "WordBoundary":
            inicio = f["offset"] / 10000000
            marcas.append({"texto": f["text"], "inicio": inicio, "fin": inicio + (f["duration"] / 10000000)})
    with open(ruta, "wb") as f: f.write(audio)
    return marcas

def generar_whoosh(ruta):
    frecuencia, duracion = 44100, 0.4
    datos = array("h")
    for i in range(int(frecuencia * duracion)):
        t = i / frecuencia
        vol = (t / duracion) * (1 - t / duracion) * 4
        ruido = random.uniform(-1, 1)
        datos.append(int(32767 * 0.25 * vol * ruido)); datos.append(int(32767 * 0.25 * vol * ruido))
    with wave.open(str(ruta), "wb") as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(frecuencia)
        f.writeframes(datos.tobytes())
    return str(ruta)

def generar_musica(duracion):
    ruta = RECURSOS / "musica.wav"
    frecuencia = 22050
    datos = array("h")
    for i in range(int(frecuencia * duracion)):
        t = i / frecuencia
        sonido = (math.sin(2*math.pi*110*t)*0.26 + math.sin(2*math.pi*164.81*t)*0.18)
        valor = int(32767 * 0.05 * sonido)
        datos.append(valor); datos.append(valor)
    with wave.open(str(ruta), "wb") as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(frecuencia)
        f.writeframes(datos.tobytes())
    return str(ruta)

def crear_scroll_stopper(formato):
    ancho, alto = formato["ancho"], formato["alto"]
    imagen = Image.new("RGBA", (ancho, alto), (0,0,0,0))
    dibujo = ImageDraw.Draw(imagen)
    font = obtener_fuente_texto(int(ancho * 0.12), True)
    dibujo.rectangle((0, int(alto*0.35), ancho, int(alto*0.55)), fill=(220, 20, 20, 230))
    dibujo.text((ancho//2, int(alto*0.45)), "¡NO LO VAS\nA CREER!", font=font, fill="white", anchor="mm", align="center", stroke_width=6, stroke_fill="#000000")
    ruta = RECURSOS / "scroll.png"
    imagen.save(ruta)
    return str(ruta)

# --- RENDERIZADO ---

def crear_toma_video(ffmpeg, ruta_video, destino, duracion, formato):
    """Toma un clip de video generado por Agnes y lo ajusta a la duración y formato."""
    ancho, alto = formato["ancho"], formato["alto"]
    # Recortar y escalar al formato vertical
    filtros = [
        f"scale={ancho}:{alto}:force_original_aspect_ratio=increase",
        f"crop={ancho}:{alto}",
        "setsar=1",
        "format=yuv420p"
    ]
    cmd = [
        ffmpeg, "-y", "-i", ruta_video,
        "-vf", ",".join(filtros),
        "-t", f"{duracion:.3f}",
        "-an",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        str(destino)
    ]
    ejecutar_comando_ffmpeg(cmd)

def crear_toma_imagen(ffmpeg, ruta_imagen, destino, duracion, formato):
    """Respaldo: anima una imagen generada por Pollinations."""
    ancho, alto = formato["ancho"], formato["alto"]
    filtros = [
        f"scale={int(ancho*1.2)}:{int(alto*1.2)}:force_original_aspect_ratio=increase",
        f"crop={int(ancho*1.2)}:{int(alto*1.2)}",
        "zoompan=z='min(zoom+0.0015,1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={ancho}x{alto}:fps={FPS}",
        "eq=contrast=1.18:saturation=1.30:gamma=0.95",
        "setsar=1",
        "format=yuv420p"
    ]
    cmd = [
        ffmpeg, "-y", "-loop", "1", "-framerate", str(FPS), "-i", ruta_imagen,
        "-vf", ",".join(filtros),
        "-t", f"{duracion:.3f}", "-an",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        str(destino)
    ]
    ejecutar_comando_ffmpeg(cmd)

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
    ejecutar_comando_ffmpeg(cmd)

# --- ORQUESTADOR ---

async def crear_video():
    preparar_carpetas_de_trabajo()
    with open("guion.json", encoding="utf-8") as f: guion = json.load(f)

    titulo = str(guion.get("titulo", "Viral"))
    escenas = [e for e in guion.get("escenas", []) if str(e.get("narracion", "")).strip()][:MAX_ESCENAS]
    formato = {"nombre": "vertical", "ancho": 1080, "alto": 1920, "orientacion": "vertical"}
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    metricas = {"total_tomas": 0, "duracion_total_tomas": 0}
    escenas_finales, duraciones_finales = [], []
    whoosh = generar_whoosh(RECURSOS / "whoosh.wav")
    scroll = crear_scroll_stopper(formato)

    print("============================================================")
    print("FORTALEZA MEDIA AI 19.0 — GENERACIÓN CON AGNES VIDEO")
    print("============================================================")

    for num_escena, datos in enumerate(escenas):
        print(f"\n[ESCENA {num_escena + 1}/{len(escenas)}]")
        narracion = str(datos["narracion"]).strip()
        
        # 1. Voz
        ruta_voz = RECURSOS / f"voz_{num_escena:02d}.mp3"
        marcas = await generar_voz(narracion, str(ruta_voz))
        dur_voz = obtener_duracion_media(ffmpeg, ruta_voz)

        # 2. Cortes
        cortes = calcular_tiempos_de_corte(marcas, dur_voz)
        num_tomas = max(1, len(cortes) - 1)

        # 3. Generar material visual para cada toma
        tomas_mp4 = []
        for i in range(num_tomas):
            dur = cortes[i + 1] - cortes[i]
            if dur <= 0.4: continue
            
            ruta_toma = RECURSOS / f"toma_{num_escena:02d}_{i:02d}.mp4"
            
            # Intentar generar video con Agnes
            prompt_video = f"Cinematic vertical 9:16, dramatic lighting, {narracion[:120]}"
            video_agnes = generar_video_agnes(prompt_video, duracion_sugerida=min(5, int(dur) + 1))
            
            if video_agnes:
                crear_toma_video(ffmpeg, video_agnes, ruta_toma, dur, formato)
            else:
                # Respaldo: imagen de Pollinations animada
                print("[RESPALDO] Agnes falló. Generando imagen con Pollinations...")
                img = generar_imagen_ia(prompt_video, num_escena, i, formato)
                if img:
                    crear_toma_imagen(ffmpeg, img, ruta_toma, dur, formato)
                else:
                    # Último recurso: fondo negro
                    ruta_fondo = RECURSOS / f"fondo_{num_escena}_{i}.jpg"
                    Image.new("RGB", (formato["ancho"], formato["alto"]), "#101010").save(ruta_fondo)
                    crear_toma_imagen(ffmpeg, str(ruta_fondo), ruta_toma, dur, formato)
            
            tomas_mp4.append(str(ruta_toma))
            metricas["total_tomas"] += 1
            metricas["duracion_total_tomas"] += dur

        # 4. Concatenar tomas de la escena
        ruta_visual = RECURSOS / f"vis_{num_escena:02d}.mp4"
        with open(RECURSOS / f"list_{num_escena:02d}.txt", "w") as f:
            for t in tomas_mp4: f.write(f"file '{Path(t).resolve()}'\n")
        ejecutar_comando_ffmpeg([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(RECURSOS / f"list_{num_escena:02d}.txt"), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p", "-r", str(FPS), "-an", str(ruta_visual)])

        # 5. Añadir voz y scroll stopper (solo escena 1)
        cmd_comp = [ffmpeg, "-y", "-i", str(ruta_visual), "-i", str(ruta_voz)]
        if num_escena == 0:
            cmd_comp.extend(["-loop", "1", "-framerate", str(FPS), "-i", scroll])
            cmd_comp.extend(["-filter_complex", f"[0:v][2:v]overlay=0:0:enable='between(t,0,2)'[vout]", "-map", "[vout]", "-map", "1:a"])
        else:
            cmd_comp.extend(["-map", "0:v", "-map", "1:a"])
        
        ruta_final_escena = RECURSOS / f"final_{num_escena:02d}.mp4"
        cmd_comp.extend(["-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", f"{dur_voz:.3f}", str(ruta_final_escena)])
        ejecutar_comando_ffmpeg(cmd_comp)

        escenas_finales.append(str(ruta_final_escena))
        duraciones_finales.append(obtener_duracion_media(ffmpeg, ruta_final_escena))

    # 6. Unir escenas con XFade
    print("\n[RENDER] Uniendo escenas...")
    video_unido = OUTPUT / "base.mp4"
    if len(escenas_finales) > 1:
        filtros = []
        last_v, last_a, offset = "[v0]", "[a0]", 0.0
        for i in range(len(escenas_finales)):
            filtros.extend([f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS[v{i}]", f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]"])
        for i in range(1, len(escenas_finales)):
            offset += duraciones_finales[i - 1] - 0.4
            filtros.extend([f"{last_v}[v{i}]xfade=transition='smoothleft':duration=0.4:offset={offset:.3f}[vx{i}]", f"{last_a}[a{i}]acrossfade=d=0.4[ax{i}]"])
            last_v, last_a = f"[vx{i}]", f"[ax{i}]"
        cmd = [ffmpeg, "-y"] + sum([["-i", e] for e in escenas_finales], []) + ["-filter_complex", ";".join(filtros), "-map", last_v, "-map", last_a, "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(video_unido)]
        ejecutar_comando_ffmpeg(cmd)
    else:
        shutil.copy2(escenas_finales[0], video_unido)

    # 7. Mezcla final (música, ducking, barra roja)
    dur_total = obtener_duracion_media(ffmpeg, video_unido)
    musica = generar_musica(max(10, int(dur_total) + 5))
    whooshes = [whoosh] * int(dur_total // 2)
    destino = OUTPUT / "fortaleza_final.mp4"
    mezcla_final(ffmpeg, str(video_unido), musica, whooshes, str(destino), dur_total)
    shutil.copy2(destino, OUTPUT / "fortaleza_short.mp4")
    
    metricas["promedio_toma"] = metricas["duracion_total_tomas"] / max(1, metricas["total_tomas"])
    evaluar_y_mutar(CONFIG, metricas)
    print("\n✅ PRODUCCIÓN COMPLETADA CON AGNES VIDEO")
    return str(destino)

if __name__ == "__main__":
    asyncio.run(crear_video())