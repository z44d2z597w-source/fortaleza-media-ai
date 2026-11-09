from video_engine import guardar_guion

def iniciar_fortaleza():
    print("FORTALEZA MEDIA AI")
    print("Iniciando motor de contenido...")

    tema = "Misterios del océano"

    guion = guardar_guion(tema)

    print("Guion creado correctamente:")
    print(guion["titulo"])
    print("Escenas:", len(guion["escenas"]))

if __name__ == "__main__":
    iniciar_fortaleza()