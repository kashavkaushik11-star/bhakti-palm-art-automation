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
from huggingface_hub import InferenceClient

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work"
MUSIC = ROOT / "music"
REFERENCE = ROOT / "palm_reference.jpg.jpg"  # Human visual reference only; NEVER sent to the model.
WORK.mkdir(exist_ok=True)

TOPICS = [
    ("श्री कृष्ण", "कृष्ण", "हे कृष्ण, अपने भक्तों के जीवन में प्रेम, शांति और भक्ति का प्रकाश भर दो।", "krishna"),
    ("महादेव", "शिव", "हर हर महादेव। महादेव की भक्ति मन को शक्ति, धैर्य और शांति देती है।", "shiv"),
    ("श्री हनुमान", "हनुमान", "जय बजरंगबली। श्री हनुमान की भक्ति साहस और विश्वास की प्रेरणा देती है।", "hanuman"),
    ("श्री राम", "राम", "श्री राम का नाम मन को मर्यादा, शांति और सत्य के मार्ग की याद दिलाता है।", "ram"),
    ("माता रानी", "माता", "जय माता दी। माँ की भक्ति में विश्वास, शक्ति और करुणा का भाव है।", "mata"),
]

PALM_SCENES = {
    "krishna": "Vrindavan and Mathura pilgrimage, Yamuna river, ancient ghats, Govardhan hill, cows, trees, tiny Krishna temples and many tiny pilgrims",
    "shiv": "Tungnath Temple pilgrimage in the Garhwal Himalayas, the ancient stone Tungnath Shiva temple as a SMALL detailed landmark, steep Himalayan trail, snowy mountain peaks, alpine meadows, rocky slopes, winding mountain stream, stone steps, tiny pilgrims carrying backpacks, small bells and distant mountain shrines",
    "hanuman": "Ayodhya and Ram-Hanuman pilgrimage, river, forest, stone bridge, distant mountain, tiny temples and many tiny pilgrims",
    "ram": "Ayodhya and Ramayana pilgrimage, Sarayu river, ghats, forest paths, stone bridge, tiny temples, villages and many tiny pilgrims",
    "mata": "Himalayan Mata Rani pilgrimage, steep mountain valley, long stairway, shrine, temple flags, rocky terrain and many tiny devotees",
}


def gemini_text(prompt: str) -> str:
    key = os.environ["GEMINI_API_KEY"]
    models = ["gemini-2.5-flash-lite", "gemini-3-flash-preview"]
    last_error = None
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500}}
        for attempt in range(3):
            try:
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
            except Exception as exc:
                last_error = str(exc)
            time.sleep(min(5 * (attempt + 1), 15))
    raise RuntimeError(f"Gemini text generation failed: {last_error}")


def generate_qwen_image(prompt: str, output: Path):
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Missing GitHub Secret: HF_TOKEN")

    client = InferenceClient(api_key=token, provider="auto")
    last_error = None
    for attempt in range(3):
        try:
            result = client.text_to_image(
                prompt=prompt,
                model="Qwen/Qwen-Image",
                width=768,
                height=1360,
            )
            result.save(output)
            print("Image generated with Hugging Face Qwen/Qwen-Image (text-to-image, no reference image input).")
            return
        except Exception as exc:
            last_error = str(exc)
            print(f"Qwen-Image attempt {attempt + 1}/3 failed: {last_error}")
            time.sleep(min(10 * (attempt + 1), 30))
    raise RuntimeError(f"Qwen/Qwen-Image generation failed: {last_error}")


def make_fallback_devotional_music(category: str) -> Path:
    output = WORK / f"fallback_{category}.mp3"
    if output.exists() and output.stat().st_size > 0:
        return output
    filter_complex = "sine=frequency=196:duration=10[a];sine=frequency=293.66:duration=10[b];sine=frequency=392:duration=10[c];[a][b][c]amix=inputs=3:duration=longest:weights=0.48 0.28 0.16,volume=0.55,afade=t=in:st=0:d=0.8,afade=t=out:st=8.8:d=1.2"
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
    test_only = os.getenv("TEST_ONLY", "false").lower() == "true"
    required = ["GEMINI_API_KEY", "HF_TOKEN"]
    if not test_only:
        required += ["FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_ACCESS_TOKEN", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]
    missing = [x for x in required if not os.getenv(x)]
    if missing:
        raise RuntimeError("Missing GitHub Secrets: " + ", ".join(missing))

    # For the current visual benchmark, always test the requested Tungnath scene.
    if test_only:
        topic, deity, message, category = ("तुंगनाथ मंदिर", "शिव", "तुंगनाथ महादेव के दिव्य हिमालयी धाम की भक्ति मन में शांति और शक्ति भरती है।", "shiv")
    else:
        topic, deity, message, category = random.choice(TOPICS)

    title = f"🙏 {topic} | भक्ति संदेश"
    try:
        generated_caption = gemini_text(f"Write a short devotional Hindi caption for a Reel about {topic}. Mention {deity}. Return only the caption.")
    except Exception as exc:
        print(f"Gemini text unavailable; using local caption: {exc}")
        generated_caption = message
    description = f"{generated_caption}\n\n#Bhakti #SanatanDharma #{deity} #BhaktiReels #Shorts"
    scene = PALM_SCENES[category]

    image_prompt = f"""Create a COMPLETELY NEW photorealistic macro photograph of a real human hand resting palm-up on clean white paper, with realistic skin pores, palm creases, wrist, natural nails and exactly five separated fingers.

Create an ORIGINAL dense handmade blue/indigo ballpoint-pen artwork directly on the skin. Cover about 90 percent of the visible skin and continue detailed artwork across the palm, wrist, thumb and ALL five fingers almost to every fingertip. Every finger must contain substantial fine artwork and must not be blank.

The drawing is a completely new miniature pilgrimage world for this scene: {scene}. Include the Tungnath Temple as one SMALL but recognizable ancient stone Shiva temple landmark, surrounded by Himalayan terrain, trails and tiny pilgrims. Keep the temple proportional and integrated into the dense map instead of making it huge.

Use extremely fine blue/indigo ballpoint hatching, cross-hatching, stippling, contour lines and tiny handmade linework. Pack many small details across the entire hand: mountain contours, streams, stone paths, steps, tiny shrines, small trees, rocks, animals and many tiny pilgrims.

Place 2-3 real blue/black ballpoint pens beside the hand on white paper. Make the final result look like a genuine macro photograph of an expert artist drawing a NEW Tungnath pilgrimage map directly on real skin.

IMPORTANT: Generate a new image from text only. The repository reference image is NOT an input and must NOT be copied or reconstructed. Do not reproduce its exact hand artwork, landmarks, text, signs, composition, layout, or linework. The reference is only a human visual target for the general medium: dense blue ballpoint pilgrimage art on a real hand. Invent a fresh Tungnath-specific artwork.

Do NOT make it a tattoo, sticker, printed glove, CGI render, cartoon, vector art or sparse symbols. Do NOT create extra or malformed fingers, giant temple, giant faces, colored ink, logos, watermarks or large text. No blank fingers."""

    image = WORK / "palm_art.png"
    video = WORK / "bhakti_reel.mp4"
    generate_qwen_image(image_prompt, image)
    music = choose_music(category)
    make_video(image, music, video)

    if test_only:
        print("TEST_ONLY=true: image/video generated but NOT posted to Facebook or YouTube.")
        print(json.dumps({"topic": topic, "music": music.name, "image": str(image), "video": str(video), "image_model": "Qwen/Qwen-Image", "reference_used_as_input": False}, ensure_ascii=False))
        return

    fb = facebook_reel(video, title, description)
    yt = youtube_upload(video, title, description)
    print(json.dumps({"topic": topic, "facebook": fb, "youtube_video_id": yt, "music": music.name, "image_model": "Qwen/Qwen-Image", "reference_used_as_input": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
