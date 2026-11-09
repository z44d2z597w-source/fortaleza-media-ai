import json, random, re, requests, urllib.parse
from datetime import datetime, timezone
from pathlib import Path

ARCHIVO_GUION = Path("guion.json")
GENEROS = ["Terror psicológico", "Misterio histórico", "Ciencia ficción distópica", "Drama familiar", "Leyenda urbana", "Conspiración tecnológica"]
ESTILOS = ["Cinematic 8k, dramatic lighting", "Dark fantasy oil painting", "Vintage 35mm film", "Cyberpunk neon", "Anime style"]
VOCES = ["es-MX-DaliaNeural", "es-MX-JorgeNeural"]

def generar_con_pollinations(prompt):
    print("[IA TEXTO] Generando historia con Pollinations (Gratis)...")
    url = f"https://text.pollinations.ai/{urllib.parse.quote(prompt)}?model=openai"
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        return resp.text.strip()
    except Exception as e:
        print(f"[POLLINATIONS] Error: {e}")
        return None

def crear_guion():
    genero, estilo, voz = random.choice(GENEROS), random.choice(ESTILOS), random.choice(VOCES)
    print(f"[ORIGINALIDAD] Género: {genero} | Estilo: {estilo} | Voz: {voz}")
    
    prompt = f"Escribe un guion para un Short del género '{genero}' en español mexicano. Estructura: 1. Gancho (5-8 palabras). 2. Contexto. 3. Desarrollo. 4. Clímax (giro). 5. Cierre (loop). Tono dramático. Sin títulos de escena, solo texto. Sin comillas."
    
    texto_ia = generar_con_pollinations(prompt)
    
    escenas = []
    if texto_ia:
        oraciones = [o.strip() for o in re.split(r"(?<=[.!?])\s+", texto_ia) if len(o.strip()) > 10]
        if len(oraciones) >= 5:
            quinto = len(oraciones) // 5
            escenas = [
                {"numero": 1, "duracion": 10, "tipo": "gancho", "titulo": "Inicio", "narracion": " ".join(oraciones[:quinto])},
                {"numero": 2, "duracion": 12, "tipo": "contexto", "titulo": "Contexto", "narracion": " ".join(oraciones[quinto:quinto*2])},
                {"numero": 3, "duracion": 15, "tipo": "desarrollo", "titulo": "Desarrollo", "narracion": " ".join(oraciones[quinto*2:quinto*3])},
                {"numero": 4, "duracion": 15, "tipo": "climax", "titulo": "Clímax", "narracion": " ".join(oraciones[quinto*3:quinto*4])},
                {"numero": 5, "duracion": 10, "tipo": "cierre", "titulo": "Loop", "narracion": " ".join(oraciones[quinto*4:])}
            ]
    
    if not escenas:
        print("[AVISO] Pollinations falló. Usando respaldo.")
        escenas = [
            {"numero": 1, "duracion": 8, "tipo": "gancho", "titulo": "El inicio", "narracion": "Hay un secreto en tu celular que ni tú conoces."},
            {"numero": 2, "duracion": 12, "tipo": "contexto", "titulo": "El contexto", "narracion": "Todas las noches, una aplicación invisible se enciende."},
            {"numero": 3, "duracion": 15, "tipo": "desarrollo", "titulo": "El conflicto", "narracion": "Está grabando tus conversaciones y enviándolas a un servidor."},
            {"numero": 4, "duracion": 15, "tipo": "climax", "titulo": "La revelación", "narracion": "Cuando revisas, no hay ninguna app instalada."},
            {"numero": 5, "duracion": 10, "tipo": "cierre", "titulo": "El loop", "narracion": "Pero si hay un secreto en tu celular que ni tú conoces..."}
        ]

    return {"titulo": f"El misterio de {genero.lower()}", "formato": "vertical", "duracion": 60, "estilo_visual": estilo, "voz": voz, "escenas": escenas}

def guardar_guion():
    guion = crear_guion()
    with open(ARCHIVO_GUION, "w", encoding="utf-8") as f: json.dump(guion, f, ensure_ascii=False, indent=4)
    print(f"GUION GUARDADO: {guion['titulo']}")

if __name__ == "__main__":
    guardar_guion()