import asyncio, json, math, os, random, re, shutil, subprocess, time, urllib.parse, wave
from array import array
from io import BytesIO
from pathlib import Path
import requests, edge_tts, imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageOps

FPS = 30
OUTPUT = Path("output")
RECURSOS = OUTPUT / "recursos_short"
FORMATO = {"ancho": 1080, "alto": 1920}

def preparar_entorno():
    OUTPUT.mkdir(exist_ok=True); RECURSOS.mkdir(exist_ok=True)
    for f in RECURSOS.iterdir():
        if f.is_file(): f.unlink()

def obtener_fuente(tamano, negrita=False):
    rutas = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if negrita else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if negrita else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
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
            query = random.choice(["subway surfers", "minecraft parkour", "oddly satisfying", "satisfying video", "gameplay", "cooking video"])
            # NOTA: Pixabay no soporta "orientation" para videos. Buscamos sin ese filtro.
            resp = requests.get("https://pixabay.com/api/videos/", params={"key": pixabay_key, "q": query, "per_page": 10}, timeout=15).json()
            for hit in resp.get("hits", []):
                # Filtramos manualmente para asegurar que sea vertical
                ancho = hit.get("videos", {}).get("large", {}).get("width", 0)
                alto = hit.get("videos", {}).get("large", {}).get("height", 0)
                if alto > ancho: # Es vertical
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

def generar_ass_cinetico(marcas, dur_voz, ruta_ass):
    grupos, grupo_actual = [], []
    for p in marcas:
        grupo_actual.append(p)
        if len(grupo_actual) >= 2 or len(p["texto"]) > 8:
            grupos.append(grupo_actual); grupo_actual = []
    if grupo_actual: grupos.append(grupo_actual)

    header = """[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Kinetic, DejaVu Sans, 120, &H0000FFFF, &H00000000, &H00000000, -1, 0, 0, 0, 100, 100, 0, 0, 1, 8, 0, 5, 10, 10, 0, 1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""
    lineas = []
    for g in grupos:
        inicio, fin = max(0, g[0]["inicio"]), min(dur_voz, g[-1]["fin"] + 0.1)
        if fin <= inicio: continue
        texto = " ".join(x["texto"] for x in g).upper()
        animacion = r"{\move(540,1200,540,960,0,250)\t(0,150,\fscx115\fscy115)\t(150,250,\fscx100\fscy100)}"
        lineas.append(f"Dialogue: 0,{inicio:.2f},{fin:.2f},Kinetic,,0,0,0,,{animacion}{texto}")

    with open(ruta_ass, "w", encoding="utf-8") as f: f.write(header + "\n".join(lineas))
    return ruta_ass

async def renderizar_short():
    preparar_entorno()
    with open("guion.json", encoding="utf-8") as f: guion = json.load(f)
    
    voz = guion.get("voz", "es-MX-DaliaNeural")
    narracion = guion["narracion"]
    prompt = guion["prompt_visual"]
    
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    video_fondo = obtener_video_fondo()

    print(f"--- GENERANDO SHORT: {guion['titulo_serie']} - Parte {guion['parte']} ---")
    
    ruta_voz = RECURSOS / "voz.mp3"
    marcas = await generar_voz(narracion, ruta_voz, voz)
    dur_voz = obtener_duracion(ffmpeg, ruta_voz)
    
    ruta_ass = generar_ass_cinetico(marcas, dur_voz, RECURSOS / "subs.ass")
    img_ia = generar_imagen_ia(prompt, random.randint(1, 9999))

    cmd = [ffmpeg, "-y"]
    if video_fondo: cmd.extend(["-stream_loop", "-1", "-i", video_fondo])
    else: cmd.extend(["-f", "lavfi", "-i", f"color=c=#071426:s={FORMATO['ancho']}x{FORMATO['alto']}:r={FPS}"])
        
    cmd.extend(["-i", str(ruta_voz)])
    if img_ia: cmd.extend(["-loop", "1", "-framerate", str(FPS), "-i", img_ia])

    filtros = []
    filtros.append(f"[0:v]scale={FORMATO['ancho']}:{FORMATO['alto']}:force_original_aspect_ratio=increase,crop={FORMATO['ancho']}:{FORMATO['alto']},eq=brightness=-0.15:saturation=1.3[bg]")
    actual = "[bg]"
    if img_ia:
        # Zoom suave: supersampling a 4x para evitar jitter
        filtros.append(f"[2:v]scale=4320:7680,zoompan=z='min(zoom+0.0005,1.1)':d=1:s=1080x1920:fps={FPS}[img]")
        filtros.append(f"{actual}[img]overlay=0:0:enable='between(t,0,{dur_voz})'[v_img]")
        actual = "[v_img]"
    
    filtros.append(f"{actual}ass={ruta_ass}[v_subs]")
    filtros.append(f"[v_subs]drawbox=x=0:y=h-10:w='iw*t/{dur_voz}':h=10:color=red@0.9:t=fill[v_final]")

    destino = OUTPUT / "fortaleza_short.mp4"
    cmd.extend(["-filter_complex", ";".join(filtros), "-map", "[v_final]", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-b:a", "192k", "-t", f"{dur_voz:.3f}", str(destino)])
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"✅ Short Parte {guion['parte']} generado.")
    return str(destino)

if __name__ == "__main__":
    asyncio.run(renderizar_short())