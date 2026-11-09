import json
import random
import re
import requests

from datetime import datetime, timedelta, timezone
from pathlib import Path


# ==========================================================
# FORTALEZA MEDIA AI 6.0
# MOTOR EDITORIAL INTELIGENTE — HISTORIAS DE ALTO IMPACTO
# ==========================================================

VERSION = "6.0"

IDIOMA = "es-MX"

ARCHIVO_GUION = Path("guion.json")
ARCHIVO_HISTORIAL = Path("historial_temas.json")

URL_PAGEVIEWS = (
    "https://wikimedia.org/api/rest_v1/"
    "metrics/pageviews/top/es.wikipedia/all-access/user"
)

URL_WIKIPEDIA = "https://es.wikipedia.org/w/api.php"

CABECERAS = {
    "User-Agent": "FORTALEZA-MEDIA-AI/6.0"
}

MAX_HISTORIAL = 300
MAX_CARACTERES_INVESTIGACION = 12000

# ----------------------------------------------------------
# TEMAS DE RESPALDO — se usan si las tendencias fallan
# o si todos los temas populares ya se utilizaron.
# ----------------------------------------------------------
TEMAS_RESPALDO = [
    "Fosa de las Marianas",
    "Bioluminiscencia",
    "Tiburón de Groenlandia",
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
    "Telescopio espacial James Webb",
    "Inteligencia artificial",
    "ADN",
    "Abejas",
    "Arañas",
    "Tornados",
    "Terremotos",
    "Tsunamis",
    "Pirámides de Egipto",
    "Machu Picchu",
    "Stonehenge",
    "Imperio romano",
    "Antiguo Egipto",
    "Civilización maya",
    "Imperio azteca",
    "Vikingos",
    "Ruta de la Seda",
    "Biblioteca de Alejandría",
    "Atlántida",
    "Titanic",
    "Año bisiesto",
    "Pompeya",
    "Selva amazónica",
    "Desierto del Sahara",
    "Luz",
    "Gravedad",
]

# ----------------------------------------------------------
# TEMAS QUE NO ENCAJAN CON UN CANAL DOCUMENTAL
# (deportes, farándula, política del día).
# ----------------------------------------------------------
TEMAS_PROHIBIDOS = {
    "fútbol", "futbol", "liga", "real madrid", "barcelona",
    "champions", "nba", "nfl", "béisbol", "beisbol",
    "telenovela", "actor", "actriz", "cantante", "influencer",
    "elecciones", "presidente", "partido político",
    "miss universo", "reality show", "gran hermano",
    "kardashian", "bts", "taylor swift", "bad bunny",
}

# ----------------------------------------------------------
# PALABRAS QUE SUGIEREN CONTENIDO DE IMPACTO
# ----------------------------------------------------------
PALABRAS_INTERESANTES = {
    "sorprendente", "único", "unico", "récord", "record",
    "nunca", "jamás", "jamas", "imposible", "misterio",
    "descubrimiento", "científicos", "cientificos",
    "investigación", "investigacion", "milagro",
    "extraordinario", "raro", "extraño", "extrano",
    "fenómeno", "fenomeno", "secreto", "revelador",
    "asombroso", "impactante", "increíble", "increible",
    "oculto", "prohibido", "olvidado", "desapareció",
    "desaparecio", "sobrevivió", "sobrevivio", "cambió",
    "cambio", "revolucionó", "revoluciono",
}

# ----------------------------------------------------------
# FRASES EDITORIALES
# ----------------------------------------------------------

FRASES_GANCHO = [
    "¿Sabías que {titulo} esconde un detalle que casi nadie conoce?",
    "Esto parece imposible, pero es real: lo que descubrieron sobre {titulo} cambió todo.",
    "Hay algo sobre {titulo} que la mayoría de las personas nunca ha escuchado.",
    "Existe un dato sobre {titulo} que, una vez que lo conoces, no puedes dejar de pensar en él.",
    "Prepárate, porque lo que vamos a contar sobre {titulo} no es lo que parece.",
    "A primera vista {titulo} parece normal. Pero hay algo detrás que lo cambia todo.",
    "Lo que estás a punto de escuchar sobre {titulo} ha sorprendido incluso a los expertos.",
]

FRASES_TRANSICION = [
    "Pero aquí es donde la historia se vuelve todavía más interesante.",
    "Y eso nos lleva a una pregunta importante.",
    "Sin embargo, hay otro detalle que merece atención.",
    "Lo interesante es que este fenómeno tiene más de una explicación.",
    "Para comprenderlo, hay que observar lo que ocurre detrás.",
    "Y precisamente ahí aparece uno de los datos más importantes.",
    "Esto se conecta directamente con algo aún más fascinante.",
    "Y lo que viene después explica muchas cosas.",
]

FRASES_REVELACION = [
    "Y esto es lo que cambia toda la historia.",
    "Aquí es donde aparece el dato más sorprendente.",
    "Pero el detalle más impactante es el siguiente.",
    "Y lo que vamos a revelar ahora no es para nada lo que se imaginaban.",
]

FRASES_CIERRE = [
    "Y aunque sabemos mucho sobre este tema, todavía quedan preguntas por responder.",
    "Este es un recordatorio de cuánto nos falta por descubrir.",
    "La realidad demuestra que el mundo todavía guarda historias extraordinarias.",
    "Historias como esta nos recuerdan por qué vale la pena seguir investigando.",
]

PREGUNTAS_CTA = [
    "¿Qué parte de esta historia te sorprendió más? Cuéntamelo en los comentarios.",
    "¿Ya conocías este dato? Comparte tu opinión abajo.",
    "Si te gustó esta historia, sígueme para más contenido como este.",
    "¿Quieres saber más sobre este tema? Déjamelo saber en los comentarios.",
    "Comparte este video con alguien a quien le pueda interesar.",
]


# ==========================================================
# CONEXIÓN HTTP
# ==========================================================

def obtener_json(url, parametros=None, timeout=25):
    respuesta = requests.get(
        url,
        params=parametros,
        headers=CABECERAS,
        timeout=timeout,
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
        with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as archivo:
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
    with open(temporal, "w", encoding="utf-8") as archivo:
        json.dump(historial, archivo, ensure_ascii=False, indent=4)
    temporal.replace(ARCHIVO_HISTORIAL)


def tema_ya_utilizado(titulo, historial):
    normalizado = titulo.strip().lower()
    for elemento in historial:
        if isinstance(elemento, dict):
            anterior = str(elemento.get("titulo", "")).strip().lower()
        else:
            anterior = str(elemento).strip().lower()
        if anterior == normalizado:
            return True
    return False


# ==========================================================
# DETECCIÓN DE TEMAS POPULARES
# ==========================================================

def obtener_fecha_pageviews():
    ayer = datetime.now(timezone.utc).date() - timedelta(days=1)
    return ayer.strftime("%Y/%m/%d")


def limpiar_titulo(titulo):
    titulo = str(titulo).replace("_", " ")
    titulo = re.sub(
        r"\s*\([^)]*desambiguación[^)]*\)",
        "",
        titulo,
        flags=re.IGNORECASE,
    )
    return titulo.strip()


def titulo_valido(titulo):
    titulo = limpiar_titulo(titulo)

    if len(titulo) < 5:
        return False

    prohibidas = [
        "portada", "wikipedia:", "especial:", "archivo:",
        "categoría:", "discusión:", "anexo:", "plantilla:",
        "usuario:", "ayuda:", "fecha",
    ]
    bajo = titulo.lower()
    if any(palabra in bajo for palabra in prohibidas):
        return False

    if re.fullmatch(r"\d{1,4}", titulo):
        return False

    if re.fullmatch(r"\d{1,2}\s+de\s+\w+", bajo):
        return False

    return True


def tema_prohibido(titulo):
    bajo = titulo.lower()
    return any(p in bajo for p in TEMAS_PROHIBIDOS)


def descubrir_temas():
    fecha = obtener_fecha_pageviews()
    url = f"{URL_PAGEVIEWS}/{fecha}"
    print("[TENDENCIAS] Consultando temas populares...")

    try:
        datos = obtener_json(url)
        articulos = datos.get("items", [{}])[0].get("articles", [])
        articulos = sorted(
            articulos,
            key=lambda x: x.get("views", 0),
            reverse=True,
        )
        resultado = []
        for articulo in articulos:
            titulo = limpiar_titulo(articulo.get("article", ""))
            if not titulo_valido(titulo):
                continue
            resultado.append({
                "titulo": titulo,
                "visitas": articulo.get("views", 0),
            })
            if len(resultado) >= 60:
                break
        print("[TENDENCIAS] Temas encontrados:", len(resultado))
        return resultado
    except Exception as error:
        print("[TENDENCIAS] No se pudo consultar:", error)
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
        datos = obtener_json(URL_WIKIPEDIA, parametros)
        paginas = datos.get("query", {}).get("pages", {})
        for pagina in paginas.values():
            extracto = pagina.get("extract", "")
            extracto = limpiar_texto(extracto)
            if len(extracto) < 600:
                return None
            return {
                "titulo": pagina.get("title", titulo),
                "texto": extracto[:MAX_CARACTERES_INVESTIGACION],
                "url": (
                    "https://es.wikipedia.org/wiki/"
                    + pagina.get("title", titulo).replace(" ", "_")
                ),
            }
    except Exception as error:
        print("[INVESTIGACIÓN] Error:", error)
    return None


def limpiar_texto(texto):
    texto = re.sub(r"\[\d+\]", "", str(texto))
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


# ==========================================================
# SELECCIÓN AUTOMÁTICA DEL TEMA
# ==========================================================

def seleccionar_tema():
    historial = cargar_historial()
    tendencias = descubrir_temas()

    candidatos = []
    for elemento in tendencias:
        titulo = elemento["titulo"]
        if tema_ya_utilizado(titulo, historial):
            continue
        if tema_prohibido(titulo):
            continue
        candidatos.append(titulo)

    random.shuffle(candidatos)

    for titulo in candidatos[:25]:
        investigacion = investigar_tema(titulo)
        if investigacion:
            print("[TEMA SELECCIONADO]", investigacion["titulo"])
            return investigacion

    # Respaldo editorial.
    respaldo = [
        tema for tema in TEMAS_RESPALDO
        if not tema_ya_utilizado(tema, historial)
    ]
    random.shuffle(respaldo)

    for titulo in respaldo:
        investigacion = investigar_tema(titulo)
        if investigacion:
            print("[TEMA RESPALDO]", investigacion["titulo"])
            return investigacion

    # Si todos los temas se han utilizado, reinicia ciclo.
    print("[HISTORIAL] Reiniciando ciclo de temas.")
    guardar_historial([])

    for titulo in TEMAS_RESPALDO:
        investigacion = investigar_tema(titulo)
        if investigacion:
            return investigacion

    raise RuntimeError("No se pudo encontrar un tema investigable.")


# ==========================================================
# ANÁLISIS DEL CONTENIDO
# ==========================================================

def dividir_oraciones(texto):
    texto = limpiar_texto(texto)
    oraciones = re.split(r"(?<=[.!?])\s+", texto)
    return [
        oracion.strip()
        for oracion in oraciones
        if len(oracion.strip()) > 35
    ]


def dividir_en_bloques(oraciones, cantidad):
    if not oraciones:
        return []
    cantidad = max(1, min(cantidad, len(oraciones)))
    bloques = [[] for _ in range(cantidad)]
    for indice, oracion in enumerate(oraciones):
        posicion = min(
            cantidad - 1,
            int(indice * cantidad / len(oraciones)),
        )
        bloques[posicion].append(oracion)
    return [" ".join(bloque) for bloque in bloques if bloque]


def contar_palabras(texto):
    return len(
        re.findall(r"\b[\wáéíóúñÁÉÍÓÚÑ]+\b", texto)
    )


def puntuar_oracion(oracion):
    texto = oracion.lower()
    puntos = 0
    for palabra in PALABRAS_INTERESANTES:
        if palabra in texto:
            puntos += 1
    if any(c.isdigit() for c in oracion):
        puntos += 1
    for marca in ("año", "años", "siglo", "miles", "millones"):
        if marca in texto:
            puntos += 1
            break
    return puntos


def seleccionar_oraciones_utiles(texto, cantidad):
    """Devuelve las mejores oraciones conservando el orden narrativo."""
    oraciones = dividir_oraciones(texto)
    if len(oraciones) <= cantidad:
        return oraciones

    # Primero tomamos las más relevantes.
    con_indice = [
        (i, o, puntuar_oracion(o))
        for i, o in enumerate(oraciones[:40])
    ]
    top = sorted(con_indice, key=lambda x: -x[2])[:cantidad]
    top.sort(key=lambda x: x[0])
    return [o for _, o, _ in top]


# ==========================================================
# CONSTRUCCIÓN DE SHORTS — 5 ESCENAS
# ==========================================================

def crear_guion_short(investigacion):
    titulo = investigacion["titulo"]
    oraciones = seleccionar_oraciones_utiles(
        investigacion["texto"], 9,
    )

    if len(oraciones) < 4:
        raise RuntimeError(
            "No hay información suficiente para el guion."
        )

    gancho = random.choice(FRASES_GANCHO).format(titulo=titulo)

    if len(oraciones) >= 9:
        contexto = " ".join(oraciones[:3])
        desarrollo = " ".join(oraciones[3:6])
        revelacion = " ".join(oraciones[6:9])
    elif len(oraciones) >= 6:
        contexto = " ".join(oraciones[:2])
        desarrollo = " ".join(oraciones[2:4])
        revelacion = " ".join(oraciones[4:])
    else:
        contexto = oraciones[0]
        desarrollo = " ".join(oraciones[1:3])
        revelacion = " ".join(oraciones[3:]) or contexto

    trans_d = random.choice(FRASES_TRANSICION)
    trans_r = random.choice(FRASES_REVELACION)
    cierre = random.choice(FRASES_CIERRE)
    cta = random.choice(PREGUNTAS_CTA)

    escenas = [
        {
            "numero": 1,
            "duracion": 8,
            "tipo": "gancho",
            "titulo": titulo,
            "narracion": gancho,
        },
        {
            "numero": 2,
            "duracion": 12,
            "tipo": "contexto",
            "titulo": "El contexto",
            "narracion": contexto,
        },
        {
            "numero": 3,
            "duracion": 12,
            "tipo": "desarrollo",
            "titulo": "Lo que casi nadie cuenta",
            "narracion": f"{trans_d} {desarrollo}",
        },
        {
            "numero": 4,
            "duracion": 12,
            "tipo": "revelacion",
            "titulo": "El dato que lo cambia todo",
            "narracion": f"{trans_r} {revelacion}",
        },
        {
            "numero": 5,
            "duracion": 12,
            "tipo": "cierre",
            "titulo": "Para cerrar",
            "narracion": f"{cierre} {cta}",
        },
    ]

    escenas = [
        e for e in escenas
        if str(e.get("narracion", "")).strip()
    ]

    if len(escenas) < 3:
        bloques = dividir_en_bloques(oraciones[:6], 3)
        escenas = [
            {
                "numero": i + 1,
                "duracion": 20,
                "tipo": "desarrollo",
                "titulo": t,
                "narracion": b,
            }
            for i, (t, b) in enumerate(
                zip(["Inicio", "Desarrollo", "Cierre"], bloques)
            )
        ]

    return {
        "formato": "vertical",
        "formato_legible": "YouTube Shorts 9:16",
        "duracion": 60,
        "escenas": escenas,
    }


# ==========================================================
# CONSTRUCCIÓN DE VIDEO HORIZONTAL — 9 ESCENAS
# ==========================================================

def crear_guion_largo(investigacion):
    titulo = investigacion["titulo"]
    oraciones = seleccionar_oraciones_utiles(
        investigacion["texto"], 18,
    )

    if len(oraciones) < 12:
        return None

    bloques = dividir_en_bloques(oraciones, 7)
    if len(bloques) < 5:
        return None

    gancho = random.choice(FRASES_GANCHO).format(titulo=titulo)

    titulos_desarrollo = [
        "El contexto",
        "Cómo empieza la historia",
        "Los primeros detalles",
        "Lo que sabemos",
        "Un descubrimiento clave",
        "Lo que casi nadie nota",
        "El panorama completo",
    ]

    escenas = [
        {
            "numero": 1,
            "duracion": 20,
            "tipo": "gancho",
            "titulo": titulo,
            "narracion": gancho,
        },
    ]

    for indice, bloque in enumerate(bloques):
        narracion = bloque
        if indice > 0:
            narracion = f"{random.choice(FRASES_TRANSICION)} {narracion}"
        escenas.append({
            "numero": indice + 2,
            "duracion": 30,
            "tipo": "desarrollo",
            "titulo": titulos_desarrollo[
                min(indice, len(titulos_desarrollo) - 1)
            ],
            "narracion": narracion,
        })

    escenas.append({
        "numero": len(escenas) + 1,
        "duracion": 25,
        "tipo": "revelacion",
        "titulo": "El dato que lo cambia todo",
        "narracion": (
            random.choice(FRASES_REVELACION)
            + " "
            + random.choice(FRASES_CIERRE)
        ),
    })

    escenas.append({
        "numero": len(escenas) + 1,
        "duracion": 20,
        "tipo": "cierre",
        "titulo": "Para cerrar",
        "narracion": (
            random.choice(FRASES_CIERRE)
            + " "
            + random.choice(PREGUNTAS_CTA)
        ),
    })

    palabras = sum(
        contar_palabras(e["narracion"]) for e in escenas
    )

    if palabras < 400:
        return None

    return {
        "formato": "horizontal",
        "formato_legible": "YouTube horizontal 16:9",
        "duracion": 240,
        "escenas": escenas,
    }


# ==========================================================
# DECISIÓN EDITORIAL
# ==========================================================

def decidir_formato(investigacion):
    historial = cargar_historial()
    oraciones = dividir_oraciones(investigacion["texto"])
    palabras = contar_palabras(investigacion["texto"])

    # Se alterna: 1 video largo por cada 3 Shorts.
    turno_largo = ((len(historial) + 1) % 3 == 0)

    if turno_largo and palabras >= 900 and len(oraciones) >= 14:
        guion = crear_guion_largo(investigacion)
        if guion:
            print("[EDITORIAL] Formato horizontal seleccionado.")
            return guion

    print("[EDITORIAL] Formato Shorts seleccionado.")
    return crear_guion_short(investigacion)


# ==========================================================
# CREACIÓN DEL GUION FINAL
# ==========================================================

def crear_guion(tema=None):
    if tema and tema.strip().lower() not in (
        "aleatorio", "automático", "automatico", "tendencias",
    ):
        investigacion = investigar_tema(tema.strip())
        if not investigacion:
            raise RuntimeError(
                "No se pudo investigar el tema solicitado."
            )
    else:
        investigacion = seleccionar_tema()

    contenido = decidir_formato(investigacion)

    titulo = investigacion["titulo"]
    escenas = [
        e for e in contenido["escenas"]
        if str(e.get("narracion", "")).strip()
    ]

    if not escenas:
        raise RuntimeError("El guion quedó sin escenas válidas.")

    palabras = sum(
        contar_palabras(e["narracion"]) for e in escenas
    )

    formato = contenido["formato"]
    formato_legible = contenido.get(
        "formato_legible", formato,
    )

    hashtags = [
        "#FORTALEZAMEDIA",
        "#Curiosidades",
        "#Ciencia",
        "#Conocimiento",
        "#Historias",
    ]

    if formato == "vertical":
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
        "formato_legible": formato_legible,
        "duracion": contenido["duracion"],
        "idioma": IDIOMA,
        "estilo": (
            "documental cinematográfico, divulgación, "
            "suspenso y narrativa dinámica"
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
    with open(temporal, "w", encoding="utf-8") as archivo:
        json.dump(guion, archivo, ensure_ascii=False, indent=4)
    temporal.replace(ARCHIVO_GUION)

    historial = cargar_historial()
    historial.append({
        "titulo": guion["titulo"],
        "formato": guion["formato"],
        "creado": guion["creado"],
    })
    guardar_historial(historial)

    print("=" * 55)
    print("FORTALEZA MEDIA AI 6.0")
    print("GUION GENERADO")
    print("Título:", guion["titulo"])
    print("Formato:", guion["formato_legible"])
    print("Escenas:", len(guion["escenas"]))
    print("Palabras:", guion["palabras"])
    print("=" * 55)

    return guion


if __name__ == "__main__":
    guardar_guion()