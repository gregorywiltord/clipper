import os, json, subprocess, requests, sys, time

job_id = sys.argv[1]
BASE = f"/data/{job_id}"
os.makedirs(BASE, exist_ok=True)

def update(msg):
    with open(f"{BASE}/status.txt", "w") as f:
        f.write(msg)

def run(cmd, retries=5):
    strategies = [
        [],  # Try 1: Default
        ["--extractor-args", "youtube:player_client=android"],  # Try 2: Android
        ["--extractor-args", "youtube:player_client=web"],  # Try 3: Web
        ["-U"],  # Try 4: Update
        ["--no-cache-dir", "-U"],  # Try 5: No cache + update
    ]
    
    for attempt in range(retries):
        # Build command with strategy
        if "yt-dlp" in cmd[0] and attempt > 0:
            strategy_idx = min(attempt - 1, len(strategies) - 1)
            strategy = strategies[strategy_idx]
            # Insert strategy args after yt-dlp
            test_cmd = cmd[:1] + strategy + cmd[1:]
        else:
            test_cmd = cmd
            
        result = subprocess.run(test_cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return
            
        error_msg = result.stderr or result.stdout or "Unknown error"
        print(f"DEBUG - Attempt {attempt + 1}/{retries}")
        print(f"DEBUG - Command: {' '.join(test_cmd)}")
        print(f"DEBUG - Return code: {result.returncode}")
        print(f"DEBUG - Error: {error_msg[:200]}")
        
        if attempt < retries - 1:
            time.sleep(5 * (2 ** attempt))  # exponential backoff
            
    raise Exception(f"Command failed after {retries} attempts: {' '.join(cmd)}\n{error_msg}")

try:
    data = json.load(open(f"{BASE}/input.json"))
    url, api_key = data["url"], data["api_key"]

    update("Downloading video...")
    run(["yt-dlp", "-o", f"{BASE}/video.%(ext)s", url])

    video_file = next(f for f in os.listdir(BASE) if f.startswith("video") and not f.endswith(".json"))
    video_path = f"{BASE}/{video_file}"

    update("Fetching subtitles...")
    run(["yt-dlp", "--write-auto-sub", "--skip-download", "-o", f"{BASE}/video", url])

    subtitle_file = next((f for f in os.listdir(BASE) if f.endswith(".vtt")), None)
    if subtitle_file:
        with open(f"{BASE}/{subtitle_file}", encoding="utf-8") as f:
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
