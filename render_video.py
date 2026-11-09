# (Añade esta función al principio del archivo, después de las importaciones)
def generar_video_ia(prompt, num_escena, formato, duracion_sugerida=5):
    """Genera un video corto usando Agnes Video (gratis, ilimitado)."""
    # Agnes Video usa un endpoint público sin API key
    url = "https://api.agnes.ai/v1/video/generate"  # Endpoint de ejemplo
    payload = {
        "prompt": prompt,
        "duration": 5,  # 5 o 10 segundos
        "aspect_ratio": "9:16" if formato["nombre"] == "vertical" else "16:9"
    }
    print(f"[IA] Generando video con Agnes: {prompt[:60]}...")
    try:
        resp = requests.post(url, json=payload, timeout=180)
        resp.raise_for_status()
        data = resp.json()
        # Agnes devuelve una URL de video
        video_url = data.get("video_url") or data.get("url")
        if not video_url:
            print("[IA] Agnes no devolvió URL.")
            return None
        ruta = RECURSOS / f"ia_{num_escena:02d}.mp4"
        with requests.get(video_url, stream=True, timeout=180) as r:
            r.raise_for_status()
            with open(ruta, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"[IA] Video IA guardado en {ruta}")
        return str(ruta)
    except Exception as e:
        print(f"[IA] Error con Agnes: {e}")
        return None