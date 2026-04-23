import os, json, subprocess, requests, sys

job_id = sys.argv[1]
BASE = f"/data/{job_id}"

def update(msg):
    with open(f"{BASE}/status.txt", "w") as f:
        f.write(msg)

def run(cmd):
    subprocess.run(cmd, check=True)

try:
    data = json.load(open(f"{BASE}/input.json"))
    url, api_key = data["url"], data["api_key"]

    update("Downloading video...")
    run(["yt-dlp", "-f", "best[height<=720]", "-o", f"{BASE}/video.%(ext)s", url])

    video_file = next(f for f in os.listdir(BASE) if f.startswith("video") and not f.endswith(".json"))
    video_path = f"{BASE}/{video_file}"

    update("Fetching subtitles...")
    run(["yt-dlp", "--write-auto-sub", "--skip-download", "-o", f"{BASE}/video", url])

    subtitle_file = next(f for f in os.listdir(BASE) if f.endswith(".vtt"))
    with open(f"{BASE}/{subtitle_file}", encoding="utf-8") as f:
        transcript = f.read()

    update("Analyzing with Gemini...")
    prompt = f'Extract 3-5 viral clips. Return ONLY JSON array: [{{"start":0,"end":10}}]\n\n{transcript[:10000]}'

    res = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}",
        json={"contents": [{"parts": [{"text": prompt}]}]}
    )
    res.raise_for_status()

    text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
    clips = json.loads(text)[:5]

    clips_dir = f"{BASE}/clips"
    os.makedirs(clips_dir, exist_ok=True)

    update("Cutting clips...")
    for i, c in enumerate(clips):
        run([
            "ffmpeg", "-i", video_path,
            "-ss", str(c["start"]), "-to", str(c["end"]),
            "-vf", "scale=720:1280", "-y", f"{clips_dir}/clip_{i}.mp4"
        ])

    update("Done ✅")

except Exception as e:
    update(f"Error ❌: {e}")
