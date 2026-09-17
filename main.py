import base64
import json
import os
import random
import subprocess
import time
from pathlib import Path

import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work"
MUSIC = ROOT / "music"
WORK.mkdir(exist_ok=True)

TOPICS = [
    ("श्री कृष्ण", "कृष्ण", "हे कृष्ण, अपने भक्तों के जीवन में प्रेम, शांति और भक्ति का प्रकाश भर दो।", "krishna"),
    ("महादेव", "शिव", "हर हर महादेव। महादेव की भक्ति मन को शक्ति, धैर्य और शांति देती है।", "shiv"),
    ("श्री हनुमान", "हनुमान", "जय बजरंगबली। श्री हनुमान की भक्ति साहस और विश्वास की प्रेरणा देती है।", "hanuman"),
    ("श्री राम", "राम", "श्री राम का नाम मन को मर्यादा, शांति और सत्य के मार्ग की याद दिलाता है।", "ram"),
    ("माता रानी", "माता", "जय माता दी। माँ की भक्ति में विश्वास, शक्ति और करुणा का भाव है।", "mata"),
]


def gemini_image(prompt: str, output: Path):
    key = os.environ["GEMINI_API_KEY"]
    url = "https://generativelanguage.googleapis.com/v1beta/interactions"
    payload = {
        "model": "gemini-3.1-flash-image",
        "input": prompt,
        "response_format": {
            "type": "image",
            "aspect_ratio": "9:16",
            "image_size": "1K",
        },
    }

    # Gemini can temporarily return HTTP 429 when the request rate/quota is
    # exceeded. Retry with exponential backoff instead of failing immediately.
    last_error = None
    for attempt in range(5):
        r = requests.post(
            url,
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json=payload,
            timeout=180,
        )
        if r.status_code != 429:
            r.raise_for_status()
            data = r.json()
            image = data.get("output_image")
            if not image or not image.get("data"):
                raise RuntimeError("Gemini image response did not contain an image")
            output.write_bytes(base64.b64decode(image["data"]))
            return

        last_error = r.text
        retry_after = r.headers.get("Retry-After")
        try:
            delay = max(5, min(int(float(retry_after)), 120)) if retry_after else min(10 * (2 ** attempt), 120)
        except ValueError:
            delay = min(10 * (2 ** attempt), 120)
        print(f"Gemini returned HTTP 429; retrying in {delay}s (attempt {attempt + 1}/5)")
        time.sleep(delay)

    raise RuntimeError(f"Gemini image generation remained rate-limited after 5 attempts: {last_error}")


def choose_music(category: str) -> Path:
    files = list(MUSIC.glob("*.mp3")) + list(MUSIC.glob("*.wav")) + list(MUSIC.glob("*.m4a"))
    if not files:
        raise RuntimeError("No music found. Add licensed YouTube Audio Library tracks to music/ first.")
    matches = [p for p in files if category.lower() in p.stem.lower()]
    return random.choice(matches or files)


def make_video(image: Path, music: Path, output: Path):
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='min(zoom+0.0005,1.08)':d=300:s=1080x1920:fps=30,format=yuv420p"
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(image), "-i", str(music),
        "-t", "10", "-vf", vf, "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
        str(output),
    ]
    subprocess.run(cmd, check=True)


def facebook_reel(video: Path, title: str, description: str):
    page = os.environ["FACEBOOK_PAGE_ID"]
    token = os.environ["FACEBOOK_PAGE_ACCESS_TOKEN"]
    version = os.getenv("FACEBOOK_GRAPH_VERSION", "v26.0")
    start = requests.post(
        f"https://graph.facebook.com/{version}/{page}/video_reels",
        data={"upload_phase": "start", "access_token": token},
        timeout=60,
    )
    start.raise_for_status()
    info = start.json()
    video_id = info["video_id"]
    upload_url = info.get("upload_url") or f"https://rupload.facebook.com/video-upload/{version}/{video_id}"
    size = video.stat().st_size
    with video.open("rb") as fh:
        upload = requests.post(
            upload_url,
            headers={
                "Authorization": f"OAuth {token}",
                "offset": "0",
                "file_size": str(size),
                "Content-Type": "application/octet-stream",
            },
            data=fh,
            timeout=300,
        )
    upload.raise_for_status()
    finish = requests.post(
        f"https://graph.facebook.com/{version}/{page}/video_reels",
        data={
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "PUBLISHED",
            "title": title,
            "description": description,
            "access_token": token,
        },
        timeout=60,
    )
    finish.raise_for_status()
    return finish.json()


def youtube_upload(video: Path, title: str, description: str):
    creds = Credentials(
        None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    youtube = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {"title": title, "description": description, "categoryId": "22"},
        "status": {"privacyStatus": "public"},
    }
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(str(video), mimetype="video/mp4", resumable=True),
    )
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response.get("id")


def main():
    required = [
        "GEMINI_API_KEY",
        "FACEBOOK_PAGE_ID",
        "FACEBOOK_PAGE_ACCESS_TOKEN",
        "YOUTUBE_CLIENT_ID",
        "YOUTUBE_CLIENT_SECRET",
        "YOUTUBE_REFRESH_TOKEN",
    ]
    missing = [x for x in required if not os.getenv(x)]
    if missing:
        raise RuntimeError("Missing GitHub Secrets: " + ", ".join(missing))

    topic, deity, message, category = random.choice(TOPICS)
    title = f"🙏 {topic} | भक्ति संदेश"
    description = f"{message}\n\n#Bhakti #SanatanDharma #{deity} #BhaktiReels #Shorts"
    prompt = (
        f"Create a premium devotional palm-art illustration for a vertical 9:16 social media short about {topic}. "
        f"Show {deity} as the central devotional subject emerging from a realistic human palm/hand drawing, "
        "intricate black ink pen artwork on warm off-white paper, elegant Indian spiritual motifs, "
        "subtle golden devotional atmosphere, cinematic soft lighting, highly detailed hand-drawn linework, "
        "clean composition, no watermark, no modern objects, no text. Mobile-first 9:16 composition."
    )
    image = WORK / "palm_art.png"
    video = WORK / "bhakti_reel.mp4"
    gemini_image(prompt, image)
    music = choose_music(category)
    make_video(image, music, video)
    fb = facebook_reel(video, title, description)
    yt = youtube_upload(video, title, description)
    print(json.dumps({"topic": topic, "music": music.name, "facebook": fb, "youtube_video_id": yt}, ensure_ascii=False))


if __name__ == "__main__":
    main()
