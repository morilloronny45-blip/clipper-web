import os, uuid, subprocess, sys, zipfile, threading
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).parent
WORK = Path(os.environ.get("CLIPPER_DATA", "/tmp/clipper_jobs"))
WORK.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="CLIPPER")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
jobs = {}
lock = threading.Lock()

@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")

def process(job_id, src, clips, duration, language, model):
    folder = WORK / job_id
    out = folder / "clips"
    out.mkdir(parents=True, exist_ok=True)
    try:
        with lock:
            jobs[job_id] = {"status":"processing", "message":"Analizando audio y creando subtítulos…"}
        cmd = [sys.executable, str(ROOT / "clipper_subtitulos.py"), str(src),
               "--clips", str(clips), "--duracion", str(duration),
               "--modelo", model, "--salida", str(out)]
        if language:
            cmd += ["--idioma", language]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=8*60*60)
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout or "Error al procesar")[-3000:])
        archive = folder / "clips_generados.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for clip in out.glob("*.mp4"):
                z.write(clip, clip.name)
        with lock:
            jobs[job_id] = {"status":"done", "message":"Tus clips están listos.", "download":f"/download/{job_id}"}
    except Exception as e:
        with lock:
            jobs[job_id] = {"status":"error", "message":str(e)[-3000:]}
    finally:
        src.unlink(missing_ok=True)

@app.post("/api/process")
async def start(video: UploadFile = File(...), clips: int = Form(5),
                duration: int = Form(30), language: str = Form("es"),
                model: str = Form("small")):
    if not video.filename:
        raise HTTPException(400, "Selecciona un video.")
    ext = Path(video.filename).suffix.lower()
    if ext not in {".mp4",".mov",".mkv",".webm",".avi",".m4v"}:
        raise HTTPException(400, "Formato no compatible. Usa MP4, MOV, MKV, WEBM o AVI.")
    if not 1 <= clips <= 20 or not 10 <= duration <= 180:
        raise HTTPException(400, "Cantidad o duración fuera de los límites.")
    if model not in {"tiny","base","small","medium"}:
        raise HTTPException(400, "Modelo no válido.")
    job_id = uuid.uuid4().hex
    folder = WORK / job_id
    folder.mkdir(parents=True, exist_ok=True)
    src = folder / ("source" + ext)
    total = 0
    with src.open("wb") as f:
        while chunk := await video.read(1024*1024):
            total += len(chunk)
            if total > 1024*1024*1024:
                src.unlink(missing_ok=True)
                raise HTTPException(413, "El video supera el límite de 1 GB.")
            f.write(chunk)
    with lock:
        jobs[job_id] = {"status":"queued", "message":"Video recibido…"}
    threading.Thread(target=process, args=(job_id,src,clips,duration,language or None,model), daemon=True).start()
    return {"job_id":job_id}

@app.get("/api/status/{job_id}")
def get_status(job_id: str):
    with lock:
        item = jobs.get(job_id)
    if not item:
        raise HTTPException(404, "Trabajo no encontrado.")
    return item

@app.get("/download/{job_id}")
def get_download(job_id: str):
    archive = WORK / job_id / "clips_generados.zip"
    if not archive.exists():
        raise HTTPException(404, "El archivo aún no está listo.")
    return FileResponse(archive, filename="CLIPPER_clips.zip", media_type="application/zip")
