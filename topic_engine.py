
import json
import random
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests


HISTORIAL = Path("historial_temas.json")

API_TOP = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top"

API_RESUMEN = (
    "https://es.wikipedia.org/api/rest_v1/page/summary/"
)

CABECERAS = {
    "User-Agent": "FORTALEZA-MEDIA-AI/4.0 (automated educational video)"
}

CATEGORIAS = [
    "ciencia",
    "historia",
    "naturaleza",
    "animales",
    "espacio",
    "tecnologia",
    "geografia",
    "misterios"
]


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split())


def cargar_historial():
    if not HISTORIAL.exists():
        return []

    try:
        with open(HISTORIAL, encoding="utf-8") as archivo:
            datos = json.load(archivo)

        return datos if isinstance(datos, list) else []

    except Exception:
        return []


def guardar_historial(historial):
    with open(HISTORIAL, "w", encoding="utf-8") as archivo:
        json.dump(
            historial[-500:],
            archivo,
            ensure_ascii=False,
            indent=2
        )


def obtener_articulos_populares():
    ahora = datetime.now(timezone.utc)

    for dias_atras in range(2, 6):
        fecha = ahora - timedelta(days=dias_atras)

        url = (
            f"{API_TOP}/es.wikipedia/all-access/"
            f"{fecha.year}/{fecha.month:02d}/{fecha.day:02d}"
        )

        try:
            respuesta = requests.get(
                url,
                headers=CABECERAS,
                timeout=25
            )
            respuesta.raise_for_status()

            datos = respuesta.json()

            articulos = (
                datos.get("items", [{}])[0].get("articles", [])
            )

            if articulos:
                return [
                    articulo["article"]
                    for articulo in articulos
                    if articulo.get("article")
                ]

        except Exception as error:
            print("No se pudo consultar tendencias:", error)

    return []


def obtener_resumen(titulo):
    url = API_RESUMEN + quote(titulo, safe="")

    respuesta = requests.get(
        url,
        headers=CABECERAS,
        timeout=25
    )

    respuesta.raise_for_status()

    datos = respuesta.json()

    resumen = datos.get("extract", "").strip()
    enlace = datos.get("content_urls", {}).get(
        "desktop", {}
    ).get("page", "")

    if len(resumen) < 250:
        return None

    return {
        "titulo": datos.get("title", titulo),
        "resumen": resumen,
        "url": enlace
    }


def articulo_valido(titulo):
    titulo = titulo.strip()

    bloqueados = (
        "special:",
        "wikipedia:",
        "archivo:",
        "categoría:",
        "discusión:",
        "usuario:",
        "plantilla:",
        "portal:",
        "anexo:"
    )

    if len(titulo) < 4 or titulo.lower().startswith(bloqueados):
        return False

    if titulo.lower() in ("main page", "portada"):
        return False

    return True


def separar_oraciones(texto):
    texto = re.sub(r"\[\d+\]", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    oraciones = re.split(
        r"(?<=[.!?])\s+",
        texto
    )

    return [
        o.strip()
        for o in oraciones
        if len(o.strip()) > 35
    ]


def construir_guion(datos):
    titulo = datos["titulo"]
    oraciones = separar_oraciones(datos["resumen"])

    if len(oraciones) < 3:
        raise ValueError("Información insuficiente para crear el guion.")

    escenas = []

    escenas.append({
        "numero": 1,
        "tipo": "gancho",
        "narracion": (
            f"Hay algo que debes conocer sobre {titulo}. "
            f"{oraciones[0]}"
        )
    })

    escenas.append({
        "numero": 2,
        "tipo": "contexto",
        "narracion": " ".join(oraciones[1:3])
    })

    escenas.append({
        "numero": 3,
        "tipo": "desarrollo",
        "narracion": " ".join(oraciones[3:5])
        if len(oraciones) > 3 else oraciones[-1]
    })

    escenas.append({
        "numero": 4,
        "tipo": "cierre",
        "narracion": (
            "Esto es parte de lo que conocemos hasta ahora. "
            "¿Qué dato te sorprendió más? "
            "Te leo en los comentarios."
        )
    })

    return {
        "titulo": titulo,
        "formato": "Pendiente de decisión inteligente",
        "idioma": "es-MX",
        "estilo": "documental dinámico",
        "categoria": "descubrimiento",
        "escenas": escenas,
        "descripcion": (
            f"Descubre más sobre {titulo}. "
            "Información y contexto para seguir aprendiendo."
        ),
        "fuente_informacion": datos["url"],
        "creado": datetime.now().isoformat()
    }


def descubrir_tema():
    historial = cargar_historial()

    utilizados = {
        normalizar(item.get("tema", ""))
        for item in historial
    }

    articulos = obtener_articulos_populares()

    if not articulos:
        raise RuntimeError(
            "No se pudieron consultar temas nuevos. "
            "Se cancela la producción para no repetir contenido."
        )

    candidatos = [
        titulo for titulo in articulos[:100]
        if articulo_valido(titulo)
        and normalizar(titulo) not in utilizados
    ]

    random.shuffle(candidatos)

    for titulo in candidatos:
        try:
            datos = obtener_resumen(titulo)

            if not datos:
                continue

            guion = construir_guion(datos)

            historial.append({
                "tema": datos["titulo"],
                "fecha": datetime.now().isoformat(),
                "fuente": datos["url"]
            })

            guardar_historial(historial)

            print("Tema nuevo seleccionado:", datos["titulo"])

            return guion

        except Exception as error:
            print("Tema omitido:", titulo, error)

    raise RuntimeError(
        "No se encontró un tema nuevo con información suficiente."
    )
