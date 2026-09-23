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
    token = os.environ.get("KAGGLE_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Missing GitHub Secret: KAGGLE_API_TOKEN")
    if not REFERENCE.exists():
        raise RuntimeError(f"Missing palm reference image: {REFERENCE}")

    # Image generation is executed inside Kaggle GPU.  Use a smaller public
    # SD-1.5-family model so the job is less likely to fail on Kaggle memory,
    # download size, or model-access restrictions.
    kernel_id = os.environ.get("KAGGLE_PALM_KERNEL_ID", "daya11/bhakti-palm-art-gpu").strip()
    job_dir = WORK / "kaggle_palm_kernel"
    output_dir = WORK / "kaggle_output"
    job_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    reference_url = (
        "https://raw.githubusercontent.com/"
        "kashavkaushik11-star/bhakti-palm-art-automation/main/palm_reference.jpg.jpg"
    )

    generator_code = f'''import subprocess
import sys
from pathlib import Path

# Keep the Kaggle environment predictable while using its preinstalled CUDA/PyTorch.
subprocess.run(
    [sys.executable, "-m", "pip", "install", "-q", "-U",
     "diffusers", "transformers", "accelerate", "safetensors", "pillow"],
    check=True,
)

import requests
import torch
from PIL import Image, ImageOps
from diffusers import StableDiffusionImg2ImgPipeline

REFERENCE_URL = {reference_url!r}
PROMPT = {prompt!r}
OUT = Path("/kaggle/working/palm_art.png")
REF = Path("/kaggle/working/palm_reference.jpg")
MODEL_ID = "Lykon/dreamshaper-8"

print("CUDA available:", torch.cuda.is_available())
if not torch.cuda.is_available():
    raise RuntimeError("Kaggle GPU is not available.")
print("Torch:", torch.__version__)
print("GPU:", torch.cuda.get_device_name(0))

r = requests.get(REFERENCE_URL, timeout=120)
r.raise_for_status()
REF.write_bytes(r.content)

init = ImageOps.exif_transpose(Image.open(REF).convert("RGB"))
init.thumbnail((512, 768), Image.Resampling.LANCZOS)
canvas = Image.new("RGB", (512, 768), "white")
canvas.paste(init, ((512-init.width)//2, (768-init.height)//2))
init = canvas

negative = (
    "tattoo, henna, mehndi, decal, sticker, printed glove, digital overlay, CGI, vector art, "
    "watercolor, thick marker, solid blue patches, sparse symbols, blank fingers, extra fingers, "
    "fused fingers, malformed hand, cropped fingertips, duplicate hands, watermark, logo, text, "
    "multicolored ink, generic landscape, landscape only"
)

print("Loading:", MODEL_ID)
pipe = StableDiffusionImg2ImgPipeline.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float16,
    variant="fp16",
    safety_checker=None,
)
pipe.enable_model_cpu_offload()

print("Generating Palm-Art...")
result = pipe(
    prompt=PROMPT,
    negative_prompt=negative,
    image=init,
    strength=0.45,
    guidance_scale=7.0,
    num_inference_steps=24,
).images[0]

result = ImageOps.exif_transpose(result).convert("RGB")
final = Image.new("RGB", (768, 1344), "white")
result.thumbnail((768, 1344), Image.Resampling.LANCZOS)
final.paste(result, ((768-result.width)//2, (1344-result.height)//2))
final.save(OUT, "PNG")
print("Saved:", OUT, OUT.stat().st_size)
'''

    metadata = {
        "id": kernel_id,
        "title": "Bhakti Palm Art GPU",
        "code_file": "generator.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": true,
        "enable_gpu": true,
        "enable_internet": true,
        "machine_shape": "NvidiaTeslaT4",
        "dataset_sources": [],
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": [],
    }

    (job_dir / "generator.py").write_text(generator_code, encoding="utf-8")
    (job_dir / "kernel-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

    print(f"Submitting Kaggle GPU image job: {kernel_id}")
    subprocess.run(["kaggle", "kernels", "push", "--accelerator", "NvidiaTeslaT4", "--timeout", "1200", "-p", str(job_dir)], check=True)

    for attempt in range(1, 61):
        status = subprocess.run(
            ["kaggle", "kernels", "status", kernel_id],
            text=True,
            capture_output=True,
        )
        combined = (status.stdout + "\n" + status.stderr).strip()
        print(combined)
        low = combined.lower()
        if "complete" in low or "completed" in low or "success" in low:
            break
        if "error" in low or "failed" in low:
            # Kaggle exposes the kernel log as an output file even for failed
            # runs. Download it here so the GitHub Action shows the real cause.
            if output_dir.exists():
                shutil.rmtree(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            debug = subprocess.run(
                ["kaggle", "kernels", "output", kernel_id, "-p", str(output_dir), "--force"],
                text=True,
                capture_output=True,
            )
            print("Kaggle output command:", debug.stdout, debug.stderr)
            for log_file in output_dir.rglob("*"):
                if log_file.is_file():
                    print(f"===== KAGGLE LOG: {log_file} =====")
                    try:
                        print(log_file.read_text(encoding="utf-8", errors="replace")[-20000:])
                    except Exception as exc:
                        print("Could not read log:", exc)
            raise RuntimeError(f"Kaggle Palm-Art job failed: {combined}")
        time.sleep(30)
    else:
        raise RuntimeError("Timed out waiting for Kaggle Palm-Art GPU job.")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["kaggle", "kernels", "output", kernel_id, "-p", str(output_dir), "--force"],
        check=True,
    )

    candidates = list(output_dir.rglob("palm_art.png"))
    if not candidates:
        raise RuntimeError("Kaggle completed but palm_art.png was not returned.")
    shutil.copy2(candidates[0], output)

    image = ImageOps.exif_transpose(Image.open(output).convert("RGB"))
    image.save(output, "PNG")
    if output.stat().st_size < 10000:
        raise RuntimeError("Kaggle returned an unexpectedly small image file.")
    print("Palm-Art image generated on Kaggle GPU and downloaded successfully.")

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
    """
    Generate a real AI image-to-video clip with Google Veo 3.1 Fast.
    The generated Palm-Art image is used as the first frame so the video
    keeps the same subject/style instead of using a simple FFmpeg zoom.
    """
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing GitHub Secret: GEMINI_API_KEY")

    model = os.environ.get("VEO_MODEL", "veo-3.1-fast-generate-preview").strip()

    try:
        from google import genai
        from google.genai import types
    except Exception as exc:
        raise RuntimeError(f"google-genai is required for Veo video generation: {exc}")

    print(f"Starting Google Veo image-to-video: {model}")

    client = genai.Client(api_key=key)
    image_bytes = image.read_bytes()
    if not image_bytes:
        raise RuntimeError("Generated Palm-Art image is empty.")

    source_image = types.Image(image_bytes=image_bytes, mime_type="image/png")

    config = types.GenerateVideosConfig(
        aspect_ratio="9:16",
        resolution="720p",
        duration_seconds=8,
        person_generation="allow_adult",
    )

    operation = client.models.generate_videos(
        model=model,
        prompt=prompt,
        image=source_image,
        config=config,
    )

    for attempt in range(1, 43):
        if operation.done:
            break
        print(f"Waiting for Veo video... {attempt}/42")
        time.sleep(10)
        operation = client.operations.get(operation)

    if not operation.done:
        raise RuntimeError("Veo video generation timed out after about 7 minutes.")

    try:
        generated_video = operation.response.generated_videos[0]
        client.files.download(file=generated_video.video, destination=str(output))
    except Exception as exc:
        raise RuntimeError(f"Veo finished but video download failed: {exc}")

    if not output.exists() or output.stat().st_size < 10000:
        raise RuntimeError("Veo returned an unexpectedly small video file.")

    print(f"Veo AI video generated successfully: {output}")

def make_video(generated_video: Path, music: Path, output: Path):
    """Finalize a 9:16 Reel and replace Veo audio with the project's devotional song."""
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,"
        "format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", str(generated_video),
        "-stream_loop", "-1", "-i", str(music),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-t", "8",
        "-vf", vf,
        "-r", "24",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "19",
        "-c:a", "aac",
        "-b:a", "160k",
        "-shortest",
        "-movflags", "+faststart",
        str(output),
    ]
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
    required = ["GEMINI_API_KEY", "KAGGLE_API_TOKEN"]
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
Create a premium, photorealistic cinematic 9:16 AI video from this exact Palm-Art image about {topic}.
Use the image as the opening frame and preserve the exact hand, five fingers, blue-ink artwork and sacred subject.

Make it feel like a real filmed action sequence, not a slideshow:
- one continuous shot with strong depth and parallax
- start with a close macro view of the complete palm
- camera smoothly pushes rapidly toward the main devotional artwork
- the tiny illustrated world inside the palm comes alive with subtle believable motion
- temple flags flutter, tiny lamps flicker, water flows, clouds drift and devotional figures move naturally where appropriate
- briefly travel through the illustrated scene for a dramatic reveal, then gently pull back toward the hand
- realistic lighting, shadows, lens depth, motion blur and cinematic camera movement
- no jump cuts, no text, no captions, no logos, no extra hands
- do not redraw, deform, melt or replace the hand
- keep the blue-ink Palm-Art identity crisp and recognizable throughout
- devotional, respectful, visually surprising and highly engaging for Facebook Reels and YouTube Shorts
- no dialogue and no generated background music; the final edit will use the project's devotional song
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
        print(json.dumps({"topic": topic, "music": music.name, "image": str(image), "video": str(video), "image_model": "Kaggle GPU SDXL image-to-image", "video_model": os.getenv("VEO_MODEL", "veo-3.1-fast-generate-preview"), "reference_used_as_style_input": True}, ensure_ascii=False))
        return

    fb = facebook_reel(video, title, description)
    yt = youtube_upload(video, title, description)
    print(json.dumps({"topic": topic, "facebook": fb, "youtube_video_id": yt, "music": music.name, "image_model": "Kaggle GPU SD-1.5-family reference-guided image", "video_model": "FFmpeg cinematic motion", "reference_used_as_style_input": True}, ensure_ascii=False))

if __name__ == "__main__":
    main()
