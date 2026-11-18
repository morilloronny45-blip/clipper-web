# Clipper Web (Android / Chrome)

Esta carpeta contiene una aplicación web basada en tu `clipper_subtitulos.py`.
Permite subir un video desde Chrome, elegir cantidad/duración/idioma/modelo y descargar los clips en ZIP.

## Importante
La página web es la interfaz. El procesamiento real necesita un servidor Linux con FFmpeg,
Python y memoria/CPU suficientes para Whisper. No se puede ejecutar el script Python directamente
dentro de Chrome. El primer uso descarga el modelo de Whisper y puede tardar.

## Probar en una computadora
1. Instala Python 3.11+ y FFmpeg.
2. En esta carpeta ejecuta: `pip install -r requirements.txt`
3. Ejecuta: `uvicorn app:app --host 0.0.0.0 --port 8000`
4. Abre `http://localhost:8000`.

## Publicar para usarlo desde el celular
1. Sube esta carpeta a un repositorio privado de GitHub.
2. Crea un servicio web en un proveedor que admita Docker (por ejemplo, Render).
3. Selecciona este repositorio y el `Dockerfile`.
4. Usa un disco persistente si quieres conservar resultados; configura límites de tamaño y autenticación antes de hacerlo público.
5. Abre la URL HTTPS que te entregue el proveedor desde Chrome en Android.

## Uso
- Selecciona un video de tu dispositivo.
- Configura los clips y pulsa “Crear mis clips”.
- Espera a que termine y descarga el ZIP.
- Usa solamente videos tuyos o con permiso del titular.

## Límites de esta versión
- Acepta archivos de video subidos desde el dispositivo (no pega enlaces de plataformas).
- El ZIP se genera en el servidor.
- Esta versión básica no incluye cuentas, pagos, borrado automático ni protección por contraseña.
- Para un servicio público, añade autenticación, cuotas, limpieza automática de archivos y límites de recursos.
