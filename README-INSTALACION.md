
# FORTALEZA MEDIA AI

Sistema automatizado para crear, renderizar y publicar YouTube Shorts con inteligencia artificial.

## 1. Características

- Historias originales en español mexicano.
- Series de hasta 5 episodios.
- Ganchos fuertes al inicio y giros al final.
- Cuatro estilos visuales alternados:
  - Minecraft Parkour.
  - Videos satisfactorios.
  - Roblox Obby.
  - Cinematográfico.
- Narración con voces mexicanas de Edge TTS.
- Videos verticales 1080x1920.
- 30 FPS.
- Subtítulos automáticos.
- Renderizado con FFmpeg.
- Historial de temas y fondos utilizados.
- Generación automática mediante GitHub Actions.
- Publicación pública en YouTube mediante Cloudflare Worker.

## 2. Archivos principales

- `main.py`: inicia la generación.
- `video_engine.py`: crea las historias y administra los estilos.
- `render_short.py`: genera el video.
- `requirements.txt`: dependencias de Python.
- `worker.js`: autorización y publicación en YouTube.
- `wrangler.toml`: configuración del Worker.
- `.github/workflows/daily.yml`: automatización.

## 3. Secretos de GitHub

Entra al repositorio y abre:

Settings > Secrets and variables > Actions

Agrega estos secretos:

- `GROQ_API_KEY`
- `PIXABAY_API_KEY`
- `FORTALEZA_UPLOAD_KEY`

No publiques ni compartas los valores de estos secretos.

## 4. Configuración de Cloudflare

En el Worker `fortaleza-youtube-auth`, configura estas variables secretas:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `FORTALEZA_UPLOAD_KEY`

El valor de `FORTALEZA_UPLOAD_KEY` debe coincidir con el secreto de GitHub.

También debe estar configurado el espacio KV:

`YOUTUBE_TOKENS`

El archivo `wrangler.toml` contiene el identificador del espacio KV.

## 5. Autorización de YouTube

La dirección de autorización es:

https://fortaleza-youtube-auth.z44d2z597w.workers.dev/login

Antes de autorizar, registra esta URI de redirección en Google Cloud:

https://fortaleza-youtube-auth.z44d2z597w.workers.dev/callback

El proyecto de Google debe tener habilitada la API de YouTube Data API v3 y el acceso OAuth correspondiente.

## 6. Generación automática

El flujo de GitHub Actions ejecuta el sistema diariamente a las 9:00 a. m. (hora de San Luis Potosí).

Para ejecutarlo manualmente:

1. Abre la pestaña Actions.
2. Selecciona FORTALEZA MEDIA AI - SHORTS AUTOMATICOS.
3. Presiona Run workflow.
4. Ejecuta el proceso.

La opción de publicación está activada por defecto.

## 7. Publicación en YouTube

La publicación utiliza el Worker de Cloudflare.

El sistema envía:

- Video MP4.
- Título.
- Descripción.
- Clave privada de autorización.

El Worker solicita un token de acceso a Google y envía el video a YouTube con privacidad pública.

La publicación depende de que OAuth, Cloudflare y YouTube estén correctamente configurados.

## 8. Formato de salida

- Resolución: 1080 x 1920.
- Orientación: vertical 9:16.
- FPS: 30.
- Formato: MP4.
- Códec de video: H.264.
- Audio: AAC.
- Duración máxima del sistema: 178 segundos.

## 9. Importante

Los fondos de Pixabay dependen de los resultados disponibles en su catálogo. Las búsquedas no garantizan que todos los clips sean gameplay auténtico de Minecraft o Roblox.

La inteligencia artificial puede producir resultados variables. Se recomienda revisar las primeras ejecuciones y comprobar que el video, el audio y los subtítulos estén correctos.

No compartas claves API, tokens OAuth ni credenciales privadas.
