import os, uuid, shutil, subprocess, sys, tempfile, threading, zipfile
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).parent
WORK = ROOT / "jobs"
WORK.mkdir(exist_ok=True)
jobs = {}
lock = threading.Lock()

app = FastAPI(title="Clipper con subtítulos")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")

def run_job(job_id, source_path, clips, duration, language, model):
    folder = WORK / job_id
    out = folder / "clips"
    out.mkdir(parents=True, exist_ok=True)
    try:
        with lock:
            jobs[job_id]["status"] = "processing"
            jobs[job_id]["message"] = "Analizando el video y generando subtítulos…"
        script = ROOT / "clipper_subtitulos.py"
        cmd = [sys.executable, str(script), str(source_path), "--clips", str(clips),
               "--duracion", str(duration), "--modelo", model, "--salida", str(out)]
        if language:
            cmd += ["--idioma", language]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60*60*8)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "No se pudo procesar el video")[-3500:])
        zip_path = folder / "clips_generados.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for p in out.glob("*.mp4"):
                z.write(p, p.name)
        with lock:
            jobs[job_id].update(status="done", message="¡Listo! Tus clips están preparados.", download=f"/download/{job_id}")
    except Exception as e:
        with lock:
            jobs[job_id].update(status="error", message=str(e)[-3500:])
    finally:
        try:
            Path(source_path).unlink(missing_ok=True)
        except Exception:
            pass

@app.post("/api/process")
async def process_video(
    video: UploadFile = File(...),
    clips: int = Form(5),
    duration: int = Form(30),
    language: str = Form("es"),
    model: str = Form("small")
):
    if clips < 1 or clips > 20: raise HTTPException(400, "Elige entre 1 y 20 clips.")
    if duration < 10 or duration > 180: raise HTTPException(400, "La duración debe estar entre 10 y 180 segundos.")
    if model not in ("tiny", "base", "small", "medium"): raise HTTPException(400, "Modelo no válido.")
    suffix = Path(video.filename or "video.mp4").suffix.lower()
    if suffix not in (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"):
        raise HTTPException(400, "Formato no compatible. Usa MP4, MOV, MKV, WEBM o AVI.")
    job_id = uuid.uuid4().hex
    folder = WORK / job_id
    folder.mkdir(parents=True, exist_ok=True)
    src = folder / ("video" + suffix)
    size = 0
    with src.open("wb") as f:
        while chunk := await video.read(1024 * 1024):
            size += len(chunk)
            if size > 2 * 1024 * 1024 * 1024:
                src.unlink(missing_ok=True)
                raise HTTPException(413, "El video supera el límite de 2 GB.")
            f.write(chunk)
    with lock:
        jobs[job_id] = {"status":"queued", "message":"Video recibido. En espera…"}
    threading.Thread(target=run_job, args=(job_id, str(src), clips, duration, language or None, model), daemon=True).start()
    return {"job_id": job_id}

@app.get("/api/status/{job_id}")
def status(job_id: str):
    with lock:
        data = jobs.get(job_id)
    if not data: raise HTTPException(404, "Trabajo no encontrado.")
    return data

@app.get("/download/{job_id}")
def download(job_id: str):
    p = WORK / job_id / "clips_generados.zip"
    if not p.exists(): raise HTTPException(404, "El archivo todavía no está listo.")
    return FileResponse(p, filename="clips_generados.zip", media_type="application/zip")
