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

def generate_reference_guided_image(output: Path):
    api_key = os.environ.get("FREEAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing GitHub Secret: FREEAI_API_KEY")

    endpoint = "https://api.free.ai/v1/image/edit/"

    prompt = """
EDIT THIS EXACT REFERENCE PHOTO. Preserve the real adult human hand itself:
preserve the same palm-up pose, wrist, thumb, all five fingers, fingernails,
skin pores, fingerprints, natural creases, lighting, camera perspective and
clean light background. Do NOT generate a new hand and do NOT change the hand
anatomy.

FIRST, COMPLETELY REMOVE/ERASE ALL EXISTING DRAWING, LANDSCAPE, TEMPLE,
MOUNTAIN, WRITING, SIGNATURE OR OTHER ARTWORK FROM THE SKIN. The final skin
must contain a NEW artwork only.

THEN DRAW A PREMIUM, DENSE HANDMADE DEVOTIONAL PALM ART DIRECTLY ON THE REAL
SKIN USING ONLY BLUE/INDIGO BALLPOINT PEN. The artwork must physically follow
the palm creases and finger contours and must look like thousands of real
ballpoint strokes: fine hatching, cross-hatching, contour lines, stippling and
tiny imperfect hand-drawn marks. Keep natural skin texture visible through
the ink. Cover almost the entire visible palm and fingers with connected
devotional artwork.

CRITICAL: EXACT CENTER OF THE PALM MUST CONTAIN A LARGE, UNMISTAKABLE,
HIGHLY RECOGNIZABLE HAND-DRAWN FIGURE OF LORD SHIVA / MAHADEV. This must be
an actual figure, NOT an Om symbol, NOT a trishul alone, and NOT a mountain.
Make Shiva's face clearly recognizable, with calm eyes, third eye, long matted
jata hair, crescent moon, snake around the neck, shoulders and torso, seated
in meditation. A clearly drawn trishul is beside him. Shiva should occupy
about 35-45% of the palm and be the dominant central subject.

Around Shiva, add secondary miniature devotional details only: a small
Himalayan temple, lamps, flowers, river/ghat, distant mountains, trees and
tiny pilgrims. These supporting details must remain much smaller than Shiva.

PHOTOREALISM IS ESSENTIAL. The result must look like a real macro photograph
of a real person's hand on which an artist spent hours drawing with a blue
ballpoint pen.

STRICTLY NO tattoo, henna, mehndi, decal, sticker, printed glove, digital
overlay, CGI, 3D render, vector art, marker, paint, watercolor, airbrush,
plastic skin, synthetic hand, blank fingers, extra fingers, missing fingers,
fused fingers, malformed anatomy, cropped fingertips, cropped wrist.

ABSOLUTELY ZERO READABLE TEXT. No Hindi, English, letters, numbers, names,
signature, handwriting, captions, labels, signs, banners, watermark or logo.
Only blue/indigo ballpoint ink. Keep the complete hand visible.
"""

    with REFERENCE.open("rb") as fh:
        files = {
            "image": (
                REFERENCE.name,
                fh,
                "image/jpeg",
            )
        }
        data = {
            "model": "qwen-image-edit",
            "prompt": prompt,
            "operation": "edit",
        }
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}"},
            files=files,
            data=data,
            timeout=600,
        )

    if not response.ok:
        raise RuntimeError(
            f"Free.ai Qwen-Image-Edit 2511 failed ({response.status_code}): "
            f"{response.text[:4000]}"
        )

    content_type = response.headers.get("content-type", "")
    if content_type.startswith("image/"):
        output.write_bytes(response.content)
    else:
        try:
            result = response.json()
        except Exception:
            raise RuntimeError(f"Free.ai returned non-image response: {response.text[:4000]}")

        image_url = (
            result.get("output_url")
            or result.get("image_url")
            or result.get("url")
            or result.get("share_url")
            or result.get("data", {}).get("output_url")
            or result.get("data", {}).get("image_url")
            or result.get("data", {}).get("url")
        )
        if not image_url:
            raise RuntimeError(f"Free.ai returned no image URL: {str(result)[:5000]}")

        image_response = requests.get(image_url, timeout=600)
        image_response.raise_for_status()
        output.write_bytes(image_response.content)

    if output.stat().st_size < 10000:
        raise RuntimeError("Free.ai returned an unexpectedly small image.")

    with Image.open(output) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        target_w, target_h = 864, 1536
        im.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (target_w, target_h), "white")
        canvas.paste(im, ((target_w - im.width) // 2, (target_h - im.height) // 2))
        canvas.save(output, "PNG")

    print("TEST: Qwen-Image-Edit 2511 via Free.ai completed with the reference hand preserved.")

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
