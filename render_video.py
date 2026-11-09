import asyncio
import html
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
from PIL import (
    Image, ImageDraw, ImageFont, ImageEnhance,
    ImageFilter, ImageOps,
)

# ==========================================================
# FORTALEZA MEDIA AI 18.0 — TITÁN DEFINITIVO
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

CABECERAS = {"User-Agent": "FortalezaMediaAI/18.0 python-requests"}
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

# --- BÚSQUEDA DE MATERIAL ---

def generar_palabras_clave(titulo, narracion):
    palabras = re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ]{4,}", titulo + " " + narracion)
    filtradas = [p for p in palabras if p.lower() not in ["para", "porque", "sobre", "desde", "hasta", "donde", "cuando"]]
    return " ".join(list(dict.fromkeys(filtradas))[:3]) if filtradas else "cinematic"

def buscar_videos_stock(titulo, narracion, num_escena, formato):
    clave = os.environ.get("PIXABAY_API_KEY")
    if not clave: return []
    consulta = generar_palabras_clave(titulo, narracion)
    url = "https://pixabay.com/api/videos/"
    params = {"key": clave, "q": consulta, "orientation": formato["orientacion"], "per_page": 10}
    try:
        hits = requests.get(url, params=params, timeout=20).json().get("hits", [])
    except Exception: return []

    descargas = []
    for hit in hits:
        mejor = hit.get("videos", {}).get("large") or hit.get("videos", {}).get("medium")
        if not mejor: continue
        ruta = RECURSOS / f"vid_{num_escena:02d}_{len(descargas):02d}.mp4"
        try:
            with requests.get(mejor["url"], stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(ruta, "wb") as f:
                    for chunk in r.iter_content(8192): f.write(chunk)
            if os.path.getsize(ruta) > 15000:
                descargas.append({"archivo": str(ruta), "es_video": True})
                if len(descargas) >= 3: break
        except Exception: pass
    return descargas

def generar_imagen_ia(prompt, num_escena, num_toma, formato):
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width={formato['ancho']}&height={formato['alto']}&nologo=true&model=flux"
    try:
        respuesta = requests.get(url, timeout=60)
        ruta = RECURSOS / f"ia_{num_escena:02d}_{num_toma:02d}.jpg"
        with open(ruta, "wb") as f: f.write(respuesta.content)
        Image.open(ruta).verify()
        return {"archivo": str(ruta), "es_video": False}
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

def crear_toma(ffmpeg, recurso, destino, duracion, indice, formato, es_impacto):
    ancho, alto = formato["ancho"], formato["alto"]
    filtros = [f"scale={int(ancho*1.2)}:{int(alto*1.2)}:force_original_aspect_ratio=increase,crop={int(ancho*1.2)}:{int(alto*1.2)}"]
    
    movimientos = [
        ("min(zoom+0.0015,1.3)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
        ("min(zoom+0.0020,1.4)", "iw/2-(iw/zoom/2)+on*0.15", "ih/2-(ih/zoom/2)"),
        ("max(zoom-0.0010,1.0)", "iw/2-(iw/zoom/2)-on*0.10", "ih/2-(ih/zoom/2)"),
    ]
    zoom, x, y = movimientos[indice % len(movimientos)]

    if es_impacto and not recurso["es_video"]:
        filtros.append(f"zoompan=z='if(lt(on,15),1.6-on/25,1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={ancho}x{alto}:fps={FPS}")
    elif not recurso["es_video"]:
        filtros.append(f"zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s={ancho}x{alto}:fps={FPS}")
    else:
        filtros.append(f"scale={ancho}:{alto}:force_original_aspect_ratio=increase,crop={ancho}:{alto}")

    filtros.append("eq=contrast=1.18:saturation=1.30:gamma=0.95,unsharp=5:5:0.8:5:5:0.0")
    if es_impacto: filtros.append("rgbashift=rh=10:bh=-10:enable='lt(t,0.25)'")
    filtros.append("setsar=1,format=yuv420p")

    cmd = [ffmpeg, "-y"]
    if recurso["es_video"]: cmd.extend(["-stream_loop", "-1", "-i", recurso["archivo"]])
    else: cmd.extend(["-loop", "1", "-framerate", str(FPS), "-i", recurso["archivo"]])
    cmd.extend(["-vf", ",".join(filtros), "-t", f"{duracion:.3f}", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p", "-r", str(FPS), str(destino)])
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

    metricas = {"total_tomas": 0, "duracion_total_tomas": 0, "tomadas_video": 0}
    escenas_finales, duraciones_finales = [], []
    whoosh = generar_whoosh(RECURSOS / "whoosh.wav")
    scroll = crear_scroll_stopper(formato)

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

        # 3. Material (Videos Stock o Imágenes IA)
        videos = buscar_videos_stock(titulo, narracion, num_escena, formato)
        recursos = videos
        metricas["tomadas_video"] += len(videos)
        
        for i in range(len(videos), num_tomas):
            prompt = f"Cinematic vertical 9:16, dramatic lighting, {narracion[:100]}"
            img = generar_imagen_ia(prompt, num_escena, i, formato)
            if img: recursos.append(img)

        if not recursos:
            ruta = RECURSOS / f"fondo_{num_escena}.jpg"
            Image.new("RGB", (formato["ancho"], formato["alto"]), "#101010").save(ruta)
            recursos = [{"archivo": str(ruta), "es_video": False}]

        recursos_asig = ajustar_recursos(recursos, num_tomas)

        # 4. Renderizar Tomas
        tomas_mp4 = []
        for i in range(num_tomas):
            dur = cortes[i + 1] - cortes[i]
            if dur <= 0.4: continue
            ruta_toma = RECURSOS / f"toma_{num_escena:02d}_{i:02d}.mp4"
            crear_toma(ffmpeg, recursos_asig[i], ruta_toma, dur, num_escena*10+i, formato, (i == 0))
            tomas_mp4.append(str(ruta_toma))
            metricas["total_tomas"] += 1
            metricas["duracion_total_tomas"] += dur

        # 5. Concatenar
        ruta_visual = RECURSOS / f"vis_{num_escena:02d}.mp4"
        with open(RECURSOS / f"list_{num_escena:02d}.txt", "w") as f:
            for t in tomas_mp4: f.write(f"file '{Path(t).resolve()}'\n")
        ejecutar_comando_ffmpeg([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(RECURSOS / f"list_{num_escena:02d}.txt"), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p", "-r", str(FPS), "-an", str(ruta_visual)])

        # 6. Subtítulos Básicos
        cmd_comp = [ffmpeg, "-y", "-i", str(ruta_visual), "-i", str(ruta_voz)]
        
        # Scroll stopper en la primera escena
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

    # 7. Unir Escenas
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

    # 8. Mezcla Final
    dur_total = obtener_duracion_media(ffmpeg, video_unido)
    musica = generar_musica(max(10, int(dur_total) + 5))
    whooshes = [whoosh] * int(dur_total // 2)
    destino = OUTPUT / "fortaleza_final.mp4"
    mezcla_final(ffmpeg, str(video_unido), musica, whooshes, str(destino), dur_total)
    shutil.copy2(destino, OUTPUT / "fortaleza_short.mp4")
    
    metricas["promedio_toma"] = metricas["duracion_total_tomas"] / max(1, metricas["total_tomas"])
    evaluar_y_mutar(CONFIG, metricas)
    print("\n✅ PRODUCCIÓN COMPLETADA")
    return str(destino)

if __name__ == "__main__":
    asyncio.run(crear_video())