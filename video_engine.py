
import json
from datetime import datetime, date

TEMAS = [
    {
        "titulo": "El lugar más profundo de todos los océanos",
        "gancho": "Existe un lugar en nuestro planeta tan profundo que la luz del Sol jamás llega hasta el fondo.",
        "desarrollo": "Se llama fosa de las Marianas y alcanza casi once mil metros de profundidad. La presión ahí abajo es brutal: mucho mayor que la que soportamos en la superficie. Y aun en esas condiciones extremas, los científicos han encontrado formas de vida capaces de sobrevivir. Lo increíble es que todavía conocemos muy poco de ese mundo.",
        "revelacion": "Piensa en esto: hemos explorado más el espacio que algunas de las regiones más profundas de nuestro propio océano.",
        "cierre": "¿Te atreverías a bajar hasta ese lugar si pudieras regresar sano y salvo? Te leo en los comentarios."
    },
    {
        "titulo": "El animal que tiene tres corazones",
        "gancho": "Hay un animal marino que tiene tres corazones y sangre azul. Y no, no es una criatura de ciencia ficción.",
        "desarrollo": "Es el pulpo. Dos de sus corazones bombean sangre hacia las branquias y el tercero la distribuye por el resto del cuerpo. Su sangre es azul porque utiliza una proteína llamada hemocianina, que contiene cobre. Pero eso no es todo: también puede cambiar de color y textura para camuflarse.",
        "revelacion": "Y hay algo todavía más sorprendente: sus brazos pueden realizar movimientos complejos gracias a su extraordinario sistema nervioso.",
        "cierre": "¿Ya conocías estos secretos del pulpo? Comenta cuál te sorprendió más."
    },
    {
        "titulo": "El océano que brilla en la oscuridad",
        "gancho": "Imagina mirar el mar de noche y descubrir que las olas brillan como si tuvieran miles de estrellas.",
        "desarrollo": "Este fenómeno existe y se conoce como bioluminiscencia. Algunos organismos marinos producen luz mediante reacciones químicas dentro de su cuerpo. En ciertas playas, millones de diminutos organismos pueden iluminar el agua cuando las olas los agitan. Parece magia, pero es un fenómeno natural.",
        "revelacion": "Para algunas criaturas, producir luz sirve para atraer alimento, confundir depredadores o comunicarse en la oscuridad.",
        "cierre": "¿Visitarías una playa que brilla durante la noche? Cuéntamelo en los comentarios."
    },
    {
        "titulo": "El tiburón que puede vivir durante siglos",
        "gancho": "Existe un tiburón que podría vivir más de cuatrocientos años. Algunos ejemplares nacieron antes de que existieran muchas cosas que hoy consideramos normales.",
        "desarrollo": "Es el tiburón de Groenlandia. Vive en aguas extremadamente frías y crece muy lentamente. Los estudios científicos han estimado que algunos ejemplares pueden alcanzar varios siglos de vida. Su crecimiento lento y su adaptación al frío lo convierten en uno de los vertebrados más longevos conocidos.",
        "revelacion": "Eso significa que algunos de estos animales podrían haber estado nadando en el océano durante generaciones enteras de seres humanos.",
        "cierre": "¿Qué crees que ha visto un animal que lleva siglos viviendo? Te leo."
    },
    {
        "titulo": "El sonido misterioso del océano",
        "gancho": "En el océano se han registrado sonidos tan extraños que durante años despertaron todo tipo de teorías.",
        "desarrollo": "Uno de los casos más conocidos fue el sonido llamado Bloop, registrado en 1997 por sistemas de monitoreo submarino. Su enorme intensidad hizo que muchas personas imaginaran criaturas gigantes. Sin embargo, investigaciones posteriores apuntaron a que probablemente fue producido por hielo fracturándose.",
        "revelacion": "Lo fascinante es que el océano puede transportar sonidos a distancias enormes, y todavía hay mucho que aprender sobre sus paisajes acústicos.",
        "cierre": "¿Qué sonido del océano te gustaría escuchar? Escribe tu respuesta."
    },
    {
        "titulo": "La criatura transparente del océano",
        "gancho": "En las profundidades del mar existen animales tan transparentes que parecen desaparecer frente a tus ojos.",
        "desarrollo": "Algunas especies marinas tienen cuerpos casi transparentes. Esta característica puede ayudarles a pasar desapercibidas en un entorno donde esconderse es cuestión de supervivencia. Hay peces, medusas y otros organismos que parecen hechos de cristal, aunque cada uno tiene adaptaciones diferentes.",
        "revelacion": "En un mundo donde la luz escasea y los depredadores acechan, ser casi invisible puede convertirse en una ventaja extraordinaria.",
        "cierre": "¿Cuál de estas criaturas te gustaría ver en persona? Déjalo en los comentarios."
    },
    {
        "titulo": "El animal que regenera partes de su cuerpo",
        "gancho": "Hay animales capaces de recuperar partes de su cuerpo después de perderlas. Algunos parecen tener una habilidad extraordinaria para repararse.",
        "desarrollo": "Las estrellas de mar son conocidas por su capacidad de regeneración. Dependiendo de la especie y de las condiciones, pueden reconstruir brazos perdidos. En ciertos casos, un fragmento que conserve parte del disco central puede llegar a desarrollar un nuevo individuo.",
        "revelacion": "No significa que cualquier pedazo pueda convertirse en una estrella completa: su capacidad depende de la especie y de qué parte del cuerpo se haya perdido.",
        "cierre": "¿Conocías esta capacidad de las estrellas de mar? Comparte el dato con alguien."
    }
]


def seleccionar_tema():
    dia = date.today().toordinal()
    return TEMAS[dia % len(TEMAS)]


def crear_guion(tema=None):
    if tema is None or tema.strip().lower() in (
        "misterios del océano",
        "misterios del oceano",
        "aleatorio",
        "automático",
        "automatico"
    ):
        contenido = seleccionar_tema()
    else:
        contenido = next(
            (t for t in TEMAS if t["titulo"].lower() == tema.strip().lower()),
            None
        )

        if contenido is None:
            contenido = {
                "titulo": tema.strip(),
                "gancho": f"Hay algo sobre {tema.strip()} que merece toda tu atención.",
                "desarrollo": f"Hoy vamos a descubrir algunos aspectos interesantes de {tema.strip()}. Lo importante es separar los datos comprobables de las ideas que todavía no tienen una explicación definitiva.",
                "revelacion": f"Y lo más interesante de {tema.strip()} es que todavía hay preguntas que vale la pena investigar.",
                "cierre": "¿Qué opinas? Escribe tu respuesta en los comentarios."
            }

    escenas = [
        {
            "numero": 1,
            "duracion": 5,
            "tipo": "gancho",
            "narracion": contenido["gancho"]
        },
        {
            "numero": 2,
            "duracion": 40,
            "tipo": "desarrollo",
            "narracion": contenido["desarrollo"]
        },
        {
            "numero": 3,
            "duracion": 15,
            "tipo": "revelacion_y_cierre",
            "narracion": (
                contenido["revelacion"] + " " + contenido["cierre"]
            )
        }
    ]

    return {
        "titulo": contenido["titulo"],
        "formato": "YouTube Shorts",
        "duracion": 60,
        "idioma": "es-MX",
        "estilo": "misterio, suspenso y divulgación",
        "escenas": escenas,
        "descripcion": (
            contenido["titulo"]
            + " ¿Conocías este dato? Comenta tu opinión y comparte el video."
        ),
        "hashtags": [
            "#Shorts",
            "#Curiosidades",
            "#Misterios",
            "#Ciencia",
            "#FORTALEZAMEDIA"
        ],
        "creado": datetime.now().isoformat()
    }


def guardar_guion(tema=None):
    guion = crear_guion(tema)

    with open("guion.json", "w", encoding="utf-8") as archivo:
        json.dump(
            guion,
            archivo,
            ensure_ascii=False,
            indent=4
        )

    return guion
