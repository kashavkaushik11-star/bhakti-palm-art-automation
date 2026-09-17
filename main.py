import json
import os
import random
import subprocess
import time
from pathlib import Path

import requests
from huggingface_hub import InferenceClient
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
    "krishna": "A continuous Vrindavan pilgrimage panorama: Yamuna river, ghats, Govardhan hills, kadamba trees, cows, tiny devotees, small temples and a very small Krishna playing flute as one detail inside the landscape.",
    "shiv": "A continuous Himalayan Shiva pilgrimage panorama: snowy mountains, Kailash, river, Kedarnath-style temple, mountain stairs and paths, Nandi, tiny pilgrims and a very small Shiva scene embedded inside the landscape.",
    "hanuman": "A continuous Ram-Hanuman pilgrimage panorama: Ayodhya temple, forest, river, bridge, Sanjeevani mountain, tiny pilgrims and a very small Hanuman scene embedded inside the landscape.",
    "ram": "A continuous Ramayana pilgrimage panorama: Ayodhya temple, forest, river, bridge, ghats, mountains, trees, tiny pilgrims and very small Ram-Sita-Lakshman-Hanuman scenes embedded inside the landscape.",
    "mata": "A continuous Mata Rani pilgrimage panorama: Himalayan valleys, mountain stairs, shrine, temple, flags, bells, jyoti, tiny devotees and a very small Mata Rani scene embedded inside the landscape.",
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


def generate_hf_image(prompt: str, output: Path):
    """Generate the palm artwork through Hugging Face Inference Providers."""
    token = os.environ["HF_TOKEN"]
    client = InferenceClient(api_key=token, provider="auto")
    negative = (
        "blank fingers, blank palm, sparse drawing, few icons, giant deity portrait, giant face, "
        "tattoo, printed skin, sticker, digital graphic, CGI, cartoon, 3D render, illustration, "
        "plastic hand, deformed hand, extra fingers, missing fingers, duplicated fingers, "
        "colored ink, red ink, green ink, text, logo, watermark, collage, poster, parchment, "
        "paper hand, flat vector art"
    )
    last_error = None
    for attempt in range(3):
        try:
            image = client.text_to_image(
                prompt=prompt,
                model="black-forest-labs/FLUX.1-Krea-dev",
                width=768,
                height=1360,
                guidance_scale=4.0,
                num_inference_steps=28,
                negative_prompt=negative,
            )
            image.save(output)
            print("Image generated with Hugging Face FLUX.1-Krea-dev")
            return
        except Exception as exc:
            last_error = str(exc)
            print(f"Hugging Face image attempt {attempt + 1}/3 failed: {last_error}")
            time.sleep(min(10 * (attempt + 1), 30))
    raise RuntimeError(f"Hugging Face palm image generation failed: {last_error}")


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
    verify = requests.get(f"https://graph.facebook.com/{version}/{page}", params={"fields": "id,name", "access_token": token}, timeout=60)
    if not verify.ok:
        raise RuntimeError(f"Facebook Page token/Page ID check failed ({verify.status_code}): {verify.text[:1200]}")
    start = requests.post(f"https://graph.facebook.com/{version}/{page}/video_reels", data={"upload_phase": "start", "access_token": token}, timeout=60)
    if not start.ok:
        raise RuntimeError(f"Facebook Reel start failed ({start.status_code}): {start.text[:2000]}")
    info = start.json()
    video_id = info["video_id"]
    upload_url = info.get("upload_url") or f"https://rupload.facebook.com/video-upload/{version}/{video_id}"
    size = video.stat().st_size
    with video.open("rb") as fh:
        upload = requests.post(upload_url, headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size), "Content-Type": "application/octet-stream"}, data=fh, timeout=300)
    if not upload.ok:
        raise RuntimeError(f"Facebook Reel upload failed ({upload.status_code}): {upload.text[:2000]}")
    finish = requests.post(f"https://graph.facebook.com/{version}/{page}/video_reels", data={"upload_phase": "finish", "video_id": video_id, "video_state": "PUBLISHED", "title": title, "description": description, "access_token": token}, timeout=60)
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
    required = ["GEMINI_API_KEY", "HF_TOKEN", "FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_ACCESS_TOKEN", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]
    missing = [x for x in required if not os.getenv(x)]
    if missing:
        raise RuntimeError("Missing GitHub Secrets: " + ", ".join(missing))

    topic, deity, message, category = random.choice(TOPICS)
    title = f"🙏 {topic} | भक्ति संदेश"
    try:
        generated_caption = gemini_text(f"Write a short devotional Hindi caption for a Reel about {topic}. Mention {deity}. Return only the caption.")
    except Exception as exc:
        print(f"Gemini text unavailable; using local caption: {exc}")
        generated_caption = message
    description = f"{generated_caption}\n\n#Bhakti #SanatanDharma #{deity} #BhaktiReels #Shorts"
    scene = PALM_SCENES[category]

    image_prompt = f"""
Create a photorealistic macro photograph of ONE real adult human hand, palm facing the camera, wrist fully visible, five fingers and thumb clearly separated, straight-on composition, vertical 9:16. The hand is resting on a clean white tabletop with two or three real blue or black ballpoint pens beside it.

The entire visible hand is a handmade blue-ballpoint-pen artwork. An expert artist has spent many hours drawing an extraordinarily dense miniature devotional pilgrimage map directly on the skin. The artwork begins on the wrist and continues without interruption through the palm, thumb and ALL FIVE FINGERS. Do not leave blank fingers or large blank skin areas.

Every finger and the thumb must contain connected fine blue-ink linework: tiny mountain ridges, contour lines, rivers, stairs, bridges, ghats, miniature temples, shrines, trees, animals, pilgrims, paths, clouds and architectural details. The palm must be densely filled too. Use hundreds of tiny elements, fine cross-hatching, stippling, parallel pen strokes, tiny buildings and natural variation in ballpoint pressure. The natural skin pores, creases and wrinkles must remain visible under the ink so the result looks physically drawn on living skin.

This is a continuous illustrated pilgrimage map, not separate icons. The map should visually flow from wrist to palm and then branch naturally into every finger. The dominant visual impression is dense blue/indigo ballpoint cartography covering almost the whole hand.

Theme for this image: {scene}

Any deity depiction must be tiny and embedded as one small scene inside the map. Never create a giant deity portrait or giant face.

Lighting and photography: premium realistic macro photography, soft natural daylight, realistic skin texture, realistic shadows, shallow depth of field, white tabletop, authentic physical pens near the hand. Blue and indigo ink only.

Do NOT create a tattoo, printed graphic, sticker, CGI render, cartoon, vector art, 3D hand, painted hand, plastic skin, paper hand, collage, poster, parchment, sparse symbols, isolated icons, giant central deity, blank fingers, blank palm, large text, logo or watermark.
""".strip()

    image = WORK / "palm_art.png"
    video = WORK / "bhakti_reel.mp4"
    generate_hf_image(image_prompt, image)
    music = choose_music(category)
    make_video(image, music, video)

    if os.getenv("TEST_ONLY", "false").lower() == "true":
        print("TEST_ONLY=true: image/video generated but NOT posted to Facebook or YouTube.")
        print(json.dumps({"topic": topic, "music": music.name, "image": str(image), "video": str(video), "image_model": "black-forest-labs/FLUX.1-Krea-dev"}, ensure_ascii=False))
        return

    fb = facebook_reel(video, title, description)
    yt = youtube_upload(video, title, description)
    print(json.dumps({"topic": topic, "music": music.name, "facebook": fb, "youtube_video_id": yt, "image_model": "black-forest-labs/FLUX.1-Krea-dev"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
