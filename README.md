# CLIPPER — Creado por Ronny Montero

Aplicación web para subir un video desde Chrome, generar subtítulos automáticos y crear clips verticales 9:16.

## Publicación en Render
Este repositorio incluye `render.yaml` y `Dockerfile`. En Render, crea un Blueprint desde este repositorio y deja el campo Blueprint Path vacío para que detecte `render.yaml` en la raíz. También puedes crear un Web Service usando runtime Docker y `Dockerfile`.

## Ejecución local
Instala FFmpeg y Python 3.11+, luego:
`pip install -r requirements.txt`
`uvicorn app:app --host 0.0.0.0 --port 8000`

El procesamiento requiere recursos de servidor suficientes para FFmpeg y faster-whisper. La instancia gratuita puede quedarse corta para videos largos/modelos grandes. Usa videos propios o autorizados.
