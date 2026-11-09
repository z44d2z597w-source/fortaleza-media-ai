import json
import random
import re
import requests
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
import os

ARCHIVO_GUION = Path("guion.json")

def generar_con_groq(prompt):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("[GROQ] No hay clave configurada.")
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
        print("[GROQ] ¡Conexión exitosa! Guion generado.")
        return respuesta.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[GROQ] Error de conexión: {e}")
        return None

def estructurar_guion(texto_ia, titulo):
    # Limpiamos el texto por si la IA pone "Escena 1:" o comillas
    texto_ia = re.sub(r"^(Escena \d+:?|Aquí tienes.*?:)", "", texto_ia, flags=re.IGNORECASE|re.MULTILINE).strip()
    oraciones = [o.strip() for o in re.split(r"(?<=[.!?])\s+", texto_ia) if len(o.strip()) > 10]
    
    if len(oraciones) < 5: 
        return None

    # Dividimos en las 5 escenas exactas
    quinto = max(1, len(oraciones) // 5)
    escenas = [
        {"numero": 1, "duracion": 8, "tipo": "gancho", "titulo": "El inicio", "narracion": " ".join(oraciones[:quinto])},
        {"numero": 2, "duracion": 12, "tipo": "contexto", "titulo": "El contexto", "narracion": " ".join(oraciones[quinto:quinto*2])},
        {"numero": 3, "duracion": 15, "tipo": "desarrollo", "titulo": "El conflicto", "narracion": " ".join(oraciones[quinto*2:quinto*3])},
        {"numero": 4, "duracion": 15, "tipo": "climax", "titulo": "La revelación", "narracion": " ".join(oraciones[quinto*3:quinto*4])},
        {"numero": 5, "duracion": 10, "tipo": "cierre", "titulo": "El loop", "narracion": " ".join(oraciones[quinto*4:])}
    ]
    
    # Aseguramos que ninguna escena esté vacía
    for i in range(1, 5):
        if not escenas[i]["narracion"]: 
            escenas[i]["narracion"] = escenas[i-1]["narracion"]

    return {"titulo": titulo, "formato": "vertical", "duracion": 60, "escenas": escenas}

def crear_guion():
    prompt = (
        "Escribe un guion para un video vertical de YouTube Shorts sobre 'una desaparición inexplicable'. "
        "La historia debe tener exactamente esta estructura de 5 escenas, separadas por saltos de línea: "
        "1. Gancho (una frase de 5-8 palabras que impacte). "
        "2. Contexto (la situación inicial). "
        "3. Desarrollo (el conflicto o problema). "
        "4. Clímax (la revelación o el giro inesperado). "
        "5. Cierre (una frase que conecte con el inicio para crear un loop). "
        "Usa un tono dramático y directo. No incluyas títulos de escena, solo el texto narrado. No uses comillas."
    )

    print("[EDITORIAL] Solicitando historia a Groq...")
    texto_ia = generar_con_groq(prompt)
    
    if texto_ia:
        guion = estructurar_guion(texto_ia, "El misterio de la desaparición")
        if guion: return guion
    
    print("[EDITORIAL] Groq falló. Usando historia de respaldo.")
    return {
        "titulo": "El secreto de la habitación 404", "formato": "vertical", "duracion": 60,
        "escenas": [
            {"numero": 1, "duracion": 8, "tipo": "gancho", "titulo": "El inicio", "narracion": "Imagina entrar a un hotel y que la habitación 404 no exista. Eso le pasó a un huésped."},
            {"numero": 2, "duracion": 12, "tipo": "contexto", "titulo": "El contexto", "narracion": "El recepcionista le dio la llave sin mirarlo a los ojos. Le dijo que no hiciera ruido después de medianoche."},
            {"numero": 3, "duracion": 15, "tipo": "desarrollo", "titulo": "El conflicto", "narracion": "Al abrir la puerta, la habitación no tenía muebles. Solo había un espejo gigante que reflejaba un cuarto diferente."},
            {"numero": 4, "duracion": 15, "tipo": "climax", "titulo": "La revelación", "narracion": "Cuando tocó el espejo, su mano atravesó el vidrio. Del otro lado, alguien igual a él lo esperaba con una sonrisa."},
            {"numero": 5, "duracion": 10, "tipo": "cierre", "titulo": "El loop", "narracion": "Y por eso te pregunto: ¿qué harías si entraras a una habitación 404?"}
        ]
    }

def guardar_guion():
    guion = crear_guion()
    with open(ARCHIVO_GUION, "w", encoding="utf-8") as f:
        json.dump(guion, f, ensure_ascii=False, indent=4)
    print("=" * 50)
    print(f"TÍTULO: {guion['titulo']}")
    print(f"ESCENA 1: {guion['escenas'][0]['narracion']}")
    print("=" * 50)
    return guion
