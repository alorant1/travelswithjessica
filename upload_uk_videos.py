#!/usr/bin/env python3
import pickle, json
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE = Path(__file__).parent
TOKEN = BASE / "youtube_token.pickle"
OUT = BASE / "youtube_uk_urls.json"

VIDEOS = [
    {"file": "posts/uk/videos/edinburgh_quidditch.mov", "post": "edinburgh", "title": "Edinburgh, Scotland — Quidditch practice"},
    {"file": "posts/uk/videos/fortw_falkirk_wheel.mov", "post": "fort-william", "title": "Fort William, Scotland — Falkirk Wheel"},
    {"file": "posts/uk/videos/fortw_wire_bridge.mov", "post": "fort-william", "title": "Fort William, Scotland — Wire bridge at Steall Falls"},
    {"file": "posts/uk/videos/fortw_hogwarts.mov", "post": "fort-william", "title": "Fort William, Scotland — Glenfinnan Viaduct (Hogwarts Express)"},
    {"file": "posts/uk/videos/skye_weavers.mov", "post": "isle-of-skye", "title": "Isle of Skye, Scotland — Skye Weavers"},
    {"file": "posts/uk/videos/skye_pub_music.mov", "post": "isle-of-skye", "title": "Isle of Skye, Scotland — Live pub music"},
]

with open(TOKEN, "rb") as f:
    creds = pickle.load(f)

youtube = build("youtube", "v3", credentials=creds)
results = []

for v in VIDEOS:
    path = BASE / v["file"]
    size_mb = path.stat().st_size // (1024*1024)
    print(f"\nUploading: {path.name} ({size_mb}MB)...")
    
    body = {
        "snippet": {"title": v["title"], "categoryId": "19"},
        "status": {"privacyStatus": "unlisted"}
    }
    
    media = MediaFileUpload(str(path), chunksize=5*1024*1024, resumable=True)
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    
    response = None
    while response is None:
        status, response = req.next_chunk()
        if status:
            pct = int(status.resumable_progress / status.total_size * 100)
            print(f"  {pct}%", end="  ", flush=True)
    
    url = f"https://www.youtube.com/watch?v={response['id']}"
    print(f"Done → {url}")
    results.append({"post": v["post"], "file": v["file"], "url": url, "id": response["id"]})

with open(OUT, "w") as f:
    json.dump(results, f, indent=2)

print(f"\nAll done! URLs saved to {OUT}")
for r in results:
    print(f"  [{r['post']}] {r['file'].split('/')[-1]} → {r['url']}")
