
import os
import json
import random
import hashlib
import requests
from datetime import datetime, timezone

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
HISTORIAL = "historial.json"

DURACION_MAXIMA = 178

CATEGORIAS = {
    "drama": {
        "nombre": "DRAMA EMOCIONAL",
        "temas": [
            "El secreto que destruyó una amistad",
            "La hermana que ocultaba una verdad",
            "El mejor amigo que traicionó su promesa",
            "La carta que llegó demasiado tarde",
            "La familia que guardaba un secreto",
            "El niño al que nadie quería escuchar",
            "La promesa que cambió dos vidas",
            "La verdad detrás de una fotografía",
            "El regalo que nadie esperaba",
            "La persona que regresó cuando todos la daban por perdida",
            "La mentira que separó a dos hermanos",
            "El sacrificio que nadie conocía",
        ],
        "reglas": """
- Crea una historia emocional y atrapante.
- Usa secretos, amistad, familia, confianza, celos,
  decisiones difíciles, perdón o sacrificios.
- Puede haber tensión y conflictos, pero sin violencia gráfica.
- Los personajes deben tener motivaciones creíbles.
- Incluye un giro inesperado que tenga sentido.
- Termina con una emoción fuerte o una pregunta que invite
  a comentar.
- No conviertas todos los finales en tragedias.
"""
    },
    "aventura": {
        "nombre": "AVENTURA INFANTIL",
        "temas": [
            "El pequeño zorro que encontró una puerta mágica",
            "La tortuga que quería llegar a las estrellas",
            "El dragón que tenía miedo de volar",
            "La aventura del perro que podía hablar",
            "El bosque donde los animales guardaban un secreto",
            "El mapa escondido dentro de una botella",
            "La niña que encontró una ciudad diminuta",
            "El robot que quería tener un amigo",
            "El pingüino que perdió su hogar",
            "La isla de los juguetes olvidados",
            "El gato que descubrió un mundo secreto",
            "La carrera para salvar el árbol mágico",
        ],
        "reglas": """
- Crea una aventura divertida, emocionante y apta para niños.
- Usa animales con personalidad, personajes fantásticos,
  mundos sorprendentes, retos y descubrimientos.
- Incluye humor, imaginación y suspenso apropiado.
- El protagonista debe enfrentar un problema y buscar
  una solución ingeniosa.
- Incluye una enseñanza natural sobre amistad, valentía,
  respeto, bondad, confianza o trabajo en equipo.
- Evita sustos fuertes, violencia gráfica y temas adultos.
- Termina con una sorpresa emocionante o divertida.
"""
    },
}

ESTILOS_VISUALES = {
    "cinematico": {
        "nombre": "Cinematográfico narrativo",
        "descripcion": (
            "High quality cinematic storytelling scenes, "
            "expressive characters, colorful environments, "
            "dynamic camera movement and dramatic lighting."
        )
    }
}


def cargar_historial():
    if not os.path.exists(HISTORIAL):
        return {
            "episodios": [],
            "temas": [],
            "estilos": [],
            "categorias": [],
        }

    try:
        with open(HISTORIAL, encoding="utf-8") as archivo:
            datos = json.load(archivo)

        if not isinstance(datos, dict):
            raise ValueError("Historial inválido.")

        for campo in (
            "episodios",
            "temas",
            "estilos",
            "categorias",
        ):
            if not isinstance(datos.get(campo), list):
                datos[campo] = []

        return datos

    except Exception as error:
        print(f"[AVISO] No se pudo leer el historial: {error}")

        return {
            "episodios": [],
            "temas": [],
            "estilos": [],
            "categorias": [],
        }


def guardar_historial(datos):
    temporal = HISTORIAL + ".tmp"

    with open(temporal, "w", encoding="utf-8") as archivo:
        json.dump(
            datos,
            archivo,
            ensure_ascii=False,
            indent=2,
        )

    os.replace(temporal, HISTORIAL)


def elegir_categoria(historial):
    usadas = historial.get("categorias", [])
    ultima = usadas[-1] if usadas else None

    disponibles = [
        categoria
        for categoria in CATEGORIAS
        if categoria != ultima
    ]

    if not disponibles:
        disponibles = list(CATEGORIAS.keys())

    return random.choice(disponibles)


def elegir_tema(categoria, historial):
    temas = CATEGORIAS[categoria]["temas"]
    usados = historial.get("temas", [])

    disponibles = [
        tema for tema in temas
        if tema not in usados
    ]

    if not disponibles:
        disponibles = temas.copy()

    return random.choice(disponibles)


def crear_prompt(tema, episodio, categoria):
    datos = CATEGORIAS[categoria]
    nombre_categoria = datos["nombre"]

    return f"""
Crea un guion ORIGINAL para YouTube Shorts.

CATEGORÍA: {nombre_categoria}
TEMA: {tema}
EPISODIO: {episodio} de 5

IDENTIDAD DEL CONTENIDO:
{datos["reglas"]}

REQUISITOS DE NARRACIÓN:
- Escribe entre 180 y 250 palabras.
- Duración máxima absoluta: {DURACION_MAXIMA} segundos.
- Español mexicano natural y fácil de entender.
- Empieza directamente con un gancho impactante.
- Los primeros 3 segundos deben despertar curiosidad.
- No uses saludos ni introducciones aburridas.
- Mantén el interés durante toda la historia.
- Incluye diálogos breves cuando ayuden a la emoción.
- Añade cambios de ritmo y detalles sorprendentes.
- El final debe dejar una emoción o una pregunta memorable.
- No repitas frases genéricas.
- No copies historias conocidas ni personajes protegidos.
- Crea personajes y situaciones originales.
- Si es una parte intermedia, conecta con el siguiente episodio.
- No cierres toda la historia antes del episodio 5.

REQUISITOS VISUALES:
- Crea entre 6 y 8 escenas.
- Cada escena debe corresponder al fragmento narrado.
- El campo "texto" debe estar en español.
- El campo "visual" DEBE estar en inglés.
- Usa entre 5 y 10 palabras concretas en inglés.
- Describe qué personaje aparece, qué hace y dónde está.
- Describe acciones visibles, no emociones abstractas.
- Cada escena debe tener una composición diferente.
- Mantén los mismos personajes y su apariencia entre escenas.
- No incluyas letras, subtítulos ni logotipos en la imagen.
- No uses imágenes aleatorias que no correspondan al relato.

ESTILO VISUAL:
Cinematográfico narrativo.
{ESTILOS_VISUALES["cinematico"]["descripcion"]}

IMPORTANTE:
La categoría debe conservar su identidad.
No mezcles drama emocional con aventura infantil.

Responde exclusivamente con JSON válido:

{{
  "categoria": "{categoria}",
  "titulo_serie": "{tema}",
  "titulo": "Título atractivo",
  "parte": {episodio},
  "estilo_visual": "cinematico",
  "gancho": "Frase inicial impactante",
  "narracion": "Narración completa en español mexicano",
  "escenas": [
    {{
      "texto": "Fragmento de narración en español",
      "visual": "Specific visible cinematic scene in English"
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
                            "Creas historias originales y muy entretenidas. "
                            "Respetas estrictamente la categoría solicitada. "
                            "Escribes en español mexicano natural. "
                            "Las descripciones visuales deben estar en inglés, "
                            "ser concretas y representar exactamente la escena. "
                            "Conservas la apariencia de los personajes. "
                            "Respondes exclusivamente JSON válido."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                "temperature": 0.9,
                "max_tokens": 3500,
                "response_format": {
                    "type": "json_object"
                },
            },
            timeout=90,
        )

        respuesta.raise_for_status()

        contenido = respuesta.json()[
            "choices"
        ][0]["message"]["content"]

        return json.loads(contenido)

    except Exception as error:
        print(f"[AVISO] Error de Groq: {error}")
        return None


def crear_guion_respaldo(tema, episodio, categoria):
    if categoria == "aventura":
        narracion = (
            f"¡Nadie podía creer lo que acababa de encontrar! "
            f"Todo comenzó cuando el protagonista descubrió algo "
            f"extraordinario relacionado con {tema.lower()}. "
            "Al principio parecía una simple coincidencia, "
            "pero una pequeña pista reveló que aquello escondía "
            "una aventura mucho más grande. "
            "Decidió investigar, aunque sabía que no sería fácil. "
            "En el camino encontró obstáculos inesperados y "
            "conoció a alguien que necesitaba ayuda. "
            "Podía continuar solo o detenerse para ayudar. "
            "Eligió ayudar, y esa decisión cambió todo. "
            "Juntos encontraron una pista que nadie había visto. "
            "Pero justo cuando pensaban que habían resuelto "
            "el misterio, apareció un último desafío. "
            "Tuvieron que usar su ingenio, confiar el uno en el otro "
            "y trabajar en equipo. "
            "Finalmente descubrieron que el verdadero tesoro "
            "no era lo que estaban buscando, sino lo que habían "
            "aprendido durante el camino. "
            "Y todavía quedaba una sorpresa: aquella aventura "
            "apenas estaba comenzando. "
            "¿Te atreverías a descubrir qué viene después?"
        )

        escenas = [
            {
                "texto": "El protagonista encontró algo extraordinario.",
                "visual": "Curious young fox discovering glowing treasure chest"
            },
            {
                "texto": "Una pista reveló una aventura más grande.",
                "visual": "Small animal examining magical ancient map"
            },
            {
                "texto": "Encontró obstáculos inesperados.",
                "visual": "Colorful fantasy forest obstacle bridge"
            },
            {
                "texto": "Conoció a alguien que necesitaba ayuda.",
                "visual": "Friendly cartoon animals meeting in forest"
            },
            {
                "texto": "Juntos encontraron una pista.",
                "visual": "Two cute animal friends finding hidden key"
            },
            {
                "texto": "Apareció un último desafío.",
                "visual": "Magical mountain adventure glowing portal"
            },
            {
                "texto": "La aventura apenas estaba comenzando.",
                "visual": "Happy animal friends exploring colorful fantasy world"
            },
        ]

    else:
        narracion = (
            f"¡Lo que descubrió cambió todo para siempre! "
            f"La historia comenzó con un secreto relacionado "
            f"con {tema.lower()}. "
            "Durante mucho tiempo, nadie se atrevió a hablar "
            "de lo que realmente había ocurrido. "
            "Pero un pequeño detalle hizo que todo empezara "
            "a parecer diferente. "
            "Una persona decidió investigar y encontró una pista "
            "que no esperaba. "
            "Cuando preguntó la verdad, recibió una respuesta "
            "que le rompió el corazón. "
            "Podía marcharse para siempre o escuchar una explicación. "
            "Decidió escuchar, aunque sabía que podía salir lastimada. "
            "Entonces apareció un recuerdo que nadie había mencionado. "
            "Aquello cambió por completo la historia. "
            "Lo que parecía una traición escondía una decisión "
            "difícil que nadie había comprendido. "
            "Pero todavía faltaba conocer la verdad más importante. "
            "A veces, las personas que más queremos también "
            "cometen errores que deben aprender a reparar. "
            "¿Tú habrías perdonado después de descubrirlo?"
        )

        escenas = [
            {
                "texto": "La historia comenzó con un secreto.",
                "visual": "Young woman holding mysterious sealed letter"
            },
            {
                "texto": "Un pequeño detalle cambió todo.",
                "visual": "Close up old family photograph on wooden table"
            },
            {
                "texto": "Alguien decidió investigar.",
                "visual": "Person searching old documents in bedroom"
            },
            {
                "texto": "La respuesta le rompió el corazón.",
                "visual": "Emotional young person sitting alone by window"
            },
            {
                "texto": "Apareció un recuerdo inesperado.",
                "visual": "Two childhood friends looking at old photograph"
            },
            {
                "texto": "La historia cambió por completo.",
                "visual": "Family members having emotional conversation at home"
            },
            {
                "texto": "¿Habrías perdonado después de descubrirlo?",
                "visual": "Two friends reconciling in warm sunset light"
            },
        ]

    return {
        "categoria": categoria,
        "titulo_serie": tema,
        "titulo": f"{tema} - Parte {episodio}",
        "parte": episodio,
        "estilo_visual": "cinematico",
        "gancho": narracion.split(".")[0],
        "narracion": narracion,
        "escenas": escenas,
    }


def validar_guion(guion):
    if not isinstance(guion, dict):
        return False

    obligatorios = [
        "categoria",
        "titulo_serie",
        "titulo",
        "narracion",
        "escenas",
    ]

    if not all(campo in guion for campo in obligatorios):
        return False

    if guion.get("categoria") not in CATEGORIAS:
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

    if episodios:
        ultimo = episodios[-1]

        if ultimo.get("parte", 0) < 5:
            tema = ultimo.get(
                "titulo_serie",
                CATEGORIAS["drama"]["temas"][0],
            )

            episodio = ultimo.get("parte", 0) + 1
            categoria = ultimo.get("categoria", "drama")

            if categoria not in CATEGORIAS:
                categoria = "drama"

        else:
            categoria = elegir_categoria(historial)
            tema = elegir_tema(categoria, historial)
            episodio = 1

    else:
        categoria = elegir_categoria(historial)
        tema = elegir_tema(categoria, historial)
        episodio = 1

    guion = consultar_groq(
        crear_prompt(
            tema,
            episodio,
            categoria,
        )
    )

    if not validar_guion(guion):
        print("[AVISO] Se utilizará el guion de respaldo.")

        guion = crear_guion_respaldo(
            tema,
            episodio,
            categoria,
        )

    guion["categoria"] = categoria
    guion["titulo_serie"] = tema
    guion["parte"] = episodio
    guion["estilo_visual"] = "cinematico"

    guion.setdefault(
        "gancho",
        guion["narracion"].split(".")[0],
    )

    identificador = hashlib.sha256(
        f"{categoria}-{tema}-{episodio}-{guion['titulo']}".encode("utf-8")
    ).hexdigest()[:16]

    guion["id"] = identificador

    guion["fecha"] = datetime.now(
        timezone.utc
    ).isoformat()

    print(f"[CATEGORÍA] {CATEGORIAS[categoria]['nombre']}")
    print(f"[GUION] {guion['titulo']}")
    print(f"[SERIE] {tema} - Parte {episodio}")

    for numero, escena in enumerate(
        guion["escenas"],
        start=1,
    ):
        print(
            f"[VISUAL {numero}] {escena['visual']}"
        )

    return guion


def registrar_guion_completado(guion):
    """Registra un episodio únicamente después de renderizarlo."""

    if not validar_guion(guion):
        raise ValueError(
            "No se puede registrar un guion inválido."
        )

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
    categoria = guion.get("categoria")

    if tema and tema not in historial["temas"]:
        historial["temas"].append(tema)

    if estilo:
        historial["estilos"].append(estilo)

    if categoria in CATEGORIAS:
        historial["categorias"].append(categoria)

    historial["episodios"] = historial["episodios"][-100:]
    historial["temas"] = historial["temas"][-100:]
    historial["estilos"] = historial["estilos"][-100:]
    historial["categorias"] = historial["categorias"][-100:]

    guardar_historial(historial)

    print("[HISTORIAL] Episodio terminado y registrado.")
