import os, json, subprocess, requests, sys, time
from pytube import YouTube

job_id = sys.argv[1]
BASE = f"/data/{job_id}"
os.makedirs(BASE, exist_ok=True)

def update(msg):
    with open(f"{BASE}/status.txt", "w") as f:
        f.write(msg)

def run(cmd, retries=3):
    for attempt in range(retries):
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return
        error_msg = result.stderr or result.stdout or "Unknown error"
        print(f"DEBUG - Attempt {attempt + 1}/{retries}")
        print(f"DEBUG - Command: {' '.join(cmd)}")
        print(f"DEBUG - Return code: {result.returncode}")
        print(f"DEBUG - Error: {error_msg}")
        if attempt < retries - 1:
            time.sleep(5 * (2 ** attempt))  # longer backoff
    raise Exception(f"Command failed after {retries} attempts: {' '.join(cmd)}\n{error_msg}")

try:
    data = json.load(open(f"{BASE}/input.json"))
    url, api_key = data["url"], data["api_key"]

    update("Downloading video...")
    yt = YouTube(url)
    stream = yt.streams.filter(progressive=False, file_extension='mp4').order_by('resolution').desc().first()
    if not stream:
        stream = yt.streams.get_highest_resolution()
    video_path = stream.download(BASE, filename="video.mp4")

    update("Fetching subtitles...")
    caption = yt.captions.get_by_language_code('en')
    if caption:
        srt_content = caption.generate_srt_captions()
        caption_file = f"{BASE}/video.en.vtt"
        with open(caption_file, "w", encoding="utf-8") as f:
            f.write(srt_content)
        with open(caption_file, encoding="utf-8") as f:
            transcript = f.read()
    else:
        transcript = "No captions available"

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
