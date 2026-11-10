import os
import json
import random
import hashlib
import requests
from datetime import datetime, timezone

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

HISTORIAL = "historial.json"
DURACION_OBJETIVO = 170

TEMAS = [
    "Misterios inexplicables",
    "Historias de terror psicológico",
    "Casos extraños",
    "Secretos de la historia",
    "Ciencia sorprendente",
    "Misterios del océano",
    "Historias de supervivencia",
    "Fenómenos inexplicables",
    "Leyendas urbanas",
    "Experimentos científicos",
]


def cargar_historial():
    if not os.path.exists(HISTORIAL):
        return {"episodios": [], "temas": []}

    try:
        with open(HISTORIAL, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)

        if not isinstance(datos, dict):
            raise ValueError("Historial inválido")

        datos.setdefault("episodios", [])
        datos.setdefault("temas", [])
        return datos

    except Exception:
        return {"episodios": [], "temas": []}


def guardar_historial(datos):
    temporal = HISTORIAL + ".tmp"

    with open(temporal, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=2)

    os.replace(temporal, HISTORIAL)


def elegir_tema(historial):
    usados = historial.get("temas", [])
    disponibles = [tema for tema in TEMAS if tema not in usados]

    if not disponibles:
        historial["temas"] = []
        disponibles = TEMAS.copy()

    return random.choice(disponibles)


def crear_prompt(tema, episodio):
    return f"""
Crea un guion original en español mexicano para un YouTube Short.

SERIE: {tema}
EPISODIO: {episodio} de 5

REQUISITOS:
- Narración natural, emocionante y fácil de entender.
- Entre 300 y 360 palabras.
- Comienza con una frase que atrape desde el primer segundo.
- Mantén suspenso y curiosidad.
- No repitas ideas ni frases.
- Incluye detalles visuales para crear escenas.
- Termina con un giro, revelación o suspenso.
- Si es una historia ficticia, no la presentes como un caso real.
- El episodio debe conectar con el siguiente.
- No incluyas instrucciones para el editor.

Responde exclusivamente con JSON válido usando esta estructura:

{{
  "titulo_serie": "Nombre de la serie",
  "titulo": "Título atractivo del episodio",
  "parte": {episodio},
  "narracion": "Texto completo de la narración",
  "escenas": [
    {{
      "texto": "Parte de la narración",
      "visual": "Descripción detallada de lo que debe aparecer en pantalla"
    }}
  ]
}}

Incluye entre 6 y 8 escenas.
"""


def consultar_groq(prompt):
    if not GROQ_API_KEY:
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"

    encabezados = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    datos = {
        "model": "openai/gpt-oss-120b",
        "messages": [
            {
                "role": "system",
                "content": "Eres un guionista profesional especializado en historias virales originales."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.9,
        "max_tokens": 3500,
        "response_format": {"type": "json_object"},
    }

    try:
        respuesta = requests.post(
            url,
            headers=encabezados,
            json=datos,
            timeout=60,
        )

        respuesta.raise_for_status()
        contenido = respuesta.json()["choices"][0]["message"]["content"]
        return json.loads(contenido)

    except Exception as error:
        print(f"[AVISO] Groq no disponible: {error}")
        return None


def crear_guion_respaldo(tema, episodio):
    titulo = f"El misterio que nadie ha podido explicar - Parte {episodio}"

    narracion = (
        f"Hay historias que parecen imposibles, pero esta es una de esas que "
        f"te hacen cuestionar todo. Hoy conocerás una historia sobre {tema.lower()}. "
        f"Todo comenzó con un descubrimiento inesperado. Al principio, nadie le dio "
        f'importancia, pero pronto aparecieron detalles que no tenían explicación. '
        f"Los investigadores comenzaron a reunir información y encontraron "
        f"contradicciones que cambiaron por completo lo que creían saber. "
        f"Cada nueva pista abría otra pregunta. Y cuando parecía que finalmente "
        f"habían encontrado una respuesta, apareció un detalle que nadie había "
        f"notado. Lo más extraño es que ese detalle conectaba con algo ocurrido "
        f"mucho tiempo atrás. Algunas personas creen que todo tiene una explicación "
        f"lógica. Otras piensan que todavía falta descubrir la parte más importante. "
        f"Por ahora, el misterio continúa abierto. Y lo que viene después podría "
        f"cambiar la historia por completo."
    )

    escenas = [
        {
            "texto": "Todo comenzó con un descubrimiento inesperado.",
            "visual": f"Escena cinematográfica misteriosa relacionada con {tema}"
        },
        {
            "texto": "Al principio, nadie le dio importancia.",
            "visual": "Lugar vacío, ambiente inquietante, iluminación dramática"
        },
        {
            "texto": "Aparecieron detalles que no tenían explicación.",
            "visual": "Primer plano de documentos, fotografías y pistas"
        },
        {
            "texto": "Los investigadores comenzaron a reunir información.",
            "visual": "Investigadores examinando evidencias en una habitación"
        },
        {
            "texto": "Cada nueva pista abría otra pregunta.",
            "visual": "Montaje cinematográfico de pistas y objetos misteriosos"
        },
        {
            "texto": "Apareció un detalle que nadie había notado.",
            "visual": "Primer plano de un objeto oculto entre las evidencias"
        },
        {
            "texto": "El misterio continúa abierto.",
            "visual": "Paisaje oscuro y misterioso con cámara alejándose"
        },
    ]

    return {
        "titulo_serie": tema,
        "titulo": titulo,
        "parte": episodio,
        "narracion": narracion,
        "escenas": escenas,
    }


def validar_guion(guion):
    if not isinstance(guion, dict):
        return False

    campos = ["titulo_serie", "titulo", "parte", "narracion", "escenas"]

    if not all(campo in guion for campo in campos):
        return False

    if not isinstance(guion["narracion"], str):
        return False

    if len(guion["narracion"].split()) < 80:
        return False

    if not isinstance(guion["escenas"], list):
        return False

    if len(guion["escenas"]) < 3:
        return False

    for escena in guion["escenas"]:
        if not isinstance(escena, dict):
            return False

        if "texto" not in escena or "visual" not in escena:
            return False

    return True


def obtener_guion_hoy():
    historial = cargar_historial()

    episodios = historial.get("episodios", [])

    if episodios:
        ultimo = episodios[-1]

        if ultimo.get("parte", 0) < 5:
            tema = ultimo.get("titulo_serie", "Misterios inexplicables")
            episodio = ultimo.get("parte", 0) + 1
        else:
            tema = elegir_tema(historial)
            episodio = 1
    else:
        tema = elegir_tema(historial)
        episodio = 1

    prompt = crear_prompt(tema, episodio)
    guion = consultar_groq(prompt)

    if not validar_guion(guion):
        print("[AVISO] Usando guion de respaldo.")
        guion = crear_guion_respaldo(tema, episodio)

    guion["parte"] = episodio

    identificador = hashlib.sha256(
        f"{guion['titulo_serie']}-{guion['titulo']}-{episodio}".encode("utf-8")
    ).hexdigest()[:16]

    guion["id"] = identificador
    guion["fecha"] = datetime.now(timezone.utc).isoformat()

    historial.setdefault("episodios", []).append(guion)
    historial.setdefault("temas", [])

    if tema not in historial["temas"]:
        historial["temas"].append(tema)

    historial["episodios"] = historial["episodios"][-100:]
    guardar_historial(historial)

    print(f"[GUION] {guion['titulo']}")
    print(f"[SERIE] {guion['titulo_serie']} - Parte {episodio}")

    return guion