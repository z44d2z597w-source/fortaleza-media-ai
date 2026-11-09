import json
import random
import re
import requests
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
import os

ARCHIVO_GUION = Path("guion.json")
ARCHIVO_HISTORIAL = Path("historial_temas.json")

def cargar_historial():
    if not ARCHIVO_HISTORIAL.exists(): return []
    try:
        with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def guardar_historial(historial):
    with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=4)

def generar_con_groq(prompt):
    """Conecta con Groq para generar texto de alta calidad."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("[GROQ] No hay GROQ_API_KEY configurada. Saltando...")
        return None

    headers = {"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": "Eres un guionista experto en videos virales de YouTube Shorts. Escribes en español mexicano, con un tono dramático, directo y adictivo. Sigues las instrucciones al pie de la letra."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 800
    }
    
    try:
        respuesta = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
        respuesta.raise_for_status()
        print("[GROQ] Guion generado con éxito.")
        return respuesta.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[GROQ] Error: {e}")
        return None

def generar_con_pollinations(prompt):
    """Respaldo usando Pollinations (texto)."""
    prompt_encoded = urllib.parse.quote(prompt)
    url = f"https://text.pollinations.ai/{prompt_encoded}?model=openai"
    try:
        respuesta = requests.get(url, timeout=120)
        respuesta.raise_for_status()
        print("[POLLINATIONS] Guion generado con éxito.")
        return respuesta.text.strip()
    except Exception as e:
        print(f"[POLLINATIONS] Error: {e}")
        return None

def estructurar_guion(texto_ia, titulo):
    """Divide el texto de la IA en 5 escenas perfectas."""
    texto_ia = re.sub(r"^(Escena \d+:?|Aquí tienes.*?:)", "", texto_ia, flags=re.IGNORECASE|re.MULTILINE).strip()
    oraciones = [o.strip() for o in re.split(r"(?<=[.!?])\s+", texto_ia) if len(o.strip()) > 10]
    
    if len(oraciones) < 5:
        return None

    quinto = max(1, len(oraciones) // 5)
    escenas = [
        {"numero": 1, "duracion": 8, "tipo": "gancho", "titulo": "El inicio", "narracion": " ".join(oraciones[:quinto])},
        {"numero": 2, "duracion": 12, "tipo": "contexto", "titulo": "El contexto", "narracion": " ".join(oraciones[quinto:quinto*2])},
        {"numero": 3, "duracion": 15, "tipo": "desarrollo", "titulo": "El conflicto", "narracion": " ".join(oraciones[quinto*2:quinto*3])},
        {"numero": 4, "duracion": 15, "tipo": "climax", "titulo": "La revelación", "narracion": " ".join(oraciones[quinto*3:quinto*4])},
        {"numero": 5, "duracion": 10, "tipo": "cierre", "titulo": "El loop", "narracion": " ".join(oraciones[quinto*4:])}
    ]
    
    for i in range(1, 5):
        if not escenas[i]["narracion"]:
            escenas[i]["narracion"] = escenas[i-1]["narracion"]

    return {
        "titulo": titulo,
        "formato": "vertical",
        "formato_legible": "YouTube Shorts (Estructurado)",
        "duracion": 60,
        "escenas": escenas
    }

def crear_guion():
    prompt_base = (
        "Escribe un guion para un video vertical de YouTube Shorts sobre {tema}. "
        "La historia debe tener exactamente esta estructura de 5 escenas, separadas por saltos de línea: "
        "1. Gancho (una frase de 5-8 palabras que impacte). "
        "2. Contexto (la situación inicial). "
        "3. Desarrollo (el conflicto o problema). "
        "4. Clímax (la revelación o el giro inesperado). "
        "5. Cierre (una frase que conecte con el inicio para crear un loop). "
        "Usa un tono dramático y directo. No incluyas títulos de escena, solo el texto narrado. No uses comillas."
    )

    temas_drama = [
        "una traición familiar", "un secreto de pareja", "un misterio en el trabajo",
        "una desaparición inexplicable", "una herencia maldita", "un mensaje de texto escalofriante"
    ]
    random.shuffle(temas_drama)

    for tema in temas_drama:
        print(f"[EDITORIAL] Generando historia sobre: {tema}")
        prompt = prompt_base.format(tema=tema)
        
        # Intentar Groq, luego Pollinations
        texto_ia = generar_con_groq(prompt)
        if not texto_ia:
            texto_ia = generar_con_pollinations(prompt)
        
        if texto_ia:
            guion = estructurar_guion(texto_ia, f"El misterio de {tema}")
            if guion: return guion

    print("[EDITORIAL] APIs fallaron. Usando respaldo.")
    return {
        "titulo": "El secreto de la habitación 404",
        "formato": "vertical",
        "formato_legible": "YouTube Shorts (Respaldo)",
        "duracion": 60,
        "escenas": [
            {"numero": 1, "duracion": 8, "tipo": "gancho", "titulo": "El inicio", "narracion": "Imagina entrar a un hotel y que la habitación 404 no exista en los planos. Eso le pasó a un huésped."},
            {"numero": 2, "duracion": 12, "tipo": "contexto", "titulo": "El contexto", "narracion": "El recepcionista le dio la llave sin mirarlo a los ojos. Le dijo que no hiciera ruido después de medianoche."},
            {"numero": 3, "duracion": 15, "tipo": "desarrollo", "titulo": "El conflicto", "narracion": "Al abrir la puerta, la habitación no tenía muebles. Solo había un espejo gigante que reflejaba un cuarto diferente al suyo."},
            {"numero": 4, "duracion": 15, "tipo": "climax", "titulo": "La revelación", "narracion": "Cuando tocó el espejo, su mano atravesó el vidrio. Del otro lado, alguien exactamente igual a él lo estaba esperando con una sonrisa."},
            {"numero": 5, "duracion": 10, "tipo": "cierre", "titulo": "El loop", "narracion": "Y por eso te pregunto: ¿qué harías si entraras a una habitación 404?"}
        ]
    }

def guardar_guion():
    guion = crear_guion()
    guion["idioma"] = "es-MX"
    guion["creado"] = datetime.now(timezone.utc).isoformat()
    guion["hashtags"] = ["#Shorts", "#Viral", "#Misterio", "#FORTALEZAMEDIA"]
    guion["descripcion"] = f"{guion['titulo']}\n\n" + " ".join(guion["hashtags"])

    with open(ARCHIVO_GUION, "w", encoding="utf-8") as f:
        json.dump(guion, f, ensure_ascii=False, indent=4)

    historial = cargar_historial()
    historial.append({"titulo": guion["titulo"], "creado": guion["creado"]})
    guardar_historial(historial)

    print("=" * 55)
    print("GUION GENERADO CON ÉXITO")
    print("Título:", guion["titulo"])
    print("Escenas:", len(guion["escenas"]))
    print("=" * 55)
    return guion

if __name__ == "__main__":
    guardar_guion()