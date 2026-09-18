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
from gradio_client import Client, handle_file

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
        for key in ("path", "url"):
            if key in value and value[key]:
                p = Path(str(value[key]))
                if p.exists():
                    return p
    if isinstance(value, (list, tuple)):
        for item in value:
            found = _first_local_file(item)
            if found:
                return found
    return None

def generate_reference_guided_image(prompt: str, output: Path):
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Missing GitHub Secret: HF_TOKEN")
    last_error = None
    for attempt in range(3):
        try:
            client = Client("Qwen/Qwen-Image-Edit-2509", token=token)
            result = client.predict(
                images=[(handle_file(str(REFERENCE)), None)],
                prompt=prompt,
                seed=0,
                randomize_seed=True,
                true_guidance_scale=4.0,
                num_inference_steps=32,
                height=1920,
                width=1080,
                rewrite_prompt=False,
                num_images_per_prompt=1,
                api_name="/infer",
            )
            image_result = result[0] if isinstance(result, (tuple, list)) else result
            source = _first_local_file(image_result)
            if not source:
                raise RuntimeError(f"Qwen Image Edit returned an unexpected result: {image_result}")
            shutil.copyfile(source, output)
            print("Image generated with Qwen-Image-Edit-2509 using the Palm-Art reference image.")
            return
        except Exception as exc:
            last_error = str(exc)
            print(f"Qwen Image Edit attempt {attempt + 1}/3 failed: {last_error}")
            time.sleep(min(12 * (attempt + 1), 36))
    raise RuntimeError(f"Qwen-Image-Edit-2509 generation failed: {last_error}")

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
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Missing GitHub Secret: HF_TOKEN")
    negative = "flicker, morphing, deformation, distorted hand, extra fingers, missing fingers, melting ink, changing text, changing composition, blurry, low quality, watermark, camera shake, sudden zoom, new objects, duplicated objects"
    last_error = None
    for attempt in range(3):
        try:
            client = Client("kulkas2pintu/wan555", token=token)
            result = client.predict(
                input_image=handle_file(str(image)),
                last_image=None,
                prompt=prompt,
                steps=8,
                negative_prompt=negative,
                duration_seconds=4.5,
                guidance_scale=1.0,
                guidance_scale_2=1.0,
                seed=0,
                randomize_seed=True,
                quality=10,
                scheduler="UniPCMultistep",
                flow_shift=3.0,
                frame_multi=2,
                play_result_video=True,
                safe_mode=True,
                api_name="/generate_video",
            )
            video_result = result[0] if isinstance(result, (tuple, list)) else result
            source = _first_local_file(video_result)
            if not source:
                raise RuntimeError(f"Wan2.2 returned an unexpected result: {video_result}")
            shutil.copyfile(source, output)
            print("Video generated with Wan2.2 14B I2V Fast Preview.")
            return
        except Exception as exc:
            last_error = str(exc)
            print(f"Wan2.2 attempt {attempt + 1}/3 failed: {last_error}")
            time.sleep(min(15 * (attempt + 1), 45))
    raise RuntimeError(f"Wan2.2 I2V generation failed: {last_error}")

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
    required = ["HF_TOKEN"]
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

    image_prompt = f"""
Use the supplied Palm-Art reference image ONLY as a visual style, medium and composition reference.
Do NOT preserve the specific Kedarnath subject, landmarks, written text, or exact artwork from the reference.

Create a completely NEW vertical 9:16 macro photograph of a real human hand resting palm-up on clean white paper.
Keep the same Palm-Art concept: a real hand covered with extremely dense handmade blue/indigo ballpoint-pen artwork,
fine hatching, cross-hatching, stippling, miniature pilgrimage-map storytelling, realistic skin pores and palm creases,
natural nails, exactly five separated fingers, and 2-3 real blue/black ballpoint pens beside the hand.

NEW DEVOTIONAL SUBJECT FOR THIS CREATION: {topic}.
Build the entire tiny connected pilgrimage world around this theme: {scene}.
Make the chosen landmark and story recognizable but small and integrated into the hand drawing.
Every finger should contain substantial fresh artwork. Fill most visible skin with intricate blue pen linework.

The composition, objects, landmarks, people, scenery and linework must be newly invented for this creation.
The reference is for STYLE ONLY, not for copying content.
No tattoo, sticker, printed glove, CGI, vector art, sparse symbols, giant landmark, giant face,
extra fingers, malformed fingers, blank fingers, colored ink, watermark or large text.
Photorealistic macro photography, premium editorial detail, sharp ink strokes, realistic skin texture, dramatic but natural lighting.
"""
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
        print(json.dumps({"topic": topic, "music": music.name, "image": str(image), "video": str(video), "image_model": "Qwen/Qwen-Image-Edit-2509", "video_model": "Wan2.2 14B I2V Fast Preview", "reference_used_as_style_input": True}, ensure_ascii=False))
        return

    fb = facebook_reel(video, title, description)
    yt = youtube_upload(video, title, description)
    print(json.dumps({"topic": topic, "facebook": fb, "youtube_video_id": yt, "music": music.name, "image_model": "Qwen/Qwen-Image-Edit-2509", "video_model": "Wan2.2 14B I2V Fast Preview", "reference_used_as_style_input": True}, ensure_ascii=False))

if __name__ == "__main__":
    main()
