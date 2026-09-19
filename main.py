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
REFERENCE = ROOT / "palm_reference.jpg.jpg"
WORK.mkdir(exist_ok=True)

TOPICS = [
    ("श्री कृष्ण — वृंदावन", "कृष्ण", "कृष्ण भक्ति", "krishna"),
    ("महादेव — तुंगनाथ", "शिव", "शिव भक्ति", "shiv"),
    ("श्री हनुमान", "हनुमान", "हनुमान भक्ति", "hanuman"),
    ("श्री राम — अयोध्या", "राम", "राम भक्ति", "ram"),
    ("माँ वैष्णो देवी", "माता", "माता भक्ति", "mata"),
    ("केदारनाथ", "शिव", "केदारनाथ भक्ति", "shiv"),
]

def choose_topic():
    if os.getenv("GITHUB_EVENT_NAME") == "schedule":
        now = datetime.now(timezone.utc)
        slot_map = {5: 0, 8: 1, 11: 2}
        slot = slot_map.get(now.hour, now.hour % 3)
        return TOPICS[(now.date().toordinal() * 3 + slot) % len(TOPICS)]
    return random.choice(TOPICS)

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
        "-i",
        "sine=frequency=196:duration=10[a];sine=frequency=293.66:duration=10[b];"
        "sine=frequency=392:duration=10[c];[a][b][c]amix=inputs=3:duration=longest,"
        "volume=0.55,afade=t=in:st=0:d=0.8,afade=t=out:st=8.8:d=1.2",
        "-t", "10", "-c:a", "libmp3lame", "-b:a", "128k", str(output)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    return output

def _qwen_edit(input_path: Path, prompt: str, output: Path):
    api_key = os.environ.get("FREEAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing GitHub Secret: FREEAI_API_KEY")
    with input_path.open("rb") as fh:
        response = requests.post(
            "https://api.free.ai/v1/image/edit/",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"image": (input_path.name, fh, "image/jpeg")},
            data={"model": "qwen-image-edit", "prompt": prompt, "operation": "edit"},
            timeout=600,
        )
    if not response.ok:
        raise RuntimeError(f"Free.ai Qwen edit failed ({response.status_code}): {response.text[:4000]}")
    if response.headers.get("content-type", "").startswith("image/"):
        output.write_bytes(response.content)
    else:
        result = response.json()
        data = result.get("data", result)
        image_url = (
            result.get("output_url") or result.get("image_url") or result.get("url") or result.get("share_url")
            or (data.get("output_url") if isinstance(data, dict) else None)
            or (data.get("image_url") if isinstance(data, dict) else None)
            or (data.get("url") if isinstance(data, dict) else None)
        )
        if not image_url:
            raise RuntimeError(f"Free.ai returned no image URL: {str(result)[:5000]}")
        ir = requests.get(image_url, timeout=600)
        ir.raise_for_status()
        output.write_bytes(ir.content)
    if output.stat().st_size < 10000:
        raise RuntimeError("Free.ai returned an unexpectedly small image.")
    with Image.open(output) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.save(output, "PNG")


def generate_reference_guided_image(output: Path):
    # PASS 1: same reference photo, but a very simple cleanup instruction.
    # PASS 2: use that cleaned hand as the base for the actual devotional drawing.
    clean = WORK / "qwen_clean_hand.png"
    clean_prompt = """
Keep the exact real adult human hand and white studio setup unchanged.
Do not generate a new hand. Keep the same wrist, palm, thumb, all five fingers,
nails, skin pores, fingerprints, creases, lighting and camera perspective.

ERASE ALL ARTWORK FROM THE SKIN. Remove every blue/black pen drawing, mountain,
temple, river, pilgrim, symbol, Om, trident, text, name, signature and decorative
mark. The skin must become completely natural and blank. Do not add anything.
"""
    _qwen_edit(REFERENCE, clean_prompt, clean)

    art_prompt = """
Keep this EXACT cleaned real adult human hand unchanged: same wrist, palm, thumb,
all five fingers, nails, pores, fingerprints, creases, lighting and camera angle.
Do NOT generate or replace the hand.

Now draw an intricate devotional Palm Art directly on the skin using ONLY blue/indigo
ballpoint pen. Cover almost the entire palm and fingers with dense fine handmade
hatching, cross-hatching, contour lines and stippling that follows the natural
creases.

THE EXACT CENTER OF THE PALM MUST BE A LARGE, UNMISTAKABLE, HIGHLY RECOGNIZABLE
FIGURE OF LORD SHIVA / MAHADEV, occupying 35-45% of the palm. Show his actual face,
calm eyes, third eye, matted jata, crescent moon, snake, shoulders/torso in meditation
and a trishul. This is a figurative drawing of Mahadev, NOT an Om symbol, NOT only a
trishul, NOT a mountain and NOT only a temple.

Around him, add much smaller connected miniature Himalayan devotional details:
temple, lamps, flowers, river/ghat, mountains, trees and tiny pilgrims.

Make it look physically hand-drawn directly on real skin, with pores and creases
visible through the ink. Put 2-3 real blue/black ballpoint pens beside the wrist.

ABSOLUTELY NO tattoo, henna, mehndi, decal, sticker, printed glove, digital overlay,
CGI, 3D render, vector art, marker, paint, watercolor, plastic skin, synthetic hand,
extra/missing/fused/malformed fingers, cropped hand, watermark, logo, signature,
name, letters, numbers or readable text.
"""
    _qwen_edit(clean, art_prompt, output)

    with Image.open(output) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        target_w, target_h = 864, 1536
        im.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (target_w, target_h), "white")
        canvas.paste(im, ((target_w - im.width) // 2, (target_h - im.height) // 2))
        canvas.save(output, "PNG")

    print("TEST: Qwen-Image-Edit 2511 two-pass cleanup + Mahadev edit completed.")

def generate_motion_video(image: Path, output: Path):
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

def make_video(raw_video: Path, music: Path, output: Path):
    vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p"
    cmd = [
        "ffmpeg", "-y", "-i", str(raw_video), "-i", str(music), "-t", "10",
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
    body = {
        "snippet": {"title": title, "description": description, "categoryId": "22"},
        "status": {"privacyStatus": "public"}
    }
    request = youtube.videos().insert(
        part="snippet,status", body=body,
        media_body=MediaFileUpload(str(video), mimetype="video/mp4", resumable=True)
    )
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response.get("id")

def main():
    test_only = os.getenv("TEST_ONLY", "true").lower() == "true"
    required = ["FREEAI_API_KEY"]
    if not test_only:
        required += [
            "FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_ACCESS_TOKEN",
            "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"
        ]
    missing = [x for x in required if not os.getenv(x)]
    if missing:
        raise RuntimeError("Missing GitHub Secrets: " + ", ".join(missing))

    topic, deity, category, music_category = TOPICS[1]
    image = WORK / "palm_art.png"
    raw_video = WORK / "wan2_video.mp4"
    video = WORK / "bhakti_reel.mp4"

    generate_reference_guided_image(image)
    generate_motion_video(image, raw_video)
    music = choose_music(music_category)
    make_video(raw_video, music, video)

    title = f"🙏 {topic} | Bhakti Palm Art"
    description = f"{category} — {deity} की भक्ति से मन में शांति, शक्ति और विश्वास का प्रकाश।\n\n#Bhakti #SanatanDharma #Shiv #BhaktiReels #Shorts"

    if test_only:
        print("TEST_ONLY=true: generated but NOT posted.")
        print(json.dumps({
            "topic": topic,
            "music": music.name,
            "image": str(image),
            "video": str(video),
            "image_model": "Qwen-Image-Edit-2511 via Free.ai self-hosted",
            "video_model": "FFmpeg cinematic motion",
            "reference_used": True,
            "posted": False
        }, ensure_ascii=False))
        return

    fb = facebook_reel(video, title, description)
    yt = youtube_upload(video, title, description)
    print(json.dumps({
        "topic": topic,
        "facebook": fb,
        "youtube_video_id": yt,
        "music": music.name,
        "image_model": "Qwen-Image-Edit-2511 via Free.ai self-hosted",
        "video_model": "FFmpeg cinematic motion",
        "reference_used": True
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
