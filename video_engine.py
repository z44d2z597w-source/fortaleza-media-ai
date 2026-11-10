
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
    "Historias sorprendentes",
    "Casos de misterio",
    "Historias de humor",
    "Situaciones inesperadas",
    "Curiosidades del mundo",
    "Historias con finales inesperados",
]

ESTILOS_VISUALES = {
    "minecraft": {
        "nombre": "Minecraft Parkour",
        "busquedas": [
            "minecraft parkour gameplay",
            "minecraft parkour",
            "minecraft jumping gameplay",
        ],
        "descripcion": "Gameplay de Minecraft Parkour dinámico, saltos y obstáculos."
    },

    "satisfactorio": {
        "nombre": "Videos satisfactorios",
        "busquedas": [
            "satisfying kinetic sand",
            "satisfying slime",
            "satisfying cutting",
            "oddly satisfying video",
        ],
        "descripcion": "Videos visualmente satisfactorios, movimientos y procesos hipnóticos."
    },

    "roblox": {
        "nombre": "Roblox Obby",
        "busquedas": [
            "roblox obby gameplay",
            "roblox obstacle course",
            "obby gameplay",
        ],
        "descripcion": "Gameplay colorido de obstáculos, saltos y recorridos de Roblox."
    },

    "cinematico": {
        "nombre": "Cinematográfico",
        "busquedas": [
            "cinematic dark mystery",
            "cinematic abandoned places",
            "dark cinematic atmosphere",
            "cinematic suspense footage",
        ],
        "descripcion": "Imágenes cinematográficas, suspenso, lugares misteriosos y movimientos de cámara."
    },
}


def cargar_historial():
    if not os.path.exists(HISTORIAL):
        return {
            "episodios": [],
            "temas": [],
            "estilos": []
        }

    try:
        with open(HISTORIAL, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)

        if not isinstance(datos, dict):
            raise ValueError("Historial inválido")

        datos.setdefault("episodios", [])
        datos.setdefault("temas", [])
        datos.setdefault("estilos", [])

        return datos

    except Exception:
        return {
            "episodios": [],
            "temas": [],
            "estilos": []
        }


def guardar_historial(datos):
    temporal = HISTORIAL + ".tmp"

    with open(temporal, "w", encoding="utf-8") as archivo:
        json.dump(
            datos,
            archivo,
            ensure_ascii=False,
            indent=2
        )

    os.replace(temporal, HISTORIAL)


def elegir_tema(historial):
    usados = historial.get("temas", [])

    disponibles = [
        tema for tema in TEMAS
        if tema not in usados
    ]

    if not disponibles:
        historial["temas"] = []
        disponibles = TEMAS.copy()

    return random.choice(disponibles)


def elegir_estilo_visual(historial):
    estilos = list(ESTILOS_VISUALES.keys())

    usados = historial.get("estilos", [])

    # Evitar repetir los dos estilos más recientes.
    recientes = usados[-2:]

    disponibles = [
        estilo for estilo in estilos
        if estilo not in recientes
    ]

    if not disponibles:
        disponibles = estilos.copy()

    # Priorizar los estilos que menos se han utilizado.
    conteos = {
        estilo: usados.count(estilo)
        for estilo in disponibles
    }

    minimo = min(conteos.values())

    equilibrados = [
        estilo for estilo in disponibles
        if conteos[estilo] == minimo
    ]

    return random.choice(equilibrados)


def crear_prompt(tema, episodio, estilo):
    datos_estilo = ESTILOS_VISUALES[estilo]

    return f"""
Crea un guion original en español mexicano para un YouTube Short.

TEMA: {tema}
EPISODIO: {episodio} de 5

ESTILO VISUAL ASIGNADO:
{datos_estilo["nombre"]}

DESCRIPCIÓN VISUAL:
{datos_estilo["descripcion"]}

DURACIÓN:
- Entre 230 y 270 palabras.
- Narración natural para aproximadamente 2 minutos.
- No superar 178 segundos de audio.

REGLAS PARA ATRAPAR A LA AUDIENCIA:

1. Los primeros 3 segundos deben tener una frase impactante.
2. No empieces con saludos ni presentaciones.
3. Despierta curiosidad desde la primera frase.
4. Mantén preguntas abiertas durante la narración.
5. Introduce información nueva constantemente.
6. Evita explicaciones largas y aburridas.
7. Utiliza cambios de ritmo y tensión.
8. Termina con una revelación, giro o pregunta que provoque comentarios.
9. Cuando sea una serie, conecta con el siguiente episodio.
10. No inventes casos reales ni presentes ficción como noticia.

VARIEDAD DE CONTENIDO:

Alterna entre:
- Historias sorprendentes.
- Misterios.
- Curiosidades.
- Suspenso.
- Humor.
- Datos inesperados.
- Historias de supervivencia.
- Giros inesperados.

No repitas estructuras de narración de episodios anteriores.

ESCENAS:

- Incluye entre 6 y 8 escenas.
- Cada escena debe tener una descripción visual concreta.
- Las escenas deben acompañar lo que se está contando.
- No pongas imágenes estáticas como instrucción visual.
- No incluyas texto, subtítulos ni logotipos dentro de las escenas.

Responde exclusivamente con JSON válido:

{{
  "titulo_serie": "Nombre de la serie",
  "titulo": "Título atractivo del episodio",
  "parte": {episodio},
  "estilo_visual": "{estilo}",
  "gancho": "Frase inicial impactante",
  "narracion": "Narración completa",
  "escenas": [
    {{
      "texto": "Parte de la narración",
      "visual": "Descripción visual concreta para el fondo"
    }}
  ]
}}
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
                "content": (
                    "Eres un guionista profesional de YouTube Shorts. "
                    "Escribes historias originales en español mexicano, "
                    "con ritmo rápido, ganchos fuertes y finales memorables. "
                    "Respondes exclusivamente JSON válido."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.95,
        "max_tokens": 3500,
        "response_format": {
            "type": "json_object"
        },
    }

    try:
        respuesta = requests.post(
            url,
            headers=encabezados,
            json=datos,
            timeout=90,
        )

        respuesta.raise_for_status()

        contenido = respuesta.json()["choices"][0]["message"]["content"]

        return json.loads(contenido)

    except Exception as error:
        print(f"[AVISO] Groq no disponible: {error}")
        return None


def crear_guion_respaldo(tema, episodio, estilo):
    titulo = f"El misterio que nadie esperaba - Parte {episodio}"

    narracion = (
        f"Hay algo sobre {tema.lower()} que casi nadie conoce. "
        "Todo comenzó con un descubrimiento que parecía insignificante. "
        "Al principio, nadie pensó que aquello pudiera cambiar lo que "
        "se sabía hasta ese momento. Pero cuando aparecieron nuevos "
        "detalles, la situación se volvió mucho más extraña. "
        "Las primeras explicaciones parecían tener sentido, hasta que "
        "una pista inesperada puso todo de cabeza. "
        "Algunas personas intentaron encontrar una respuesta sencilla, "
        "pero cada explicación abría una pregunta todavía más difícil. "
        "Lo curioso es que un pequeño detalle había estado frente a "
        "todos desde el principio. Nadie lo había relacionado con el "
        "resto de la historia. Cuando finalmente apareció esa conexión, "
        "todo comenzó a verse diferente. "
        "Y aquí viene lo más sorprendente: todavía existe una parte "
        "de esta historia que no tiene una explicación definitiva. "
        "Tal vez la respuesta sea más sencilla de lo que parece. "
        "O tal vez apenas estamos descubriendo el principio. "
        "Porque lo que ocurrió después podría cambiar completamente "
        "la manera de entender este misterio."
    )

    escenas = [
        {
            "texto": "Todo comenzó con un descubrimiento.",
            "visual": f"Descubrimiento relacionado con {tema}, plano dinámico."
        },
        {
            "texto": "Nadie pensó que aquello pudiera cambiarlo todo.",
            "visual": "Escena de sorpresa y reacción ante un descubrimiento."
        },
        {
            "texto": "Aparecieron nuevos detalles.",
            "visual": "Primeros planos de pistas y objetos relacionados con la historia."
        },
        {
            "texto": "Una pista inesperada puso todo de cabeza.",
            "visual": "Revelación visual dramática y movimiento de cámara."
        },
        {
            "texto": "Un pequeño detalle había estado frente a todos.",
            "visual": "Acercamiento a un detalle oculto."
        },
        {
            "texto": "Todo comenzó a verse diferente.",
            "visual": "Montaje visual de la revelación."
        },
        {
            "texto": "La historia todavía no termina.",
            "visual": "Escena final intrigante que deja una pregunta abierta."
        },
    ]

    return {
        "titulo_serie": tema,
        "titulo": titulo,
        "parte": episodio,
        "estilo_visual": estilo,
        "gancho": "Hay algo sobre esta historia que casi nadie conoce.",
        "narracion": narracion,
        "escenas": escenas,
    }


def validar_guion(guion):
    if not isinstance(guion, dict):
        return False

    campos = [
        "titulo_serie",
        "titulo",
        "parte",
        "narracion",
        "escenas",
    ]

    if not all(campo in guion for campo in campos):
        return False

    if not isinstance(guion["narracion"], str):
        return False

    palabras = len(guion["narracion"].split())

    if palabras < 80 or palabras > 300:
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
            tema = ultimo.get(
                "titulo_serie",
                "Misterios inexplicables"
            )

            episodio = ultimo.get("parte", 0) + 1

        else:
            tema = elegir_tema(historial)
            episodio = 1

    else:
        tema = elegir_tema(historial)
        episodio = 1

    estilo = elegir_estilo_visual(historial)

    prompt = crear_prompt(
        tema,
        episodio,
        estilo
    )

    guion = consultar_groq(prompt)

    if not validar_guion(guion):
        print("[AVISO] Usando guion de respaldo.")

        guion = crear_guion_respaldo(
            tema,
            episodio,
            estilo
        )

    # El estilo elegido por el sistema siempre tiene prioridad.
    guion["estilo_visual"] = estilo
    guion["parte"] = episodio

    guion.setdefault(
        "gancho",
        guion["narracion"].split(".")[0]
    )

    identificador = hashlib.sha256(
        (
            f"{guion['titulo_serie']}-"
            f"{guion['titulo']}-"
            f"{episodio}"
        ).encode("utf-8")
    ).hexdigest()[:16]

    guion["id"] = identificador

    guion["fecha"] = datetime.now(
        timezone.utc
    ).isoformat()

    historial.setdefault("episodios", []).append(guion)
    historial.setdefault("temas", [])
    historial.setdefault("estilos", [])

    if tema not in historial["temas"]:
        historial["temas"].append(tema)

    historial["estilos"].append(estilo)

    historial["episodios"] = historial["episodios"][-100:]
    historial["temas"] = historial["temas"][-100:]
    historial["estilos"] = historial["estilos"][-100:]

    guardar_historial(historial)

    print(f"[GUION] {guion['titulo']}")
    print(f"[SERIE] {guion['titulo_serie']} - Parte {episodio}")
    print(f"[ESTILO VISUAL] {ESTILOS_VISUALES[estilo]['nombre']}")

    return guion
