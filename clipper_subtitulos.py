#!/usr/bin/env python3
"""
Clipper con subtítulos.

Pegas el link de TU video (o una ruta de archivo) y el programa:
  1) lo descarga (si es un link),
  2) lo transcribe con Whisper (corre en tu equipo, gratis),
  3) elige los mejores momentos (audio intenso + mucha voz),
  4) corta clips verticales 9:16 con subtítulos grandes ya incrustados.

Instalación (una sola vez):
    1) Instala ffmpeg  (Windows: winget install ffmpeg)
    2) pip install numpy faster-whisper yt-dlp

Uso:
    python clipper_subtitulos.py "https://youtube.com/watch?v=XXXX"
    python clipper_subtitulos.py mi_video.mp4 --clips 6 --duracion 30 --idioma es

Usa solo videos tuyos o con permiso del autor.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import wave

import numpy as np


# ---------------------------------------------------------------- utilidades
def correr(cmd, cwd=None):
    """Ejecuta un comando y, si falla, muestra el error real."""
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       text=True, cwd=cwd)
    if r.returncode != 0:
        sys.exit("Falló: " + " ".join(cmd[:3]) + "\n" + r.stderr[-1500:])
    return r


def ffmpeg(args, cwd=None):
    correr(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + args, cwd=cwd)


# ------------------------------------------------------------------ descarga
def descargar(link, carpeta):
    """Baja el video con yt-dlp y devuelve la ruta del archivo."""
    plantilla = os.path.join(carpeta, "video.%(ext)s")
    cmd = [sys.executable, "-m", "yt_dlp", "-f", "bv*[height<=1080]+ba/b",
           "--merge-output-format", "mp4", "--no-playlist",
           "-o", plantilla, link]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        sys.exit("No pude descargar el video:\n" + r.stderr[-1200:] +
                 "\n¿Instalaste yt-dlp?  pip install yt-dlp")
    for nombre in os.listdir(carpeta):
        if nombre.startswith("video."):
            return os.path.join(carpeta, nombre)
    sys.exit("La descarga terminó pero no encuentro el archivo.")


# ------------------------------------------------------------------- audio
def energia_por_segundo(video, tmp):
    wav_path = os.path.join(tmp, "audio.wav")
    ffmpeg(["-i", video, "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", wav_path])
    with wave.open(wav_path, "rb") as w:
        sr = w.getframerate()
        datos = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    n = len(datos) // sr
    if n == 0:
        return np.array([])
    datos = datos[: n * sr].reshape(n, sr)
    return np.sqrt((datos ** 2).mean(axis=1))


# ------------------------------------------------------------ transcripción
def transcribir(video, modelo, idioma):
    """Devuelve una lista de palabras: [{'t0','t1','texto'}, ...]."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("Falta faster-whisper:  pip install faster-whisper")
    print(f"Transcribiendo con Whisper ({modelo})... la primera vez descarga el modelo.")
    m = WhisperModel(modelo, compute_type="int8")
    segmentos, info = m.transcribe(video, language=idioma, word_timestamps=True,
                                   vad_filter=True)
    palabras = []
    for seg in segmentos:
        for w in (seg.words or []):
            texto = w.word.strip()
            if texto:
                palabras.append({"t0": w.start, "t1": w.end, "texto": texto})
    print(f"Idioma detectado: {info.language}. Palabras: {len(palabras)}")
    return palabras


# -------------------------------------------------------- mejores momentos
def normalizar(x):
    x = np.asarray(x, dtype=np.float32)
    if len(x) == 0 or x.max() == x.min():
        return np.zeros_like(x)
    return (x - x.min()) / (x.max() - x.min())


def mejores_momentos(energia, palabras, cantidad, duracion):
    """Puntúa cada segundo: volumen + cantidad de palabras habladas."""
    total = len(energia)
    if total == 0:
        return []
    habla = np.zeros(total, dtype=np.float32)
    for p in palabras:
        s = int(p["t0"])
        if 0 <= s < total:
            habla[s] += 1
    score = normalizar(energia) + normalizar(habla)

    ventana = max(3, duracion // 3)
    suave = np.convolve(score, np.ones(ventana) / ventana, mode="same")

    elegidos = []
    for idx in np.argsort(suave)[::-1]:
        ini = max(0, int(idx) - duracion // 2)
        fin = ini + duracion
        if fin > total:
            fin = total
            ini = max(0, fin - duracion)
        if all(fin <= a or ini >= b for a, b in elegidos):
            elegidos.append((ini, fin))
        if len(elegidos) >= cantidad:
            break
    return sorted(elegidos)


# -------------------------------------------------------------- subtítulos
def t_ass(t):
    t = max(0.0, t)
    h, resto = divmod(t, 3600)
    m, s = divmod(resto, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def crear_ass(palabras, ini, fin, ruta):
    """Subtítulos grandes de 3 palabras, estilo Shorts, para el rango ini-fin."""
    dentro = [p for p in palabras if p["t0"] >= ini and p["t1"] <= fin + 0.5]
    grupos = [dentro[i:i + 3] for i in range(0, len(dentro), 3)]

    cab = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n"
        "WrapStyle: 2\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,"
        "BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,"
        "BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
        "Style: Default,Arial,92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
        "1,0,0,0,100,100,0,0,1,7,2,2,60,60,520,1\n\n"
        "[Events]\n"
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    )
    lineas = []
    for i, g in enumerate(grupos):
        t0 = g[0]["t0"] - ini
        # el subtítulo dura hasta que empieza el siguiente (o hasta que termina la última palabra)
        t1 = (grupos[i + 1][0]["t0"] - ini) if i + 1 < len(grupos) else g[-1]["t1"] - ini
        texto = " ".join(x["texto"] for x in g).upper().replace("{", "").replace("}", "")
        lineas.append(f"Dialogue: 0,{t_ass(t0)},{t_ass(t1)},Default,,0,0,0,,{texto}")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(cab + "\n".join(lineas) + "\n")
    return len(grupos)


def cortar_clip(video, ini, fin, palabras, salida):
    """Corta, recorta a 9:16 y quema los subtítulos."""
    with tempfile.TemporaryDirectory() as tmp:
        # Usamos ruta relativa dentro de tmp para evitar problemas de rutas en Windows
        n = crear_ass(palabras, ini, fin, os.path.join(tmp, "sub.ass"))
        vf = "crop=min(iw\\,ih*9/16):min(ih\\,iw*16/9),scale=1080:1920"
        if n:
            vf += ",ass=sub.ass"
        ffmpeg(["-ss", str(ini), "-to", str(fin), "-i", os.path.abspath(video),
                "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-c:a", "aac", "-b:a", "160k", os.path.abspath(salida)], cwd=tmp)
    return n


# -------------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(description="Clips verticales con subtítulos.")
    p.add_argument("fuente", help="Link de tu video o ruta de un archivo")
    p.add_argument("--clips", type=int, default=5)
    p.add_argument("--duracion", type=int, default=30, help="segundos por clip")
    p.add_argument("--idioma", default=None, help="es, en... (por defecto se detecta)")
    p.add_argument("--modelo", default="small", help="tiny, base, small, medium")
    p.add_argument("--salida", default="clips")
    a = p.parse_args()

    if shutil.which("ffmpeg") is None:
        sys.exit("No encuentro ffmpeg. Windows: winget install ffmpeg | Mac: brew install ffmpeg")

    os.makedirs(a.salida, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        if a.fuente.startswith("http"):
            print("Descargando video...")
            video = descargar(a.fuente, tmp)
        else:
            video = a.fuente
            if not os.path.isfile(video):
                sys.exit(f"No encuentro el archivo: {video}")

        print("Analizando audio...")
        energia = energia_por_segundo(video, tmp)
        palabras = transcribir(video, a.modelo, a.idioma)
        momentos = mejores_momentos(energia, palabras, a.clips, a.duracion)
        if not momentos:
            sys.exit("No pude detectar momentos en este video.")

        base = "clip"
        for i, (ini, fin) in enumerate(momentos, 1):
            salida = os.path.join(a.salida, f"{base}{i}.mp4")
            print(f"Clip {i}/{len(momentos)}: {ini}s -> {fin}s")
            cortar_clip(video, ini, fin, palabras, salida)

    print(f"\nListo. Clips con subtítulos en la carpeta '{a.salida}'.")


if __name__ == "__main__":
    main()
