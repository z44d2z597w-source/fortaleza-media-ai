import json, random, re, requests, urllib.parse
from pathlib import Path

ARCHIVO_GUION = Path("guion.json")
GENEROS = ["Terror psicológico", "Misterio histórico", "Ciencia ficción distópica", "Drama familiar", "Leyenda urbana", "Conspiración tecnológica"]
VOCES = ["es-MX-DaliaNeural", "es-MX-JorgeNeural"]

def generar_con_pollinations(prompt):
    print("[IA TEXTO] Generando historia larga con Pollinations...")
    url = f"https://text.pollinations.ai/{urllib.parse.quote(prompt)}?model=openai"
    try:
        resp = requests.get(url, timeout=90)
        resp.raise_for_status()
        return resp.text.strip()
    except Exception as e:
        print(f"[POLLINATIONS] Error: {e}")
        return None

def crear_guion():
    genero = random.choice(GENEROS)
    voz = random.choice(VOCES)
    print(f"[ORIGINALIDAD] Género: {genero} | Voz: {voz}")
    
    # EXIGIMOS UNA HISTORIA LARGA (Mínimo 150 palabras para durar más de 1 minuto)
    prompt = (
        f"Escribe una historia dramática de '{genero}' en español mexicano. "
        "La historia DEBE tener al menos 150 palabras de duración. "
        "Estructura: 1. Gancho. 2. Contexto. 3. Desarrollo. 4. Clímax. 5. Cierre. "
        "No incluyas títulos de escena ni comillas, solo escribe los 5 párrafos de la historia."
    )
    
    texto_ia = generar_con_pollinations(prompt)
    escenas = []
    
    if texto_ia:
        # Limpiamos y separamos en párrafos
        parrafos = [p.strip() for p in texto_ia.split('\n') if len(p.strip()) > 20]
        
        # Si la IA no separó por párrafos, dividimos por oraciones
        if len(parrafos) < 5:
            oraciones = [o.strip() for o in re.split(r"(?<=[.!?])\s+", texto_ia) if len(o.strip()) > 10]
            if len(oraciones) >= 5:
                tercio = len(oraciones) // 5
                parrafos = [" ".join(oraciones[i*tercio:(i+1)*tercio]) for i in range(5)]

        if len(parrafos) >= 5:
            escenas = [
                {"numero": 1, "duracion": 10, "tipo": "gancho", "titulo": "Inicio", "narracion": parrafos[0]},
                {"numero": 2, "duracion": 15, "tipo": "contexto", "titulo": "Contexto", "narracion": parrafos[1]},
                {"numero": 3, "duracion": 15, "tipo": "desarrollo", "titulo": "Desarrollo", "narracion": parrafos[2]},
                {"numero": 4, "duracion": 15, "tipo": "climax", "titulo": "Clímax", "narracion": parrafos[3]},
                {"numero": 5, "duracion": 10, "tipo": "cierre", "titulo": "Loop", "narracion": parrafos[4]}
            ]
    
    if not escenas:
        print("[AVISO] Pollinations falló o dio texto muy corto. Usando respaldo LARGO.")
        escenas = [
            {"numero": 1, "duracion": 10, "tipo": "gancho", "titulo": "El inicio", "narracion": "Hay un secreto en tu celular que ni tú conoces. Lo que descubrí anoche me dejó sin dormir."},
            {"numero": 2, "duracion": 15, "tipo": "contexto", "titulo": "El contexto", "narracion": "Todas las noches a las 3 de la mañana, una aplicación invisible se enciende en segundo plano y empieza a grabar."},
            {"numero": 3, "duracion": 15, "tipo": "desarrollo", "titulo": "El conflicto", "narracion": "Está grabando tus conversaciones y enviándolas a un servidor en otro país. Y cuando revisas, no hay ninguna app instalada."},
            {"numero": 4, "duracion": 15, "tipo": "climax", "titulo": "La revelación", "narracion": "El archivo no pertenece a ninguna empresa conocida. El código fuente estaba firmado con tu propio nombre."},
            {"numero": 5, "duracion": 10, "tipo": "cierre", "titulo": "El loop", "narracion": "Y por eso te digo: hay un secreto en tu celular que ni tú conoces."}
        ]

    return {"titulo": f"El misterio de {genero.lower()}", "formato": "vertical", "duracion": 60, "estilo_visual": "Cinematic 8k", "voz": voz, "escenas": escenas}

def guardar_guion():
    guion = crear_guion()
    with open(ARCHIVO_GUION, "w", encoding="utf-8") as f: json.dump(guion, f, ensure_ascii=False, indent=4)
    print(f"GUION GUARDADO: {guion['titulo']} | Palabras totales aprox: {sum(len(e['narracion'].split()) for e in guion['escenas'])}")

if __name__ == "__main__":
    guardar_guion()