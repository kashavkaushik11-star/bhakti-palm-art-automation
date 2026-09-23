import json, os, subprocess
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work_cc"
WORK.mkdir(exist_ok=True)
TOPICS = ["amazing nature", "beautiful wildlife", "science facts", "space universe", "travel beautiful places", "interesting facts"]

def search(key, q):
    p = {"part":"snippet", "q":q, "type":"video", "videoLicense":"creativeCommon", "videoDuration":"short", "order":"relevance", "maxResults":25, "safeSearch":"strict"}
    r = requests.get("https://www.googleapis.com/youtube/v3/search", params={**p, "key":key}, timeout=60)
    r.raise_for_status()
    return r.json().get("items", [])

def details(key, vid):
    r = requests.get("https://www.googleapis.com/youtube/v3/videos", params={"part":"snippet,status,contentDetails", "id":vid, "key":key}, timeout=60)
    r.raise_for_status()
    x = r.json().get("items", [])
    return x[0] if x else None

def download(url, out):
    payload = {
        "url": url,
        "videoQuality": "1080",
        "downloadMode": "auto",
        "youtubeVideoCodec": "h264",
        "youtubeVideoContainer": "mp4",
        "alwaysProxy": True,
        "disableMetadata": False,
    }
    r = requests.post(
        "http://127.0.0.1:9000/",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        json=payload,
        timeout=180,
    )
    print("Cobalt HTTP:", r.status_code)
    print("Cobalt body:", r.text[:2000])
    r.raise_for_status()
    data = r.json()
    print("Cobalt response:", json.dumps(data, ensure_ascii=False))
    status = data.get("status")
    if status == "error":
        raise RuntimeError(json.dumps(data, ensure_ascii=False))
    if status == "picker":
        raise RuntimeError("Cobalt returned multiple items; refusing ambiguous download.")
    direct = data.get("url")
    if not direct:
        raise RuntimeError("Cobalt returned no download URL.")
    with requests.get(direct, stream=True, timeout=300) as dl:
        dl.raise_for_status()
        with open(out, "wb") as fh:
            for chunk in dl.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)

def reel(src, out):
    subprocess.run(["ffmpeg","-y","-i",str(src),"-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920","-t","60","-r","30","-c:v","libx264","-preset","veryfast","-crf","22","-c:a","aac","-b:a","128k","-movflags","+faststart",str(out)], check=True)

def metadata(key, title):
    prompt = ("Create metadata for a Hindi short video based on this source title: " + title +
              ". Return ONLY valid JSON with keys title, caption, description, tags. Hindi, concise, no false claims. "
              "Mention Creative Commons and include [SOURCE_URL] in description. tags must be an array of 8-12 short tags without #.")
    r = requests.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key="+key,
        json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.4,"maxOutputTokens":700}}, timeout=120)
    r.raise_for_status()
    raw = "".join(p.get("text","") for p in r.json()["candidates"][0]["content"]["parts"]).strip()
    fence = chr(96) * 3
    if raw.startswith(fence):
        raw = raw.replace(fence+"json","",1).replace(fence,"").strip()
    return json.loads(raw)

def main():
    key = os.environ["YOUTUBE_API_KEY"]
    gkey = os.environ.get("GEMINI_API_KEY","")
    topic = TOPICS[int(os.environ.get("TOPIC_INDEX","0")) % len(TOPICS)]
    candidates = []
    for item in search(key, topic):
        vid = item.get("id",{}).get("videoId")
        if not vid:
            continue
        d = details(key, vid)
        if d and d.get("status",{}).get("license") == "creativeCommon":
            candidates.append(d)

    if not candidates:
        raise RuntimeError("No suitable Creative Commons video found.")

    src = WORK / "source.mp4"
    out = WORK / "cc_reel.mp4"
    chosen = None
    errors = []

    for d in candidates[:10]:
        vid = d["id"]
        sn = d["snippet"]
        url = "https://www.youtube.com/watch?v=" + vid
        try:
            print("Trying CC video:", sn["title"], url)
            download(url, src)
            if src.exists() and src.stat().st_size > 10000:
                chosen = (d, url)
                break
        except Exception as exc:
            errors.append(f"{vid}: {exc}")
            if src.exists():
                src.unlink()
            print("Download failed; trying next CC candidate.")

    if not chosen:
        raise RuntimeError("YouTube download failed for all tested CC candidates.\n" + "\n".join(errors[-5:]))

    d, url = chosen
    sn = d["snippet"]
    reel(src, out)
    m = metadata(gkey, sn["title"]) if gkey else {"title":sn["title"],"caption":sn["title"],"description":"Creative Commons source video.","tags":["shorts","facts"]}
    desc = str(m["description"]).replace("[SOURCE_URL]",url) + "\n\nOriginal creator: " + sn["channelTitle"] + "\nSource: " + url + "\nLicense: Creative Commons (verify before publishing)."
    data = {"source_url":url,"source_title":sn["title"],"source_channel":sn["channelTitle"],"license":"creativeCommon","title":m["title"],"caption":m["caption"],"description":desc,"tags":m["tags"],"video":str(out)}
    (WORK/"metadata.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(data,ensure_ascii=False,indent=2))

if __name__ == "__main__":
    main()
