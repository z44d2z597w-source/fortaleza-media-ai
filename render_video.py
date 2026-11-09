import asyncio, json, math, os, random, re, shutil, subprocess, time, urllib.parse, wave
from array import array
from io import BytesIO
from pathlib import Path
import requests, edge_tts, imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageOps

# ==========================================================
# FORTALEZA MEDIA AI 31.0 — COHERENCIA SEMÁNTICA TOTAL
# ==========================================================

FPS = 30
OUTPUT = Path("output")
RECURSOS = OUTPUT / "recursos"
FORMATO = {"ancho": 1080, "alto": 1920}

def preparar_entorno():
    OUTPUT.mkdir(exist_ok=True); RECURSOS.mkdir(exist_ok=True)
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

def calcular_cortes(palabras, duracion_total):
    if duracion_total <= 0: return [0.0, duracion_total]
    puntos = [(palabras[i-1]["fin"] + palabras[i]["inicio"])/2 for i in range(1, len(palabras)) if palabras[i]["inicio"] - palabras[i-1]["fin"] >= 0.25]
    puntos += [p["fin"] + 0.05 for p in palabras if p["texto"].strip().endswith((".", "?", "!"))]
    puntos = sorted(set(round(c, 3) for c in puntos))
    cortes = [0.0]
    for c in puntos:
        if (c < 5.0 and c - cortes[-1] >= 1.2) or (c >= 5.0 and c - cortes[-1] >= 1.5 and duracion_total - c >= 1.5): cortes.append(c)
    resultado = [0.0]
    for c in cortes[1:]:
        while c - resultado[-1] > 3.5: resultado.append(resultado[-1] + 3.5)
        resultado.append(c)
    while duracion_total - resultado[-1] > 3.5: resultado.append(resultado[-1] + 3.5)
    if resultado[-1] < duracion_total: resultado.append(duracion_total)
    else: resultado[-1] = duracion_total
    return resultado

# --- EXTRACCIÓN DE PALABRAS CLAVE (Para que el video concuerde) ---
def extraer_palabras_clave(texto):
    # Quitamos palabras vacías o conectores para que Pixabay busque solo lo importante
    palabras_vacias = {"para", "porque", "sobre", "desde", "hasta", "donde", "cuando", "también", "tienen", "puede", "entre", "pero", "algo", "todo", "cada", "hacia", "después", "durante", "del", "las", "los", "una", "uno", "con", "sin", "por", "que", "sus", "hay", "más", "muy", "hoy"}
    palabras = re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ]{4,}", texto.lower())
    filtradas = [p for p in palabras if p not in palabras_vacias]
    # Nos quedamos con las 3 palabras más largas (suelen ser las más descriptivas)
    filtradas.sort(key=len, reverse=True)
    return " ".join(list(dict.fromkeys(filtradas))[:3])

# --- GENERADORES VISUALES ---
def buscar_video_stock(narracion, escena, toma):
    key = os.environ.get("PIXABAY_API_KEY")
    if key:
        try:
            query = extraer_palabras_clave(narracion)
            print(f"    -> [STOCK] Buscando video de: '{query}'")
            resp = requests.get("https://pixabay.com/api/videos/", params={"key": key, "q": query, "orientation": "vertical", "per_page": 5}, timeout=15).json()
            
            for hit in resp.get("hits", []):
                url = hit.get("videos", {}).get("medium", {}).get("url")
                if url:
                    ruta = RECURSOS / f"pixabay_{escena}_{toma}.mp4"
                    with requests.get(url, stream=True, timeout=20) as r:
                        with open(ruta, "wb") as f:
                            for chunk in r.iter_content(8192): f.write(chunk)
                    if os.path.getsize(ruta) > 15000:
                        print(f"    -> [PIXABAY] Video real conseguido.")
                        return str(ruta), True
        except Exception: pass
    return None

def generar_imagen_ia(narracion, escena, toma):
    try:
        # Añadimos una semilla aleatoria para que NUNCA se repita la misma imagen en bucle
        seed = random.randint(1, 999999)
        prompt = f"Cinematic 8k, dramatic lighting, {narracion[:100]}"
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width={FORMATO['ancho']}&height={FORMATO['alto']}&nologo=true&seed={seed}"
        
        resp = requests.get(url, timeout=45)
        img = Image.open(BytesIO(resp.content)); img.verify()
        ruta = RECURSOS / f"poll_{escena}_{toma}.jpg"
        with open(ruta, "wb") as f: f.write(resp.content)
        print(f"    -> [POLLINATIONS] Imagen IA generada (Seed: {seed}).")
        return str(ruta), False
    except Exception: return None

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

# --- RENDERIZADO ---
def crear_toma(ffmpeg, ruta, destino, duracion, idx, es_video):
    if es_video:
        filtros = [f"scale={FORMATO['ancho']}:{FORMATO['alto']}:force_original_aspect_ratio=increase", f"crop={FORMATO['ancho']}:{FORMATO['alto']}", "setsar=1", "format=yuv420p"]
        cmd = [ffmpeg, "-y", "-stream_loop", "-1", "-i", ruta, "-vf", ",".join(filtros), "-t", f"{duracion:.3f}", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-r", str(FPS), str(destino)]
    else:
        # Zoom agresivo para que las imágenes parezcan video
        movs = [
            ("min(zoom+0.0030,1.5)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
            ("min(zoom+0.0040,1.6)", "iw/2-(iw/zoom/2)+on*0.5", "ih/2-(ih/zoom/2)"),
            ("max(zoom-0.0020,1.0)", "iw/2-(iw/zoom/2)-on*0.4", "ih/2-(ih/zoom/2)")
        ]
        zoom, x, y = movs[idx % len(movs)]
        filtros = [
            f"scale={int(FORMATO['ancho']*1.3)}:{int(FORMATO['alto']*1.3)}:force_original_aspect_ratio=increase", 
            f"crop={int(FORMATO['ancho']*1.3)}:{int(FORMATO['alto']*1.3)}", 
            f"zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s={FORMATO['ancho']}x{FORMATO['alto']}:fps={FPS}", 
            "eq=contrast=1.15:saturation=1.3", "setsar=1", "format=yuv420p"
        ]
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
    escenas = guion.get("escenas", [])
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    clips_finales = []
    
    scroll_img = crear_scroll_stopper()

    print(f"--- PRODUCIENDO: {guion['titulo']} | VOZ: {voz} ---")
    
    for i, escena in enumerate(escenas):
        print(f"\n[ESCENA {i+1}/{len(escenas)}]")
        narracion = escena["narracion"]
        ruta_voz = RECURSOS / f"voz_{i}.mp3"
        marcas = await generar_voz(narracion, ruta_voz, voz)
        dur = obtener_duracion(ffmpeg, ruta_voz)
        cortes = calcular_cortes(marcas, dur)
        
        tomas = []
        for j in range(len(cortes)-1):
            d_toma = cortes[j+1] - cortes[j]
            if d_toma <= 0.4: continue
            
            # 1. Intentar buscar un video real que concuerde con la narración
            res = buscar_video_stock(narracion, i, j)
            
            # 2. Si no hay video, generar una imagen IA única basada en la narración
            if not res: 
                res = generar_imagen_ia(narracion, i, j)
            
            if res:
                recurso, es_video = res
                ruta_toma = RECURSOS / f"toma_{i}_{j}.mp4"
                crear_toma(ffmpeg, recurso, ruta_toma, d_toma, i*10+j, es_video)
                tomas.append(str(ruta_toma))

        ruta_vis = RECURSOS / f"vis_{i}.mp4"
        with open(RECURSOS / f"list_{i}.txt", "w") as f:
            for t in tomas: f.write(f"file '{Path(t).resolve()}'\n")
        subprocess.run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(RECURSOS / f"list_{i}.txt"), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p", "-r", str(FPS), "-an", str(ruta_vis)], check=True, capture_output=True)
        
        subtitulos = crear_subtitulos(marcas, i, dur)
        cmd_comp = [ffmpeg, "-y", "-i", str(ruta_vis), "-i", str(ruta_voz)]
        
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
        cmd_comp.extend(["-filter_complex", ";".join(filtros), "-map", actual, "-map", "1:a", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.3f}", str(ruta_final_escena)])
        subprocess.run(cmd_comp, check=True, capture_output=True)
        clips_finales.append(str(ruta_final_escena))

    print("\n[RENDER] Uniendo todas las escenas...")
    video_unido = OUTPUT / "base.mp4"
    with open(OUTPUT / "all.txt", "w") as f:
        for c in clips_finales: f.write(f"file '{Path(c).resolve()}'\n")
    subprocess.run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(OUTPUT / "all.txt"), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(video_unido)], check=True, capture_output=True)
    
    dur_total = obtener_duracion(ffmpeg, video_unido)
    destino = OUTPUT / "fortaleza_final.mp4"
    filtro_barra = f"[0:v]drawbox=x=0:y=h-10:w='iw*t/{dur_total}':h=10:color=red@0.9:t=fill[vout]"
    subprocess.run([ffmpeg, "-y", "-i", str(video_unido), "-filter_complex", filtro_barra, "-map", "[vout]", "-map", "0:a", "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-c:a", "copy", str(destino)], check=True, capture_output=True)
    
    shutil.copy2(destino, OUTPUT / "fortaleza_short.mp4")
    print("\n✅ PRODUCCIÓN COMPLETADA CON COHERENCIA")
    return str(destino)

if __name__ == "__main__":
    asyncio.run(crear_video())