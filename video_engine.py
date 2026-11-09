
import json
import random
import re
import requests

from datetime import datetime, timedelta, timezone
from pathlib import Path


# ==========================================================
# FORTALEZA MEDIA AI 5.0
# MOTOR EDITORIAL INTELIGENTE
# ==========================================================

VERSION = "5.0"

IDIOMA = "es-MX"

ARCHIVO_GUION = Path("guion.json")
ARCHIVO_HISTORIAL = Path("historial_temas.json")

URL_PAGEVIEWS = (
    "https://wikimedia.org/api/rest_v1/"
    "metrics/pageviews/top/es.wikipedia/all-access/user"
)

URL_WIKIPEDIA = (
    "https://es.wikipedia.org/w/api.php"
)

CABECERAS = {
    "User-Agent": "FORTALEZA-MEDIA-AI/5.0"
}

MAX_HISTORIAL = 300

MAX_CARACTERES_INVESTIGACION = 10000

TEMAS_RESPALDO = [
    "Fosa de las Marianas",
    "Bioluminiscencia",
    "Tiburón de Groenlandia",
    "Pulpo",
    "Aurora polar",
    "Agujeros negros",
    "Volcanes submarinos",
    "Antártida",
    "Planeta Marte",
    "Cerebro humano",
    "Bosques tropicales",
    "Extinción de especies",
    "Océanos",
    "Evolución humana",
    "Vida en condiciones extremas",
]

FRASES_GANCHO = [
    "Lo que estás a punto de descubrir parece imposible, pero tiene una explicación.",
    "Existe algo relacionado con este tema que muy pocas personas conocen.",
    "Hay un detalle de esta historia que cambia por completo la manera de entenderla.",
    "Prepárate, porque este descubrimiento tiene mucho más detrás de lo que parece.",
    "A primera vista parece algo normal, pero la realidad es mucho más sorprendente.",
]

FRASES_TRANSICION = [
    "Pero aquí es donde la historia se vuelve todavía más interesante.",
    "Y eso nos lleva a una pregunta importante.",
    "Sin embargo, existe otro detalle que merece atención.",
    "Lo interesante es que este fenómeno tiene más de una explicación.",
    "Para comprenderlo, hay que observar lo que ocurre detrás.",
    "Y precisamente ahí aparece uno de los datos más importantes.",
]

FRASES_CIERRE = [
    "Y aunque conocemos mucho más sobre este tema, todavía quedan preguntas por responder.",
    "Este es un recordatorio de cuánto nos falta por descubrir.",
    "La realidad demuestra que el mundo todavía guarda historias extraordinarias.",
]


# ==========================================================
# CONEXIÓN HTTP
# ==========================================================

def obtener_json(url, parametros=None, timeout=25):

    respuesta = requests.get(
        url,
        params=parametros,
        headers=CABECERAS,
        timeout=timeout
    )

    respuesta.raise_for_status()

    return respuesta.json()


# ==========================================================
# HISTORIAL DE TEMAS
# ==========================================================

def cargar_historial():

    if not ARCHIVO_HISTORIAL.exists():
        return []

    try:
        with open(
            ARCHIVO_HISTORIAL,
            "r",
            encoding="utf-8"
        ) as archivo:

            datos = json.load(archivo)

        if isinstance(datos, list):
            return datos

        return []

    except Exception as error:

        print("[HISTORIAL] No se pudo leer:", error)

        return []


def guardar_historial(historial):

    historial = historial[-MAX_HISTORIAL:]

    temporal = ARCHIVO_HISTORIAL.with_suffix(".tmp")

    with open(
        temporal,
        "w",
        encoding="utf-8"
    ) as archivo:

        json.dump(
            historial,
            archivo,
            ensure_ascii=False,
            indent=4
        )

    temporal.replace(ARCHIVO_HISTORIAL)


def tema_ya_utilizado(titulo, historial):

    normalizado = titulo.strip().lower()

    for elemento in historial:

        if isinstance(elemento, dict):

            anterior = str(
                elemento.get("titulo", "")
            ).strip().lower()

        else:

            anterior = str(elemento).strip().lower()

        if anterior == normalizado:
            return True

    return False


# ==========================================================
# DETECCIÓN DE TEMAS POPULARES
# ==========================================================

def obtener_fecha_pageviews():

    ayer = datetime.now(
        timezone.utc
    ).date() - timedelta(days=1)

    return ayer.strftime("%Y/%m/%d")


def limpiar_titulo(titulo):

    titulo = str(titulo).replace("_", " ")

    titulo = re.sub(
        r"\s*\([^)]*desambiguación[^)]*\)",
        "",
        titulo,
        flags=re.IGNORECASE
    )

    return titulo.strip()


def titulo_valido(titulo):

    titulo = limpiar_titulo(titulo)

    if len(titulo) < 5:
        return False

    prohibidas = [
        "portada",
        "wikipedia:",
        "especial:",
        "archivo:",
        "categoría:",
        "discusión:",
        "anexo:",
        "plantilla:",
        "usuario:",
        "ayuda:",
        "fecha",
    ]

    bajo = titulo.lower()

    if any(
        palabra in bajo
        for palabra in prohibidas
    ):
        return False

    if re.fullmatch(
        r"\d{1,4}",
        titulo
    ):
        return False

    if re.fullmatch(
        r"\d{1,2}\s+de\s+\w+",
        bajo
    ):
        return False

    return True


def descubrir_temas():

    fecha = obtener_fecha_pageviews()

    url = f"{URL_PAGEVIEWS}/{fecha}"

    print("[TENDENCIAS] Consultando temas populares...")

    try:

        datos = obtener_json(url)

        articulos = datos.get(
            "items", [{}]
        )[0].get("articles", [])

        articulos = sorted(
            articulos,
            key=lambda x: x.get("views", 0),
            reverse=True
        )

        resultado = []

        for articulo in articulos:

            titulo = limpiar_titulo(
                articulo.get("article", "")
            )

            if not titulo_valido(titulo):
                continue

            resultado.append({
                "titulo": titulo,
                "visitas": articulo.get("views", 0),
            })

            if len(resultado) >= 35:
                break

        print(
            "[TENDENCIAS] Temas encontrados:",
            len(resultado)
        )

        return resultado

    except Exception as error:

        print(
            "[TENDENCIAS] No se pudo consultar:",
            error
        )

        return []


# ==========================================================
# INVESTIGACIÓN DEL TEMA
# ==========================================================

def investigar_tema(titulo):

    print("[INVESTIGACIÓN]", titulo)

    parametros = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "titles": titulo,
        "explaintext": 1,
        "exsectionformat": "plain",
        "redirects": 1,
    }

    try:

        datos = obtener_json(
            URL_WIKIPEDIA,
            parametros
        )

        paginas = datos.get(
            "query", {}
        ).get("pages", {})

        for pagina in paginas.values():

            extracto = pagina.get(
                "extract",
                ""
            )

            extracto = limpiar_texto(extracto)

            if len(extracto) < 350:
                return None

            return {
                "titulo": pagina.get(
                    "title",
                    titulo
                ),
                "texto": extracto[
                    :MAX_CARACTERES_INVESTIGACION
                ],
                "url": (
                    "https://es.wikipedia.org/wiki/"
                    + pagina.get(
                        "title",
                        titulo
                    ).replace(" ", "_")
                )
            }

    except Exception as error:

        print(
            "[INVESTIGACIÓN] Error:",
            error
        )

    return None


def limpiar_texto(texto):

    texto = re.sub(
        r"\[\d+\]",
        "",
        str(texto)
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


# ==========================================================
# SELECCIÓN AUTOMÁTICA DEL TEMA
# ==========================================================

def seleccionar_tema():

    historial = cargar_historial()

    tendencias = descubrir_temas()

    candidatos = [
        elemento["titulo"]
        for elemento in tendencias
        if not tema_ya_utilizado(
            elemento["titulo"],
            historial
        )
    ]

    random.shuffle(candidatos)

    for titulo in candidatos[:15]:

        investigacion = investigar_tema(titulo)

        if investigacion:

            print(
                "[TEMA SELECCIONADO]",
                investigacion["titulo"]
            )

            return investigacion

    # Respaldo automático.
    respaldo = [
        tema
        for tema in TEMAS_RESPALDO
        if not tema_ya_utilizado(
            tema,
            historial
        )
    ]

    random.shuffle(respaldo)

    for titulo in respaldo:

        investigacion = investigar_tema(titulo)

        if investigacion:
            return investigacion

    # Si todos los temas se han utilizado,
    # reinicia el ciclo de selección.
    print(
        "[HISTORIAL] Reiniciando ciclo de temas."
    )

    guardar_historial([])

    for titulo in TEMAS_RESPALDO:

        investigacion = investigar_tema(titulo)

        if investigacion:
            return investigacion

    raise RuntimeError(
        "No se pudo encontrar un tema investigable."
    )


# ==========================================================
# ANÁLISIS DEL CONTENIDO
# ==========================================================

def dividir_oraciones(texto):

    texto = limpiar_texto(texto)

    oraciones = re.split(
        r"(?<=[.!?])\s+",
        texto
    )

    return [
        oracion.strip()
        for oracion in oraciones
        if len(oracion.strip()) > 35
    ]


def dividir_en_bloques(oraciones, cantidad):

    bloques = [
        []
        for _ in range(cantidad)
    ]

    for indice, oracion in enumerate(oraciones):

        posicion = min(
            cantidad - 1,
            int(
                indice * cantidad /
                max(1, len(oraciones))
            )
        )

        bloques[posicion].append(oracion)

    return [
        " ".join(bloque)
        for bloque in bloques
        if bloque
    ]


def contar_palabras(texto):

    return len(
        re.findall(
            r"\b[\wáéíóúñÁÉÍÓÚÑ]+\b",
            texto
        )
    )


# ==========================================================
# CONSTRUCCIÓN DE SHORTS
# ==========================================================

def crear_guion_short(investigacion):

    titulo = investigacion["titulo"]

    oraciones = dividir_oraciones(
        investigacion["texto"]
    )

    if not oraciones:
        raise RuntimeError(
            "No hay información suficiente para el guion."
        )

    gancho = (
        random.choice(FRASES_GANCHO)
        + " "
        + titulo
        + " es un tema que merece atención."
    )

    desarrollo = " ".join(
        oraciones[:5]
    )

    revelacion = (
        random.choice(FRASES_TRANSICION)
        + " "
        + " ".join(oraciones[5:8])
    )

    cierre = (
        random.choice(FRASES_CIERRE)
        + " ¿Qué parte de esta historia te sorprendió más?"
    )

    escenas = [
        {
            "numero": 1,
            "duracion": 7,
            "tipo": "gancho",
            "titulo": titulo,
            "narracion": gancho,
        },
        {
            "numero": 2,
            "duracion": 38,
            "tipo": "desarrollo",
            "titulo": "Lo que necesitas saber",
            "narracion": desarrollo,
        },
        {
            "numero": 3,
            "duracion": 15,
            "tipo": "revelacion_y_cierre",
            "titulo": "El detalle sorprendente",
            "narracion": (
                revelacion + " " + cierre
            ),
        },
    ]

    return {
        "formato": "YouTube Shorts 9:16",
        "duracion": 60,
        "escenas": escenas,
    }


# ==========================================================
# CONSTRUCCIÓN DE VIDEO HORIZONTAL
# ==========================================================

def crear_guion_largo(investigacion):

    titulo = investigacion["titulo"]

    oraciones = dividir_oraciones(
        investigacion["texto"]
    )

    if len(oraciones) < 12:
        return None

    bloques = dividir_en_bloques(
        oraciones,
        8
    )

    if len(bloques) < 6:
        return None

    escenas = []

    titulos = [
        "Una historia que merece conocerse",
        "El contexto",
        "Los primeros detalles",
        "Cómo funciona",
        "Lo que sabemos",
        "Un descubrimiento importante",
        "Lo que todavía falta entender",
        "La conclusión",
    ]

    gancho = (
        random.choice(FRASES_GANCHO)
        + " Hoy vamos a conocer la historia de "
        + titulo
        + "."
    )

    escenas.append({
        "numero": 1,
        "duracion": 20,
        "tipo": "gancho",
        "titulo": titulo,
        "narracion": gancho,
    })

    for indice, bloque in enumerate(bloques[:7]):

        narracion = bloque

        if indice > 0:
            narracion = (
                random.choice(FRASES_TRANSICION)
                + " "
                + narracion
            )

        escenas.append({
            "numero": indice + 2,
            "duracion": 30,
            "tipo": "desarrollo",
            "titulo": titulos[
                min(indice + 1, len(titulos) - 1)
            ],
            "narracion": narracion,
        })

    escenas.append({
        "numero": len(escenas) + 1,
        "duracion": 20,
        "tipo": "cierre",
        "titulo": "Lo que nos deja esta historia",
        "narracion": (
            random.choice(FRASES_CIERRE)
            + " ¿Qué fue lo que más te llamó la atención? "
            "Comparte tu opinión."
        ),
    })

    palabras = sum(
        contar_palabras(escena["narracion"])
        for escena in escenas
    )

    # Un video largo requiere suficiente narración.
    if palabras < 260:
        return None

    return {
        "formato": "YouTube horizontal 16:9",
        "duracion": 240,
        "escenas": escenas,
    }


# ==========================================================
# DECISIÓN EDITORIAL
# ==========================================================

def decidir_formato(investigacion):

    historial = cargar_historial()

    oraciones = dividir_oraciones(
        investigacion["texto"]
    )

    palabras = contar_palabras(
        investigacion["texto"]
    )

    # Se favorecen Shorts, pero se reserva espacio
    # para contenido horizontal cuando hay suficiente material.
    turno_largo = (
        (len(historial) + 1) % 4 == 0
    )

    if turno_largo and palabras >= 500 and len(oraciones) >= 12:

        guion = crear_guion_largo(
            investigacion
        )

        if guion:
            print(
                "[EDITORIAL] Formato horizontal seleccionado."
            )
            return guion

    print(
        "[EDITORIAL] Formato Shorts seleccionado."
    )

    return crear_guion_short(
        investigacion
    )


# ==========================================================
# CREACIÓN DEL GUION FINAL
# ==========================================================

def crear_guion(tema=None):

    if tema and tema.strip().lower() not in (
        "aleatorio",
        "automático",
        "automatico",
        "tendencias"
    ):

        investigacion = investigar_tema(
            tema.strip()
        )

        if not investigacion:
            raise RuntimeError(
                "No se pudo investigar el tema solicitado."
            )

    else:

        investigacion = seleccionar_tema()

    contenido = decidir_formato(
        investigacion
    )

    titulo = investigacion["titulo"]

    escenas = contenido["escenas"]

    palabras = sum(
        contar_palabras(
            escena["narracion"]
        )
        for escena in escenas
    )

    formato = contenido["formato"]

    hashtags = [
        "#FORTALEZAMEDIA",
        "#Curiosidades",
        "#Ciencia",
        "#Conocimiento",
        "#Historias",
    ]

    if "Shorts" in formato:
        hashtags.insert(0, "#Shorts")
    else:
        hashtags.insert(0, "#Documental")

    descripcion = (
        f"{titulo}\n\n"
        "Contenido narrado en español mexicano. "
        "Investigación y contexto basados en la fuente indicada.\n\n"
        f"Fuente de consulta: {investigacion['url']}\n\n"
        + " ".join(hashtags)
    )

    return {
        "version_motor": VERSION,
        "titulo": titulo,
        "formato": formato,
        "duracion": contenido["duracion"],
        "idioma": IDIOMA,
        "estilo": (
            "documental cinematográfico, "
            "divulgación, suspenso y narrativa dinámica"
        ),
        "palabras": palabras,
        "escenas": escenas,
        "descripcion": descripcion,
        "hashtags": hashtags,
        "fuente": investigacion["url"],
        "creado": datetime.now().astimezone().isoformat(),
    }


# ==========================================================
# GUARDAR Y REGISTRAR PRODUCCIÓN
# ==========================================================

def guardar_guion(tema=None):

    guion = crear_guion(tema)

    temporal = ARCHIVO_GUION.with_suffix(".tmp")

    with open(
        temporal,
        "w",
        encoding="utf-8"
    ) as archivo:

        json.dump(
            guion,
            archivo,
            ensure_ascii=False,
            indent=4
        )

    temporal.replace(ARCHIVO_GUION)

    historial = cargar_historial()

    historial.append({
        "titulo": guion["titulo"],
        "formato": guion["formato"],
        "creado": guion["creado"],
    })

    guardar_historial(historial)

    print("=" * 55)
    print("FORTALEZA MEDIA AI 5.0")
    print("GUION GENERADO")
    print("Título:", guion["titulo"])
    print("Formato:", guion["formato"])
    print("Escenas:", len(guion["escenas"]))
    print("Palabras:", guion["palabras"])
    print("=" * 55)

    return guion


if __name__ == "__main__":

    guardar_guion()
