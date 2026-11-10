
import os
import json
import random
import hashlib
import requests
from datetime import datetime, timezone

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
HISTORIAL = "historial.json"

DURACION_MAXIMA = 178

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
    "Historias de humor",
    "Situaciones inesperadas",
    "Curiosidades del mundo",
    "Historias con finales inesperados",
]

ESTILOS_VISUALES = {
    "minecraft": {
        "nombre": "Minecraft Parkour",
        "descripcion": "Gameplay dinámico, saltos y obstáculos."
    },
    "satisfactorio": {
        "nombre": "Videos satisfactorios",
        "descripcion": "Procesos visualmente satisfactorios, slime, arena y movimientos hipnóticos."
    },
    "roblox": {
        "nombre": "Roblox Obby",
        "descripcion": "Gameplay colorido de obstáculos y recorridos."
    },
    "cinematico": {
        "nombre": "Cinematográfico",
        "descripcion": "Imágenes cinematográficas, misterio, suspenso y atmósferas oscuras."
    },
}


def cargar_historial():
    if not os.path.exists(HISTORIAL):
        return {"episodios": [], "temas": [], "estilos": []}

    try:
        with open(HISTORIAL, encoding="utf-8") as archivo:
            datos = json.load(archivo)

        if not isinstance(datos, dict):
            raise ValueError("Historial inválido")

        for campo in ("episodios", "temas", "estilos"):
            if not isinstance(datos.get(campo), list):
                datos[campo] = []

        return datos

    except Exception as error:
        print(f"[AVISO] No se pudo leer el historial: {error}")
        return {"episodios": [], "temas": [], "estilos": []}


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


def elegir_estilo_visual(historial):
    estilos = list(ESTILOS_VISUALES.keys())
    usados = historial.get("estilos", [])

    recientes = usados[-2:]
    disponibles = [e for e in estilos if e not in recientes]

    if not disponibles:
        disponibles = estilos.copy()

    conteos = {e: usados.count(e) for e in disponibles}
    minimo = min(conteos.values())

    equilibrados = [
        e for e in disponibles
        if conteos[e] == minimo
    ]

    return random.choice(equilibrados)


def crear_prompt(tema, episodio, estilo):
    nombre_estilo = ESTILOS_VISUALES[estilo]["nombre"]
    descripcion = ESTILOS_VISUALES[estilo]["descripcion"]

    return f"""
Crea un guion ORIGINAL para YouTube Shorts en español mexicano.

TEMA: {tema}
EPISODIO: {episodio} de 5
ESTILO VISUAL: {nombre_estilo}
DESCRIPCIÓN: {descripcion}

REQUISITOS:
- Narración de 230 a 270 palabras.
- Duración máxima absoluta: 178 segundos.
- Gancho impactante durante los primeros 3 segundos.
- Nada de saludos ni presentaciones.
- Ritmo rápido y natural.
- Mantén la curiosidad durante todo el relato.
- Añade preguntas, tensión y cambios de ritmo.
- Termina con una revelación o giro memorable.
- No presentes ficción como si fuera un hecho real.
- No inventes datos históricos o científicos.
- Evita repetir estructuras y frases genéricas.
- Si es una serie, conecta con el siguiente episodio.
- Entre 6 y 8 escenas visuales.
- Cada escena debe acompañar lo que se está narrando.
- Las escenas deben tener movimiento y variedad.
- No incluyas subtítulos ni logotipos en las escenas.

Responde exclusivamente con JSON válido:

{{
  "titulo_serie": "{tema}",
  "titulo": "Título atractivo",
  "parte": {episodio},
  "estilo_visual": "{estilo}",
  "gancho": "Frase impactante",
  "narracion": "Narración completa",
  "escenas": [
    {{
      "texto": "Fragmento de narración",
      "visual": "Descripción concreta del fondo"
    }}
  ]
}}
"""


def consultar_groq(prompt):
    if not GROQ_API_KEY:
        print("[AVISO] No se encontró GROQ_API_KEY.")
        return None

    try:
        respuesta = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openai/gpt-oss-120b",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Eres un guionista profesional de Shorts. "
                            "Escribes en español mexicano, con originalidad, "
                            "ritmo rápido y finales sorprendentes. "
                            "Respondes exclusivamente JSON válido."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.9,
                "max_tokens": 3500,
                "response_format": {"type": "json_object"},
            },
            timeout=90,
        )

        respuesta.raise_for_status()
        contenido = respuesta.json()["choices"][0]["message"]["content"]
        return json.loads(contenido)

    except Exception as error:
        print(f"[AVISO] Error de Groq: {error}")
        return None


def crear_guion_respaldo(tema, episodio, estilo):
    narracion = (
        f"Hay un detalle sobre {tema.lower()} que podría cambiar "
        "completamente la manera en que entiendes esta historia. "
        "Todo comenzó con algo que parecía normal. Nadie imaginaba "
        "que aquel pequeño acontecimiento terminaría convirtiéndose "
        "en una situación imposible de ignorar. "
        "Al principio apareció una explicación sencilla. Parecía "
        "resolver todas las dudas, pero había un problema: un detalle "
        "no encajaba. Cuando alguien decidió investigarlo, encontró "
        "una pista que había pasado desapercibida. "
        "Esa pista abrió una nueva posibilidad y, de repente, "
        "lo que parecía una historia común se convirtió en algo "
        "mucho más extraño. Cada respuesta provocaba otra pregunta. "
        "Algunos pensaron que todo era una coincidencia. Otros "
        "creyeron que existía algo más detrás de lo ocurrido. "
        "Pero había una pieza que todavía faltaba. "
        "Cuando esa pieza apareció, la historia tomó un rumbo "
        "completamente diferente. Lo más sorprendente no fue lo "
        "que ocurrió al principio, sino lo que se descubrió después. "
        "Y aquí está el detalle que casi todos pasan por alto: "
        "la primera pista siempre estuvo frente a nosotros. "
        "A veces, la explicación más evidente no es la correcta. "
        "¿Tú qué crees que ocurrió realmente? "
        "Porque esta historia todavía tiene una pregunta pendiente."
    )

    escenas = [
        {
            "texto": "Todo comenzó con algo aparentemente normal.",
            "visual": "Escena dinámica relacionada con el tema."
        },
        {
            "texto": "Apareció una explicación sencilla.",
            "visual": "Movimiento visual que represente una primera explicación."
        },
        {
            "texto": "Un detalle no encajaba.",
            "visual": "Acercamiento dramático a una pista."
        },
        {
            "texto": "Alguien decidió investigarlo.",
            "visual": "Escena de investigación y descubrimiento."
        },
        {
            "texto": "Cada respuesta provocaba otra pregunta.",
            "visual": "Montaje rápido de imágenes relacionadas."
        },
        {
            "texto": "La historia tomó un rumbo diferente.",
            "visual": "Revelación visual inesperada."
        },
        {
            "texto": "Todavía existe una pregunta pendiente.",
            "visual": "Final intrigante con atmósfera de suspenso."
        }
    ]

    return {
        "titulo_serie": tema,
        "titulo": f"Una historia que te hará dudar - Parte {episodio}",
        "parte": episodio,
        "estilo_visual": estilo,
        "gancho": "Hay un detalle que podría cambiarlo todo.",
        "narracion": narracion,
        "escenas": escenas,
    }


def validar_guion(guion):
    if not isinstance(guion, dict):
        return False

    obligatorios = [
        "titulo_serie",
        "titulo",
        "narracion",
        "escenas",
    ]

    if not all(campo in guion for campo in obligatorios):
        return False

    if not isinstance(guion["narracion"], str):
        return False

    palabras = len(guion["narracion"].split())

    if palabras < 80 or palabras > 300:
        return False

    if not isinstance(guion["escenas"], list):
        return False

    if not 3 <= len(guion["escenas"]) <= 8:
        return False

    for escena in guion["escenas"]:
        if not isinstance(escena, dict):
            return False

        if not escena.get("texto") or not escena.get("visual"):
            return False

    return True


def obtener_guion_hoy():
    historial = cargar_historial()
    episodios = historial["episodios"]

    # Solo se utilizan episodios que ya terminaron de renderizarse.
    if episodios:
        ultimo = episodios[-1]

        if ultimo.get("parte", 0) < 5:
            tema = ultimo.get("titulo_serie", TEMAS[0])
            episodio = ultimo.get("parte", 0) + 1
        else:
            tema = elegir_tema(historial)
            episodio = 1
    else:
        tema = elegir_tema(historial)
        episodio = 1

    estilo = elegir_estilo_visual(historial)

    guion = consultar_groq(
        crear_prompt(tema, episodio, estilo)
    )

    if not validar_guion(guion):
        print("[AVISO] Se utilizará el guion de respaldo.")
        guion = crear_guion_respaldo(
            tema,
            episodio,
            estilo,
        )

    # El sistema conserva el tema, episodio y estilo elegidos.
    guion["titulo_serie"] = tema
    guion["parte"] = episodio
    guion["estilo_visual"] = estilo

    guion.setdefault(
        "gancho",
        guion["narracion"].split(".")[0]
    )

    identificador = hashlib.sha256(
        f"{tema}-{episodio}-{guion['titulo']}".encode("utf-8")
    ).hexdigest()[:16]

    guion["id"] = identificador
    guion["fecha"] = datetime.now(timezone.utc).isoformat()

    # IMPORTANTE:
    # Aquí todavía NO se guarda como episodio terminado.
    # Se registra después de completar el renderizado.

    print(f"[GUION] {guion['titulo']}")
    print(f"[SERIE] {tema} - Parte {episodio}")
    print(f"[ESTILO] {ESTILOS_VISUALES[estilo]['nombre']}")

    return guion


def registrar_guion_completado(guion):
    """Registra un episodio únicamente después de renderizarlo."""

    if not validar_guion(guion):
        raise ValueError("No se puede registrar un guion inválido.")

    historial = cargar_historial()
    identificador = guion.get("id")

    if any(
        episodio.get("id") == identificador
        for episodio in historial["episodios"]
    ):
        print("[HISTORIAL] Este episodio ya estaba registrado.")
        return

    historial["episodios"].append(guion)

    tema = guion.get("titulo_serie")
    estilo = guion.get("estilo_visual")

    if tema and tema not in historial["temas"]:
        historial["temas"].append(tema)

    if estilo in ESTILOS_VISUALES:
        historial["estilos"].append(estilo)

    historial["episodios"] = historial["episodios"][-100:]
    historial["temas"] = historial["temas"][-100:]
    historial["estilos"] = historial["estilos"][-100:]

    guardar_historial(historial)

    print("[HISTORIAL] Episodio terminado y registrado.")
