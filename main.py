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

PALM_SCENES = {
    "krishna": "A continuous Vrindavan devotional panorama: Krishna playing flute, Radha, Yamuna river, cows, kadamba trees, Govardhan hills, ghats, small temples and many tiny devotees.",
    "shiv": "A continuous Shiva pilgrimage panorama: Mount Kailash, Shiva and Parvati, Ganga, Nandi, trishul, Kedarnath-style temple, snowy Himalayas, pilgrims, mountain paths and sacred ghats.",
    "hanuman": "A continuous Hanuman-Ram devotional panorama: Hanuman, Shri Ram, Ayodhya temple, forest, Sanjeevani mountain, river, bridge, tiny devotees and pilgrimage paths.",
    "ram": "A continuous Ramayana panorama: Ram, Sita, Lakshman, Hanuman, Ayodhya temple, forest, river, bridge, ghats, mountains, trees and tiny devotees.",
    "mata": "A continuous Mata Rani pilgrimage panorama: Durga/Mata Rani, mountain shrine, temple, Himalayan path, devotees, flags, bells, jyoti, valleys and sacred landscape.",
}


def gemini_text(prompt: str) -> str:
    key = os.environ["GEMINI_API_KEY"]
    models = ["gemini-2.5-flash-lite", "gemini-3-flash-preview"]
    last_error = None
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500}}
        for attempt in range(3):
            r = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=120)
            if r.ok:
                data = r.json()
                text = "".join(p.get("text", "") for p in data.get("candidates", [{}])[0].get("content", {}).get("parts", []))
                if text.strip():
                    return text.strip()
            else:
                last_error = r.text
                if r.status_code not in (429, 500, 502, 503, 504):
                    break
            time.sleep(min(5 * (attempt + 1), 15))
    raise RuntimeError(f"Gemini text generation failed: {last_error}")


def generate_flux_image(prompt: str, output: Path):
    token = os.environ["CLOUDFLARE_API_TOKEN"]
    account = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    last_error = None

    # FLUX.2 Dev is Cloudflare's newer high-fidelity model and supports portrait
    # dimensions through its multipart REST interface. Keep Schnell as a fallback.
    models = [
        ("@cf/black-forest-labs/flux-2-dev", 28),
        ("@cf/black-forest-labs/flux-1-schnell", 8),
    ]
    for model, steps in models:
        url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
        for attempt in range(3):
            try:
                if model.endswith("flux-2-dev"):
                    response = requests.post(
                        url,
                        headers={"Authorization": f"Bearer {token}"},
                        files={
                            "prompt": (None, prompt[:2048]),
                            "steps": (None, str(steps)),
                            "width": (None, "1024"),
                            "height": (None, "1536"),
                            "guidance": (None, "4.0"),
                        },
                        timeout=360,
                    )
                else:
                    response = requests.post(
                        url,
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                        json={"prompt": prompt[:2048], "steps": steps},
                        timeout=300,
                    )

                if response.ok:
                    data = response.json()
                    image = data.get("result", {}).get("image")
                    if image:
                        output.write_bytes(base64.b64decode(image))
                        print(f"Image generated with {model}")
                        return
                    last_error = str(data)
                else:
                    last_error = response.text
                    if response.status_code not in (429, 500, 502, 503, 504):
                        break
            except Exception as exc:
                last_error = str(exc)
            time.sleep(min(8 * (attempt + 1), 24))

    raise RuntimeError(f"Cloudflare FLUX image generation failed: {last_error}")


def make_fallback_devotional_music(category: str) -> Path:
    output = WORK / f"fallback_{category}.mp3"
    if output.exists() and output.stat().st_size > 0:
        return output
    filter_complex = (
        "sine=frequency=196:duration=10[a];"
        "sine=frequency=293.66:duration=10[b];"
        "sine=frequency=392:duration=10[c];"
        "[a][b][c]amix=inputs=3:duration=longest:weights=0.48 0.28 0.16,"
        "volume=0.55,afade=t=in:st=0:d=0.8,afade=t=out:st=8.8:d=1.2"
    )
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", filter_complex, "-t", "10", "-c:a", "libmp3lame", "-b:a", "128k", str(output)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    return output


def choose_music(category: str) -> Path:
    files = list(MUSIC.glob("*.mp3")) + list(MUSIC.glob("*.wav")) + list(MUSIC.glob("*.m4a"))
    if files:
        matches = [p for p in files if category.lower() in p.stem.lower()]
        return random.choice(matches or files)
    print("No licensed track found in music/. Using generated devotional instrumental fallback for this test run.")
    return make_fallback_devotional_music(category)


def make_video(image: Path, music: Path, output: Path):
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='min(zoom+0.0005,1.08)':d=300:s=1080x1920:fps=30,format=yuv420p"
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(image), "-i", str(music), "-t", "10", "-vf", vf, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(output)]
    subprocess.run(cmd, check=True)


def facebook_reel(video: Path, title: str, description: str):
    page = os.environ["FACEBOOK_PAGE_ID"].strip()
    token = os.environ["FACEBOOK_PAGE_ACCESS_TOKEN"].strip()
    version = os.getenv("FACEBOOK_GRAPH_VERSION", "v26.0")
    if token.startswith("OAuth "):
        token = token[6:].strip()

    verify = requests.get(
        f"https://graph.facebook.com/{version}/{page}",
        params={"fields": "id,name", "access_token": token},
        timeout=60,
    )
    if not verify.ok:
        raise RuntimeError(f"Facebook Page token/Page ID check failed ({verify.status_code}): {verify.text[:1200]}")

    start = requests.post(
        f"https://graph.facebook.com/{version}/{page}/video_reels",
        data={"upload_phase": "start", "access_token": token},
        timeout=60,
    )
    if not start.ok:
        raise RuntimeError(f"Facebook Reel start failed ({start.status_code}): {start.text[:2000]}")

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
    if not upload.ok:
        raise RuntimeError(f"Facebook Reel upload failed ({upload.status_code}): {upload.text[:2000]}")

    finish = requests.post(
        f"https://graph.facebook.com/{version}/{page}/video_reels",
        data={"upload_phase": "finish", "video_id": video_id, "video_state": "PUBLISHED", "title": title, "description": description, "access_token": token},
        timeout=60,
    )
    if not finish.ok:
        raise RuntimeError(f"Facebook Reel publish failed ({finish.status_code}): {finish.text[:2000]}")
    return finish.json()


def youtube_upload(video: Path, title: str, description: str):
    creds = Credentials(None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token", client_id=os.environ["YOUTUBE_CLIENT_ID"], client_secret=os.environ["YOUTUBE_CLIENT_SECRET"], scopes=["https://www.googleapis.com/auth/youtube.upload"])
    youtube = build("youtube", "v3", credentials=creds)
    body = {"snippet": {"title": title, "description": description, "categoryId": "22"}, "status": {"privacyStatus": "public"}}
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(str(video), mimetype="video/mp4", resumable=True))
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response.get("id")


def main():
    required = ["GEMINI_API_KEY", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID", "FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_ACCESS_TOKEN", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]
    missing = [x for x in required if not os.getenv(x)]
    if missing:
        raise RuntimeError("Missing GitHub Secrets: " + ", ".join(missing))

    topic, deity, message, category = random.choice(TOPICS)
    title = f"🙏 {topic} | भक्ति संदेश"

    text_prompt = f"Write a short devotional Hindi caption for a Reel about {topic}. Mention {deity}. Return only the caption."
    try:
        generated_caption = gemini_text(text_prompt)
    except Exception as exc:
        print(f"Gemini text unavailable; using local caption: {exc}")
        generated_caption = message

    description = f"{generated_caption}\n\n#Bhakti #SanatanDharma #{deity} #BhaktiReels #Shorts"
    scene = PALM_SCENES[category]

    image_prompt = f"""
Ultra-realistic professional macro photograph of ONE real human open palm and wrist, palm facing camera, portrait composition, hand centered and filling most of the frame.
The entire hand is a MASTERPIECE of extremely dense blue/indigo BALLPOINT PEN HAND-DRAWING physically drawn directly on the skin. Recreate the visual language of premium real palm-art reference photography: thousands of tiny pen strokes, fine cross-hatching, stippling, miniature line-art scenes, realistic pen pressure and imperfect handmade strokes.
{scene}
CRITICAL COMPOSITION: the drawing is ONE CONNECTED CONTINUOUS PANORAMA from wrist to palm and continuing naturally across ALL FIVE FINGERS and thumb. Cover about 90 percent of visible skin with connected artwork. Every finger must contain detailed landscape/architecture/people/foliage, not one isolated icon. The palm must be packed with layered tiny temples, mountains, rivers, trees, pilgrims, paths and devotional storytelling. Very little untouched skin.
The ink follows the natural creases and contours of the hand. Real skin pores, fine wrinkles and natural texture remain visible beneath the blue ink. Anatomically correct human hand, five fingers, realistic proportions.
White paper tabletop, a few real blue and black ballpoint pens around the edges, soft natural studio light, realistic shadows, shallow depth of field, extremely sharp macro detail, high-end photography.
ABSOLUTELY NOT: tattoo, sticker, printed graphic, digital painting, CGI, 3D object, floating deity, deity emerging from palm, isolated symbols, sparse icons, empty palm, blank fingers, colored paint, black ink, parchment, paper hand, collage, panels, borders, watermark, logo, large text.
The final image must look like a real photograph of an artist who spent hours drawing a dense devotional miniature world with a blue ballpoint pen directly on a person's hand.
""".strip()

    image = WORK / "palm_art.png"
    video = WORK / "bhakti_reel.mp4"
    generate_flux_image(image_prompt, image)

    music = choose_music(category)
    make_video(image, music, video)

    if os.getenv("TEST_ONLY", "false").lower() == "true":
        print("TEST_ONLY=true: image/video generated but NOT posted to Facebook or YouTube.")
        print(json.dumps({"topic": topic, "music": music.name, "image": str(image), "video": str(video)}, ensure_ascii=False))
        return

    fb = facebook_reel(video, title, description)
    yt = youtube_upload(video, title, description)
    print(json.dumps({"topic": topic, "music": music.name, "facebook": fb, "youtube_video_id": yt}, ensure_ascii=False))


if __name__ == "__main__":
    main()
