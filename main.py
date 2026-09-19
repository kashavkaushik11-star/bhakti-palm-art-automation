import json
import os
import random
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work"
MUSIC = ROOT / "music"
WORK.mkdir(exist_ok=True)

TOPICS = [
    ("श्री कृष्ण — वृंदावन", "कृष्ण", "कृष्ण भक्ति", "krishna"),
    ("महादेव — तुंगनाथ", "शिव", "शिव भक्ति", "shiv"),
    ("श्री हनुमान", "हनुमान", "हनुमान भक्ति", "hanuman"),
    ("श्री राम — अयोध्या", "राम", "राम भक्ति", "ram"),
    ("माँ वैष्णो देवी", "माता", "माता भक्ति", "mata"),
    ("केदारनाथ", "शिव", "केदारनाथ भक्ति", "shiv"),
    ("काशी विश्वनाथ", "शिव", "काशी भक्ति", "shiv"),
    ("जगन्नाथ पुरी", "जगन्नाथ", "जगन्नाथ भक्ति", "krishna"),
    ("सोमनाथ", "शिव", "सोमनाथ भक्ति", "shiv"),
    ("बद्रीनाथ", "विष्णु", "बद्रीनाथ भक्ति", "krishna"),
]

def choose_topic():
    if os.getenv("GITHUB_EVENT_NAME") == "schedule":
        now = datetime.now(timezone.utc)
        slot_map = {5: 0, 8: 1, 11: 2}
        slot = slot_map.get(now.hour, now.hour % 3)
        return TOPICS[(now.date().toordinal() * 3 + slot) % len(TOPICS)]
    return random.choice(TOPICS)

def generate_reference_guided_image(prompt: str, output: Path):
    """TEST 6: Free.ai self-hosted flux-schnell direct text-to-image. No reference image."""
    api_key = os.environ.get("FREEAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing GitHub Secret: FREEAI_API_KEY")

    endpoint = "https://api.free.ai/v1/image/generate/"
    direct_prompt = """
Premium photorealistic macro editorial photograph of ONE real adult human hand,
palm facing the camera, complete hand visible from wrist through all five fingertips.
Natural human anatomy, realistic nails, pores, fingerprints and skin creases.
Light white studio background. Place 2-3 real blue/black ballpoint pens beside wrist.

The ENTIRE visible palm and fingers contain intricate handmade devotional Palm Art
drawn DIRECTLY ON REAL SKIN with dense blue/indigo BALLPOINT PEN. The ink follows
skin creases with thousands of thin imperfect pen strokes, cross-hatching, hatching
and stippling. It must look physically hand-drawn on skin, NOT tattoo, henna,
mehndi, decal, sticker, printed glove, digital overlay, CGI, vector, marker, paint
or watercolor.

CRITICAL CENTRAL SUBJECT: EXACT CENTER OF THE PALM contains a LARGE,
unmistakable, highly recognizable FIGURE OF LORD SHIVA (MAHADEV), not a symbol.
Show Shiva's recognizable face, calm eyes, third eye, long matted jata hair,
crescent moon, snake around neck, shoulders and torso, seated in meditation.
A clearly drawn trishul is beside him. Shiva's actual figure occupies 35-45% of
the palm and is the dominant recognizable element.

Around Shiva add only secondary miniature devotional details: Himalayan temple,
lamps, flowers, river/ghat, distant mountains, trees and tiny pilgrims.
The landscape must NEVER become the main subject.

Make it look like a real artist spent hours drawing this devotional world with blue
ballpoint pen directly on living skin while natural skin texture remains visible.
Crisp macro photography, realistic lighting, premium handcrafted appearance.

ABSOLUTELY ZERO READABLE TEXT: no Hindi, English, letters, numbers, names,
signature, handwriting, captions, labels, signs, banners, watermark or logo.

ONE HAND ONLY. No extra/missing/fused/duplicate fingers. No cropped fingertips.
No cropped wrist. No malformed anatomy.
"""
    payload = {
        "model": "flux-schnell",
        "prompt": direct_prompt,
        "width": 1024,
        "height": 1536,
    }

    last_error = None
    for attempt in range(3):
        try:
            response = requests.post(
                endpoint,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=300,
            )
            if not response.ok:
                raise RuntimeError(
                    f"Free.ai flux-schnell generation failed ({response.status_code}): "
                    f"{response.text[:3000]}"
                )
            data = response.json()
            image_url = (
                data.get("output_url") or data.get("image_url") or data.get("url")
                or data.get("data", {}).get("output_url")
                or data.get("data", {}).get("image_url")
            )
            if not image_url:
                raise RuntimeError(f"Free.ai returned no image URL: {str(data)[:4000]}")
            img = requests.get(image_url, timeout=300)
            img.raise_for_status()
            output.write_bytes(img.content)
            if output.stat().st_size < 10000:
                raise RuntimeError("Free.ai returned an unexpectedly small image.")
            with Image.open(output) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((864, 1536), Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", (864, 1536), "white")
                canvas.paste(im, ((864 - im.width) // 2, (1536 - im.height) // 2))
                canvas.save(output, format="PNG")
            print("TEST 6: direct Free.ai flux-schnell generation succeeded; reference image was NOT used.")
            return
        except Exception as exc:
            last_error = str(exc)
            print(f"Direct flux-schnell attempt {attempt + 1}/3 failed: {last_error}")
            if attempt < 2:
                time.sleep(min(10 * (attempt + 1), 30))
    raise RuntimeError(f"Direct flux-schnell generation failed: {last_error}")

def choose_music(category: str) -> Path:
    files = list(MUSIC.glob("*.mp3")) + list(MUSIC.glob("*.wav")) + list(MUSIC.glob("*.m4a"))
    if files:
        matches = [p for p in files if category.lower() in p.stem.lower()]
        return random.choice(matches or files)
    output = WORK / f"fallback_{category}.mp3"
    if output.exists() and output.stat().st_size > 0:
        return output
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "sine=frequency=196:duration=10[a];sine=frequency=293.66:duration=10[b];"
               "sine=frequency=392:duration=10[c];[a][b][c]amix=inputs=3:duration=longest,"
               "volume=0.55,afade=t=in:st=0:d=0.8,afade=t=out:st=8.8:d=1.2",
        "-t", "10", "-c:a", "libmp3lame", "-b:a", "128k", str(output)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    return output

def generate_wan_video(image: Path, output: Path):
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(image), "-t", "8",
        "-vf",
        "scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
        "zoompan=z='min(zoom+0.0008,1.08)':x='iw/2-(iw/zoom/2)':"
        "y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30,"
        "eq=contrast=1.03:saturation=1.05",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-pix_fmt", "yuv420p", str(output),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

def make_video(generated_video: Path, music: Path, output: Path):
    vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p"
    cmd = [
        "ffmpeg", "-y", "-i", str(generated_video), "-i", str(music), "-t", "10",
        "-vf", vf, "-r", "30", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "19", "-c:a", "aac", "-b:a", "160k", "-shortest",
        "-movflags", "+faststart", str(output)
    ]
    subprocess.run(cmd, check=True)

def facebook_reel(video: Path, title: str, description: str):
    page = os.environ["FACEBOOK_PAGE_ID"].strip()
    token = os.environ["FACEBOOK_PAGE_ACCESS_TOKEN"].strip()
    version = os.getenv("FACEBOOK_GRAPH_VERSION", "v26.0")
    verify = requests.get(
        f"https://graph.facebook.com/{version}/{page}",
        params={"fields": "id,name", "access_token": token}, timeout=60
    )
    if not verify.ok:
        raise RuntimeError(f"Facebook Page token/Page ID check failed: {verify.text[:1200]}")
    start = requests.post(
        f"https://graph.facebook.com/{version}/{page}/video_reels",
        data={"upload_phase": "start", "access_token": token}, timeout=60
    )
    if not start.ok:
        raise RuntimeError(f"Facebook Reel start failed: {start.text[:2000]}")
    info = start.json()
    video_id = info["video_id"]
    upload_url = info.get("upload_url") or f"https://rupload.facebook.com/video-upload/{version}/{video_id}"
    with video.open("rb") as fh:
        upload = requests.post(
            upload_url,
            headers={"Authorization": f"OAuth {token}", "offset": "0",
                     "file_size": str(video.stat().st_size),
                     "Content-Type": "application/octet-stream"},
            data=fh, timeout=300
        )
    if not upload.ok:
        raise RuntimeError(f"Facebook Reel upload failed: {upload.text[:2000]}")
    finish = requests.post(
        f"https://graph.facebook.com/{version}/{page}/video_reels",
        data={"upload_phase": "finish", "video_id": video_id,
              "video_state": "PUBLISHED", "title": title,
              "description": description, "access_token": token}, timeout=60
    )
    if not finish.ok:
        raise RuntimeError(f"Facebook Reel publish failed: {finish.text[:2000]}")
    return finish.json()

def youtube_upload(video: Path, title: str, description: str):
    creds = Credentials(
        None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )
    youtube = build("youtube", "v3", credentials=creds)
    body = {"snippet": {"title": title, "description": description, "categoryId": "22"},
            "status": {"privacyStatus": "public"}}
    request = youtube.videos().insert(
        part="snippet,status", body=body,
        media_body=MediaFileUpload(str(video), mimetype="video/mp4", resumable=True)
    )
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response.get("id")

def main():
    test_only = os.getenv("TEST_ONLY", "false").lower() == "true"
    required = ["FREEAI_API_KEY"]
    if not test_only:
        required += [
            "FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_ACCESS_TOKEN",
            "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"
        ]
    missing = [x for x in required if not os.getenv(x)]
    if missing:
        raise RuntimeError("Missing GitHub Secrets: " + ", ".join(missing))

    topic, deity, category, music_category = choose_topic()
    if test_only:
        topic, deity, category, music_category = TOPICS[1]

    title = f"🙏 {topic} | Bhakti Palm Art"
    description = f"{category} — {deity} की भक्ति से मन में शांति, शक्ति और विश्वास का प्रकाश।\n\n#Bhakti #SanatanDharma #{deity} #BhaktiReels #Shorts"

    image = WORK / "palm_art.png"
    raw_video = WORK / "wan2_video.mp4"
    video = WORK / "bhakti_reel.mp4"

    generate_reference_guided_image("Direct prompt generation", image)
    generate_wan_video(image, raw_video)
    music = choose_music(music_category)
    make_video(raw_video, music, video)

    if test_only:
        print("TEST_ONLY=true: generated but NOT posted.")
        print(json.dumps({
            "topic": topic, "music": music.name, "image": str(image),
            "video": str(video), "image_model": "Free.ai flux-schnell (self-hosted)",
            "video_model": "FFmpeg cinematic motion", "reference_used": False
        }, ensure_ascii=False))
        return

    fb = facebook_reel(video, title, description)
    yt = youtube_upload(video, title, description)
    print(json.dumps({
        "topic": topic, "facebook": fb, "youtube_video_id": yt,
        "music": music.name, "image_model": "Free.ai flux-schnell",
        "video_model": "FFmpeg cinematic motion", "reference_used": False
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
