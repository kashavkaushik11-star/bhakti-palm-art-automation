import json
import os
import random
import shutil
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
    ("श्री कृष्ण — वृंदावन", "कृष्ण", "कृष्ण भक्ति", "krishna", "वृंदावन, यमुना घाट, गोवर्धन पर्वत, छोटी-छोटी कृष्ण मंदिरों की झलक, गायें, भक्त"),
    ("महादेव — तुंगनाथ", "शिव", "शिव भक्ति", "shiv", "तुंगनाथ मंदिर, हिमालय, बर्फीली चोटियाँ, पत्थर की सीढ़ियाँ, पहाड़ी झरना, तीर्थयात्री"),
    ("श्री हनुमान", "हनुमान", "हनुमान भक्ति", "hanuman", "हनुमान मंदिर, पर्वतीय वन, रामसेतु की प्रतीकात्मक झलक, भक्त और दीपक"),
    ("श्री राम — अयोध्या", "राम", "राम भक्ति", "ram", "अयोध्या, सरयू घाट, मंदिर, दीपों की पंक्तियाँ, रामायण से जुड़े छोटे दृश्य"),
    ("माँ वैष्णो देवी", "माता", "माता भक्ति", "mata", "वैष्णो देवी यात्रा मार्ग, पहाड़, सीढ़ियाँ, गुफा मंदिर, लाल ध्वज और भक्त"),
    ("केदारनाथ", "शिव", "केदारनाथ भक्ति", "shiv", "केदारनाथ मंदिर, हिमालय, मंदाकिनी, बर्फीली चोटियाँ, तीर्थयात्री"),
    ("काशी विश्वनाथ", "शिव", "काशी भक्ति", "shiv", "काशी विश्वनाथ मंदिर, गंगा घाट, नावें, दीपदान और संकरी प्राचीन गलियाँ"),
    ("जगन्नाथ पुरी", "जगन्नाथ", "जगन्नाथ भक्ति", "krishna", "जगन्नाथ मंदिर, रथ, समुद्र तट, भक्तों की यात्रा और मंदिर ध्वज"),
    ("सोमनाथ", "शिव", "सोमनाथ भक्ति", "shiv", "सोमनाथ मंदिर, अरब सागर, सूर्यास्त, तट और मंदिर की वास्तुकला"),
    ("बद्रीनाथ", "विष्णु", "बद्रीनाथ भक्ति", "krishna", "बद्रीनाथ मंदिर, अलकनंदा, हिमालय, तप्त कुंड और तीर्थयात्री"),
    ("रामायण — वनवास", "राम", "रामायण", "ram", "वन मार्ग, कुटिया, नदी, वन्यजीवन और श्री राम-सीता-लक्ष्मण की सूक्ष्म कथात्मक झलक"),
    ("महाभारत — कुरुक्षेत्र", "कृष्ण", "महाभारत", "krishna", "कुरुक्षेत्र, रथ, गीता उपदेश की प्रतीकात्मक झलक, युद्धभूमि और दूर खड़े योद्धा"),
    ("भगवद्गीता — श्री कृष्ण", "कृष्ण", "गीता ज्ञान", "krishna", "कुरुक्षेत्र का रथ, श्री कृष्ण और अर्जुन की सूक्ष्म दृश्यात्मक झलक, दिव्य प्रकाश"),
    ("गंगा आरती — हरिद्वार", "गंगा", "गंगा भक्ति", "mata", "हर की पौड़ी, गंगा आरती, दीप, घाट, भक्त और बहती गंगा"),
    ("नटराज — शिव तांडव", "शिव", "शिव तांडव", "shiv", "नटराज की दिव्य मुद्रा, कैलाश, डमरू, त्रिशूल, पर्वत और ऊर्जा की लहरें"),
    ("राधा-कृष्ण प्रेम", "राधा-कृष्ण", "राधा कृष्ण भक्ति", "krishna", "वृंदावन की गलियाँ, कुंज, यमुना, बांसुरी, मोर और राधा-कृष्ण की सूक्ष्म झलक"),
    ("गणेश जी", "गणेश", "गणेश भक्ति", "mata", "गणेश मंदिर, मोदक, दीप, पुष्प, छोटे भक्त और उत्सव का वातावरण"),
    ("नवरात्रि — माँ दुर्गा", "दुर्गा", "दुर्गा भक्ति", "mata", "माँ दुर्गा का मंदिर, सिंह, त्रिशूल, दीप, पुष्प और पर्वतीय मंदिर परिसर"),
    ("श्री श्याम बाबा", "श्याम", "श्याम भक्ति", "krishna", "खाटू श्याम मंदिर, ध्वज, भक्तों की यात्रा, पुष्प और मंदिर प्रांगण"),
    ("चार धाम यात्रा", "विष्णु", "चार धाम", "krishna", "हिमालयी तीर्थ मार्ग, मंदिर, नदियाँ, पर्वत, पुल और तीर्थयात्रियों की यात्रा"),
]

def choose_topic():
    if os.getenv("GITHUB_EVENT_NAME") == "schedule":
        now = datetime.now(timezone.utc)
        slot_map = {5: 0, 8: 1, 11: 2}
        slot = slot_map.get(now.hour, now.hour % 3)
        index = (now.date().toordinal() * 3 + slot) % len(TOPICS)
        return TOPICS[index]
    return random.choice(TOPICS)

def gemini_text(prompt: str) -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY not configured; using local caption fallback.")
    models = ["gemini-3.1-flash-lite", "gemini-3-flash-preview"]
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

def _first_local_file(value):
    if value is None:
        return None
    if isinstance(value, (str, Path)):
        p = Path(str(value))
        return p if p.exists() else None
    if isinstance(value, dict):
        # Gradio video outputs may be returned as {"video": "/tmp/...mp4"}
        # while image outputs may use {"path": "..."}.
        for key in ("path", "video", "file", "url"):
            if key in value and value[key]:
                p = Path(str(value[key]))
                if p.exists():
                    return p
        # Some APIs nest the actual file inside a result object.
        for item in value.values():
            found = _first_local_file(item)
            if found:
                return found
    if isinstance(value, (list, tuple)):
        for item in value:
            found = _first_local_file(item)
            if found:
                return found
    return None

def generate_reference_guided_image(prompt: str, output: Path):
    if not REFERENCE.exists():
        raise RuntimeError(f"Missing palm reference image: {REFERENCE}")

    # Verified new model test: Microsoft Mage-Flow-Edit-Turbo via public HF ZeroGPU.
    from gradio_client import Client, handle_file

    generation_prompt = f"""
Create a NEW photorealistic vertical macro photograph of a REAL adult human hand from the supplied
real-hand reference image. The hand must be the primary photographic subject BEFORE any artwork:
real skin, real anatomy, real palm creases, real fingerprints, realistic nails and natural
three-dimensional fingers. Do not render an illustrated, plastic, rubber, mannequin, CGI or
cartoon hand.

REQUESTED NEW ARTWORK:
{prompt}

Use the reference only as a structural/style guide. Preserve the real adult palm-up
hand geometry, complete wrist-to-fingertips framing and natural skin texture, but
redesign the artwork completely.

CRITICAL RESULT — REAL HAND FIRST:
Show ONE complete real adult human hand, palm facing camera, with the entire hand visible
from wrist through all five fingertips and thumb. Every finger must be anatomically realistic,
naturally separated, correctly proportioned, three-dimensional and fully inside the 9:16 frame.
The hand must occupy most of the image height. Preserve realistic joints, knuckles, tendons,
finger pads, nails, palm creases, pores and subtle skin variation.

The ENTIRE visible hand must contain artwork — not just the center of the palm.
Continuous blue/indigo ballpoint-pen linework must extend naturally across the wrist, lower palm,
upper palm, thumb, index finger, middle finger, ring finger, little finger and all the way toward
each fingertip. No large blank skin areas. The artwork density may vary for anatomy, but every
visible part of the hand should have connected handmade pen strokes.

The ink must look physically drawn directly onto the real skin surface. It must follow the
three-dimensional contours, wrinkles, folds and creases of the actual hand, with realistic
line thickness, pressure variation, tiny imperfections, hatching, cross-hatching, stippling
and contour strokes. NEVER make the artwork look like a flat image pasted, projected or
wrapped over the hand.

Put the requested Hindu devotional figure LARGE, clearly recognizable and visually dominant
in the CENTER of the palm, while the rest of the full hand remains covered with connected
supporting devotional line-art. The central figure is part of the pen drawing, not a separate
sticker or printed image. It must be the main focal
point, not a tiny figure hidden inside a landscape. Surround it with a dense miniature
devotional world connected by fine hand-drawn pen lines: temples, lamps, flowers,
river, trees, mountains, pilgrims and other subject-specific details. Use the
surrounding scenery to support the deity, never to replace it with a generic
mountain landscape.

Make the five fingers individually detailed with devotional line-art that remains
secondary to the central figure. Keep real skin pores, fingerprints, wrinkles and
natural nails visible between ink strokes. Keep a clean seamless white/light-gray
background with only 2-3 real blue/black ballpoint pens naturally placed beside the
wrist.

Ultra-photorealistic macro editorial photograph of a real human hand, realistic skin color,
natural pores and fingerprints, realistic nails and shadows, physically plausible lighting,
sharp handmade blue/indigo ballpoint ink detail, shallow but controlled photographic depth of
field, true skin texture visible between ink strokes. The hand must look like a real photograph
taken with a macro camera, not an AI illustration.

ABSOLUTELY NO readable writing anywhere in the image. No names, signatures, labels,
captions, words, letters, numbers, arrows, signs, logos, watermarks, calligraphy,
brand marks, notebook text, or decorative text. Do not invent a signature on the wrist
or palm.

DO NOT create a fake-looking hand, mannequin hand, plastic hand, rubber hand, wax hand,
CGI hand, illustrated hand, cartoon hand, deformed hand, tattoo, henna, mehndi, decal, sticker,
printed glove, digital overlay, flat texture overlay, CGI artwork, vector art, paint, watercolor,
marker, solid blue patches, sparse symbols,
blank fingers, mountain-only artwork, generic landscape-only artwork, extra fingers,
fused fingers, malformed hands, cropped fingertips, duplicate hands, circular plates,
frames, borders, paper props, notebooks, or multicolored ink.

Invent completely new devotional artwork and do not copy the exact deity drawing or
composition from the reference.
""".strip()

    client_kwargs = {}
    if os.getenv("HF_TOKEN"):
        client_kwargs["token"] = os.getenv("HF_TOKEN")
    client = Client("mage-flow-community/mage-flow", **client_kwargs)

    result = client.predict(
        generation_prompt,
        handle_file(str(REFERENCE)),
        "worst quality, low quality, blurry, bad anatomy, bad hands, extra fingers, "
        "fused fingers, cropped hand, tattoo, henna, mehndi, watermark, logo, text",
        4,
        1.0,
        1024,
        1024,
        1344,
        42,
        "turbo",
        api_name="/generate",
    )

    image_value = result[0] if isinstance(result, (list, tuple)) else result
    if isinstance(image_value, dict):
        image_value = image_value.get("path") or image_value.get("url") or image_value.get("image")

    if isinstance(image_value, str):
        src = Path(image_value)
        if not src.exists():
            raise RuntimeError(f"Mage-Flow returned an inaccessible image path: {image_value}")
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((768, 1344), Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", (768, 1344), "white")
            canvas.paste(im, ((768 - im.width)//2, (1344 - im.height)//2))
            canvas.save(output, format="PNG")
    else:
        try:
            im = ImageOps.exif_transpose(image_value).convert("RGB")
        except Exception as exc:
            raise RuntimeError(f"Mage-Flow returned an unsupported image result: {type(image_value)}") from exc
        im.thumbnail((768, 1344), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (768, 1344), "white")
        canvas.paste(im, ((768 - im.width)//2, (1344 - im.height)//2))
        canvas.save(output, format="PNG")

    if output.stat().st_size < 10000:
        raise RuntimeError("Mage-Flow returned an unexpectedly small image file.")

    print("Image generated with Mage-Flow-Edit-Turbo via the verified Hugging Face community ZeroGPU Space.")

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
    print("No music file found in music/. Using generated devotional instrumental fallback.")
    return make_fallback_devotional_music(category)

def generate_wan_video(image: Path, prompt: str, output: Path):
    # Reliable no-quota AI-video fallback: create a cinematic 9:16 motion reel
    # directly from the generated Palm-Art image. This avoids ZeroGPU/Space
    # availability and still produces a moving short suitable for Reels.
    last_error = None
    for attempt in range(2):
        try:
            cmd = [
                "ffmpeg", "-y", "-loop", "1", "-i", str(image),
                "-t", "8",
                "-vf",
                "scale=2160:3840:force_original_aspect_ratio=increase,"
                "crop=2160:3840,"
                "zoompan=z='min(zoom+0.0008,1.08)':"
                "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                "d=1:s=1080x1920:fps=30,"
                "eq=contrast=1.03:saturation=1.05",
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-pix_fmt", "yuv420p", str(output),
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            if output.stat().st_size < 10000:
                raise RuntimeError("FFmpeg returned an unexpectedly small video file.")
            print("Video created as a cinematic Palm-Art motion reel with FFmpeg.")
            return
        except Exception as exc:
            last_error = str(exc)
            print(f"Motion video attempt {attempt + 1}/2 failed: {last_error}")
            time.sleep(5)
    raise RuntimeError(f"Motion video generation failed: {last_error}")

def make_video(generated_video: Path, music: Path, output: Path):
    vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p"
    cmd = ["ffmpeg", "-y", "-i", str(generated_video), "-i", str(music), "-t", "10", "-vf", vf, "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(output)]
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

    topic, deity, category, music_category, scene = choose_topic()
    title = f"🙏 {topic} | Bhakti Palm Art"
    fallback_caption = f"{category} — {deity} की भक्ति से मन में शांति, शक्ति और विश्वास का प्रकाश।"
    try:
        generated_caption = gemini_text(f"Write one short, beautiful Hindi devotional caption for a social media Reel about {topic}. Keep it respectful, spiritual and concise. Return only the caption.")
    except Exception as exc:
        print(f"Gemini caption unavailable; using local caption: {exc}")
        generated_caption = fallback_caption
    description = f"{generated_caption}\n\n#Bhakti #SanatanDharma #{deity} #BhaktiReels #Shorts"

    # Build a compact subject prompt; Riverflow receives the reference image separately.
    # Isolated test trigger commit.
    deity_en = {
        "कृष्ण": "Lord Krishna playing flute",
        "राधा-कृष्ण": "Radha and Lord Krishna together",
        "शिव": "Lord Shiva / Mahadev",
        "हनुमान": "Lord Hanuman",
        "राम": "Lord Rama with Sita",
        "माता": "Goddess Vaishno Devi",
        "गंगा": "Goddess Ganga",
        "जगन्नाथ": "Lord Jagannath",
        "विष्णु": "Lord Vishnu",
        "दुर्गा": "Goddess Durga",
        "गणेश": "Lord Ganesha",
        "श्याम": "Khatu Shyam",
    }.get(deity, deity)
    image_prompt = (
        f"Devotional Palm Art featuring {deity_en}. "
        f"Create the main sacred figure clearly in the center of the palm, surrounded by "
        f"tiny connected devotional scenes inspired by {scene}. "
        f"The complete real hand must remain visible from wrist through all five fingertips."
    )
    motion_prompt = f"""
Animate this Palm-Art illustration as a premium devotional cinematic short about {topic}.
Preserve the exact hand, finger geometry, blue-ink artwork and composition of the generated image.
Create subtle believable motion inside the drawing: tiny pilgrims slowly walking, water gently flowing where present,
clouds drifting, temple flags moving softly, tiny lamps flickering and a very subtle divine glow.
Use a slow cinematic push-in with stable framing. Keep all ink lines crisp and coherent.
Do not redraw the hand or replace the artwork. Do not introduce new objects.
"""

    image = WORK / "palm_art.png"
    raw_video = WORK / "wan2_video.mp4"
    video = WORK / "bhakti_reel.mp4"

    generate_reference_guided_image(image_prompt, image)
    generate_wan_video(image, motion_prompt, raw_video)
    music = choose_music(music_category)
    make_video(raw_video, music, video)

    if test_only:
        print("TEST_ONLY=true: generated but NOT posted.")
        print(json.dumps({"topic": topic, "music": music.name, "image": str(image), "video": str(video), "image_model": "Mage-Flow-Edit-Turbo via Hugging Face community ZeroGPU Space (reference edit)", "video_model": "FFmpeg cinematic motion", "reference_used_as_style_input": True}, ensure_ascii=False))
        return

    fb = facebook_reel(video, title, description)
    yt = youtube_upload(video, title, description)
    print(json.dumps({"topic": topic, "facebook": fb, "youtube_video_id": yt, "music": music.name, "image_model": "Sourceful Riverflow V2.5 Fast via OpenRouter (reference edit)", "video_model": "FFmpeg cinematic motion", "reference_used_as_style_input": True}, ensure_ascii=False))

if __name__ == "__main__":
    main()
