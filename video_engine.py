
import json
import re
import random
import time
import urllib.parse
import urllib.request

from datetime import datetime, timedelta, timezone
from pathlib import Path


# ==========================================================
# FORTALEZA MEDIA AI — VIDEO ENGINE 4.0
# DESCUBRIMIENTO Y CREACIÓN AUTOMÁTICA DE GUIONES
# ==========================================================

VERSION = "4.0"

ARCHIVO_GUION = Path("guion.json")
ARCHIVO_HISTORIAL = Path("historial_temas.json")

IDIOMA = "es-MX"
DURACION = 60

USER_AGENT = (
    "FORTALEZA-MEDIA-AI/4.0 "
    "(educational video production)"
)

URL_PAGEVIEWS = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/"
    "top/es.wikipedia/all-access/user/{fecha}"
)

URL_WIKIPEDIA_API = (
    "https://es.wikipedia.org/w/api.php"
)

# Evita artículos que no sirven como tema principal.
PALABRAS_EXCLUIDAS = [
    "desambiguación",
    "anexo:",
    "categoría:",
    "especial:",
    "wikipedia:",
    "portal:",
    "discusión:",
    "usuario:",
    "plantilla:",
    "archivo:",
    "lista de",
    "elecciones",
    "resultados electorales",
]

# Fuentes de respaldo si Wikipedia no responde.
TEMAS_RESPALDO = [
    "Fosa de las Marianas",
    "Pulpo",
    "Bioluminiscencia",
    "Tiburón de Groenlandia",
    "Aurora polar",
    "Volcanes submarinos",
    "Estrellas de mar",
    "Agujeros negros",
    "Antártida",
    "La Gran Barrera de Coral",
    "Marte",
    "Tardígrados",
    "La selva amazónica",
    "La Luna",
    "El sistema solar",
]


# ==========================================================
# CONEXIÓN A FUENTES PÚBLICAS
# ==========================================================

def obtener_json(url, timeout=15):

    solicitud = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json"
        }
    )

    with urllib.request.urlopen(
        solicitud,
        timeout=timeout
    ) as respuesta:

        contenido = respuesta.read().decode("utf-8")

        return json.loads(contenido)


def fecha_pageviews():

    # Los datos del día anterior suelen estar disponibles
    # con mayor fiabilidad que los del día en curso.
    fecha = datetime.now(timezone.utc).date() - timedelta(days=1)

    return fecha.strftime("%Y/%m/%d")


# ==========================================================
# HISTORIAL PARA EVITAR REPETICIONES
# ==========================================================

def cargar_historial():

    if not ARCHIVO_HISTORIAL.exists():
        return []

    try:
        with ARCHIVO_HISTORIAL.open(
            "r",
            encoding="utf-8"
        ) as archivo:

            datos = json.load(archivo)

        if isinstance(datos, list):
            return datos

        if isinstance(datos, dict):
            return datos.get("temas", [])

    except Exception as error:
        print(f"[HISTORIAL] No se pudo leer: {error}")

    return []


def guardar_historial(historial):

    datos = {
        "version": VERSION,
        "actualizado": datetime.now(
            timezone.utc
        ).isoformat(),
        "temas": historial[-300:]
    }

    ARCHIVO_HISTORIAL.write_text(
        json.dumps(
            datos,
            ensure_ascii=False,
            indent=4
        ),
        encoding="utf-8"
    )


def normalizar(texto):

    texto = str(texto).lower().strip()

    texto = re.sub(
        r"[^a-záéíóúüñ0-9 ]",
        "",
        texto
    )

    return re.sub(r"\s+", " ", texto)


def tema_ya_usado(titulo, historial):

    titulo_normalizado = normalizar(titulo)

    for elemento in historial:

        if isinstance(elemento, str):
            anterior = elemento

        elif isinstance(elemento, dict):
            anterior = elemento.get("titulo", "")

        else:
            continue

        if normalizar(anterior) == titulo_normalizado:
            return True

    return False


# ==========================================================
# DESCUBRIMIENTO DE TEMAS
# ==========================================================

def obtener_temas_populares():

    fecha = fecha_pageviews()

    url = URL_PAGEVIEWS.format(fecha=fecha)

    datos = obtener_json(url)

    articulos = datos.get("items", [])

    if not articulos:
        return []

    paginas = articulos[0].get("articles", [])

    candidatos = []

    for pagina in paginas:

        titulo = pagina.get("article", "").replace("_", " ").strip()

        if not titulo:
            continue

        titulo_lower = titulo.lower()

        if any(
            palabra in titulo_lower
            for palabra in PALABRAS_EXCLUIDAS
        ):
            continue

        # Evitar páginas que sean fechas o números.
        if re.fullmatch(r"[\d\s./-]+", titulo):
            continue

        # Evitar títulos demasiado largos.
        if len(titulo) > 90:
            continue

        candidatos.append({
            "titulo": titulo,
            "visitas": pagina.get("views", 0)
        })

    # Priorizar páginas populares sin elegir siempre
    # necesariamente la primera posición.
    candidatos.sort(
        key=lambda x: x["visitas"],
        reverse=True
    )

    return candidatos[:60]


# ==========================================================
# INVESTIGACIÓN DEL ARTÍCULO
# ==========================================================

def investigar_articulo(titulo):

    parametros = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "exintro": "1",
        "explaintext": "1",
        "redirects": "1",
        "titles": titulo
    }

    url = (
        URL_WIKIPEDIA_API
        + "?"
        + urllib.parse.urlencode(parametros)
    )

    datos = obtener_json(url)

    paginas = datos.get(
        "query",
        {}
    ).get(
        "pages",
        {}
    )

    for pagina in paginas.values():

        extracto = pagina.get(
            "extract",
            ""
        ).strip()

        titulo_real = pagina.get(
            "title",
            titulo
        )

        if len(extracto) >= 300:

            return {
                "titulo": titulo_real,
                "extracto": extracto,
                "url": (
                    "https://es.wikipedia.org/wiki/"
                    + urllib.parse.quote(
                        titulo_real.replace(" ", "_")
                    )
                )
            }

    return None


# ==========================================================
# SELECCIÓN INTELIGENTE DEL TEMA
# ==========================================================

def seleccionar_tema():

    historial = cargar_historial()

    candidatos = []

    try:

        print("[TEMAS] Consultando temas populares...")

        candidatos = obtener_temas_populares()

        print(
            f"[TEMAS] Candidatos encontrados: "
            f"{len(candidatos)}"
        )

    except Exception as error:

        print(
            f"[TEMAS] Consulta no disponible: {error}"
        )

    # Primero se intenta utilizar contenido popular nuevo.
    for candidato in candidatos:

        titulo = candidato["titulo"]

        if tema_ya_usado(titulo, historial):
            continue

        try:

            articulo = investigar_articulo(titulo)

            if articulo:

                articulo["visitas"] = candidato["visitas"]

                print(
                    f"[TEMAS] Tema seleccionado: "
                    f"{articulo['titulo']}"
                )

                return articulo

        except Exception as error:

            print(
                f"[TEMAS] No se pudo investigar "
                f"{titulo}: {error}"
            )

        time.sleep(0.15)

    # Si no hay temas populares disponibles,
    # utilizar el banco de respaldo.
    disponibles = [
        tema for tema in TEMAS_RESPALDO
        if not tema_ya_usado(tema, historial)
    ]

    if disponibles:

        random.shuffle(disponibles)

        for titulo in disponibles:

            try:

                articulo = investigar_articulo(titulo)

                if articulo:
                    print(
                        f"[TEMAS] Tema de respaldo: "
                        f"{articulo['titulo']}"
                    )
                    return articulo

            except Exception:
                continue

    # Si todos los temas están usados, reiniciar
    # únicamente el historial de selección.
    print(
        "[TEMAS] Se agotaron los temas disponibles. "
        "Reiniciando historial."
    )

    guardar_historial([])

    for titulo in TEMAS_RESPALDO:

        try:

            articulo = investigar_articulo(titulo)

            if articulo:
                return articulo

        except Exception:
            continue

    raise RuntimeError(
        "No fue posible encontrar un tema ni consultar "
        "una fuente de información."
    )


# ==========================================================
# CONSTRUCCIÓN DEL GUION
# ==========================================================

def limpiar_texto(texto):

    texto = re.sub(
        r"\[\d+\]",
        "",
        texto
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


def separar_oraciones(texto):

    texto = limpiar_texto(texto)

    oraciones = re.split(
        r"(?<=[.!?])\s+",
        texto
    )

    return [
        o.strip()
        for o in oraciones
        if len(o.strip()) > 35
    ]


def construir_guion(articulo):

    titulo = articulo["titulo"]

    extracto = articulo["extracto"]

    fuente = articulo["url"]

    oraciones = separar_oraciones(extracto)

    if len(oraciones) < 3:
        raise ValueError(
            "El artículo no contiene suficiente información."
        )

    # Se utilizan oraciones del artículo como base
    # para reducir la invención de datos.
    seleccionadas = oraciones[:8]

    desarrollo = " ".join(seleccionadas[:6])

    revelacion = (
        "Y esto es solamente una parte de lo que "
        "se conoce sobre este tema. "
        "La información sigue siendo objeto de estudio."
    )

    gancho = (
        f"¿Sabías que existe algo llamado {titulo}? "
        "Lo que hay detrás de este tema es mucho "
        "más interesante de lo que parece."
    )

    cierre = (
        "¿Ya conocías este tema? "
        "Cuéntame qué fue lo que más te sorprendió "
        "y comparte este video."
    )

    escenas = [
        {
            "numero": 1,
            "duracion": 7,
            "tipo": "gancho",
            "narracion": gancho
        },
        {
            "numero": 2,
            "duracion": 43,
            "tipo": "investigacion",
            "narracion": desarrollo
        },
        {
            "numero": 3,
            "duracion": 10,
            "tipo": "revelacion_y_cierre",
            "narracion": (
                revelacion + " " + cierre
            )
        }
    ]

    descripcion = (
        f"{titulo}\n\n"
        "Descubre este tema con FORTALEZA MEDIA AI.\n\n"
        f"Fuente informativa: {fuente}\n\n"
        "Contenido elaborado a partir de información "
        "documental. Consulta la fuente para conocer "
        "el contexto completo."
    )

    return {
        "titulo": titulo,
        "formato": "YouTube Shorts",
        "duracion": DURACION,
        "idioma": IDIOMA,
        "estilo": (
            "documental, misterio, divulgación, "
            "suspenso y curiosidades"
        ),
        "fuente": fuente,
        "escenas": escenas,
        "descripcion": descripcion,
        "hashtags": [
            "#Shorts",
            "#Curiosidades",
            "#AprendeEnTikTok",
            "#Ciencia",
            "#Documental",
            "#FORTALEZAMEDIA"
        ],
        "creado": datetime.now(
            timezone.utc
        ).isoformat()
    }


# ==========================================================
# GUARDAR GUION E HISTORIAL
# ==========================================================

def guardar_guion(tema=None):

    # Permite conservar la compatibilidad con main.py.
    # Si se indica un tema manual, se investiga ese tema.
    if tema and normalizar(tema) not in (
        "aleatorio",
        "automatico",
        "misterios del oceano"
    ):

        articulo = investigar_articulo(tema)

        if not articulo:
            raise RuntimeError(
                f"No se pudo investigar el tema: {tema}"
            )

    else:

        articulo = seleccionar_tema()

    guion = construir_guion(articulo)

    ARCHIVO_GUION.write_text(
        json.dumps(
            guion,
            ensure_ascii=False,
            indent=4
        ),
        encoding="utf-8"
    )

    historial = cargar_historial()

    historial.append({
        "titulo": articulo["titulo"],
        "fecha": datetime.now(
            timezone.utc
        ).isoformat(),
        "fuente": articulo["url"]
    })

    guardar_historial(historial)

    print(
        "[GUION] Guion generado correctamente: "
        + guion["titulo"]
    )

    return guion


# ==========================================================
# PRUEBA DIRECTA
# ==========================================================

if __name__ == "__main__":

    print("=" * 55)
    print("FORTALEZA MEDIA AI — VIDEO ENGINE 4.0")
    print("=" * 55)

    resultado = guardar_guion()

    print("\nTÍTULO:")
    print(resultado["titulo"])

    print("\nESCENAS:")

    for escena in resultado["escenas"]:

        print(
            f"\n{escena['numero']}. "
            f"{escena['tipo'].upper()}"
        )

        print(escena["narracion"])

    print("\nGUION GUARDADO EN guion.json")
