import json
from datetime import datetime

def crear_guion(tema):
    return {
        "titulo": tema,
        "formato": "YouTube Shorts",
        "duracion": 60,
        "idioma": "es-MX",
        "escenas": [
            {
                "numero": 1,
                "duracion": 5,
                "tipo": "gancho",
                "narracion": f"Hoy descubrirás algo sorprendente sobre {tema}."
            },
            {
                "numero": 2,
                "duracion": 40,
                "tipo": "desarrollo",
                "narracion": f"Vamos a conocer los detalles más interesantes sobre {tema}."
            },
            {
                "numero": 3,
                "duracion": 15,
                "tipo": "cierre",
                "narracion": "Síguenos para descubrir más contenido."
            }
        ],
        "creado": datetime.now().isoformat()
    }


def guardar_guion(tema):
    guion = crear_guion(tema)

    with open("guion.json", "w", encoding="utf-8") as archivo:
        json.dump(guion, archivo, ensure_ascii=False, indent=4)

    return guion