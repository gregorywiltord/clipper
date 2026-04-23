from flask import Flask, render_template, request, redirect, send_from_directory
import os, uuid, subprocess, json

app = Flask(__name__)
DATA_DIR = "/data"
os.makedirs(DATA_DIR, exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        job_id = str(uuid.uuid4())
        job_path = f"{DATA_DIR}/{job_id}"
        os.makedirs(job_path, exist_ok=True)

        with open(f"{job_path}/input.json", "w") as f:
            json.dump({"url": request.form["url"], "api_key": request.form["api_key"]}, f)

        subprocess.Popen(["python", "worker.py", job_id])
        return redirect(f"/status/{job_id}")

    return render_template("index.html")

@app.route("/status/<job_id>")
def status(job_id):
    job_path = f"{DATA_DIR}/{job_id}"
    status_file = f"{job_path}/status.txt"

    status = "Processing..."
    clips = []

    if os.path.exists(status_file):
        with open(status_file) as f:
            status = f.read()

    clips_dir = f"{job_path}/clips"
    if os.path.exists(clips_dir):
        clips = sorted(os.listdir(clips_dir))

    return render_template("status.html", status=status, clips=clips, job_id=job_id)

@app.route("/download/<job_id>/<filename>")
def download(job_id, filename):
    return send_from_directory(f"{DATA_DIR}/{job_id}/clips", filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
