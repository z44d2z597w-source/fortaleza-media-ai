# FORTALEZA MEDIA AI 2.0

Sistema automatizado para crear YouTube Shorts mediante inteligencia artificial.

## Características

- Generación de historias originales.
- Series de 5 episodios conectados.
- Guiones en español mexicano.
- Inteligencia artificial mediante Groq.
- Sistema de respaldo para generar guiones.
- Narración con Edge TTS.
- Voz mexicana.
- Fondos de video de Pixabay.
- Generación de imágenes con Pollinations.
- Escenas con movimiento mediante FFmpeg.
- Subtítulos automáticos.
- Formato vertical 1080x1920.
- Resolución de 30 FPS.
- Duración máxima de 178 segundos.
- Historial para evitar repetir fondos.
- Generación automática mediante GitHub Actions.

## Archivos principales

- main.py: inicia todo el proceso.
- video_engine.py: genera las historias.
- render_short.py: crea los videos.
- requirements.txt: dependencias.
- .github/workflows/daily.yml: automatización diaria.

## Configuración de secretos

En GitHub entra a:

Settings > Secrets and variables > Actions

Agrega:

GROQ_API_KEY
PIXABAY_API_KEY
FORTALEZA_UPLOAD_KEY

No compartas estos secretos públicamente.

## Servicios

Groq:
https://console.groq.com/

Pixabay:
https://pixabay.com/api/docs/

Pollinations:
https://pollinations.ai/

## Generación manual

1. Entra a la pestaña Actions.
2. Selecciona FORTALEZA MEDIA AI - SHORTS DIARIOS.
3. Presiona Run workflow.
4. Mantén la publicación desactivada.
5. Ejecuta el proceso.
6. Espera a que termine.
7. Descarga el artefacto del video.

## Publicación

La publicación automática todavía requiere configurar y verificar el Worker de YouTube.

No activar la publicación hasta comprobar que el video generado es correcto.

## Formato de salida

Resolución: 1080 x 1920.
FPS: 30.
Formato: MP4.
Códec: H.264.
Audio: AAC.
Duración máxima: 178 segundos.

## Importante

Los servicios externos pueden tener límites, cambios o interrupciones.
La generación de imágenes, videos y guiones depende de su disponibilidad.