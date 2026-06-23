#!/usr/bin/env python3
"""
Upload all remaining videos and update HTML pages with YouTube embeds.
Run after verifying the YouTube channel (adaml6017@gmail.com) with a phone number.
"""
import json, time, pickle, re, os
from pathlib import Path
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE = Path(__file__).parent
TOKEN = BASE / "youtube_token.pickle"
VIDEOS_DIR = BASE / "videos"
RESULTS_FILE = BASE / "youtube_remaining_urls.json"

VIDEOS = [
    # Turkey
    {"key": "turkey_istanbul_BkeemJXg", "file": "turkey_istanbul_BkeemJXg.mov", "title": "Istanbul, Turkey — street scene", "page": "posts/turkey/istanbul.html"},
    {"key": "turkey_istanbul_UmdnM7nJ", "file": "turkey_istanbul_UmdnM7nJ.mov", "title": "Istanbul, Turkey — Bosphorus", "page": "posts/turkey/istanbul.html"},
    {"key": "turkey_istanbul_f8x2yNIM", "file": "turkey_istanbul_f8x2yNIM.mov", "title": "Istanbul, Turkey — Grand Bazaar", "page": "posts/turkey/istanbul.html"},
    {"key": "turkey_istanbul_zg79qVYS", "file": "turkey_istanbul_zg79qVYS.mov", "title": "Istanbul, Turkey — spice market", "page": "posts/turkey/istanbul.html"},
    {"key": "turkey_istanbul_24kIwoKr", "file": "turkey_istanbul_24kIwoKr.mov", "title": "Istanbul, Turkey — evening", "page": "posts/turkey/istanbul.html"},
    {"key": "turkey_cappadocia_VnPFrcH5", "file": "turkey_cappadocia_VnPFrcH5.mov", "title": "Cappadocia, Turkey — hot air balloon", "page": "posts/turkey/cappadocia.html"},
    {"key": "turkey_cappadocia_0Kg85ghi", "file": "turkey_cappadocia_0Kg85ghi.mov", "title": "Cappadocia, Turkey — valleys", "page": "posts/turkey/cappadocia.html"},
    {"key": "turkey_antalya_7DL3lCr6", "file": "turkey_antalya_7DL3lCr6.mov", "title": "Antalya, Turkey — old city", "page": "posts/turkey/antalya.html"},
    {"key": "turkey_antalya_VSmaHLjj", "file": "turkey_antalya_VSmaHLjj.mov", "title": "Antalya, Turkey — harbour", "page": "posts/turkey/antalya.html"},
    {"key": "turkey_antalya_xkdJyY4G", "file": "turkey_antalya_xkdJyY4G.mov", "title": "Antalya, Turkey — waterfall", "page": "posts/turkey/antalya.html"},
    {"key": "turkey_sanliurfa_A7HCL10l", "file": "turkey_sanliurfa_A7HCL10l.mov", "title": "Şanlıurfa, Turkey — bazaar", "page": "posts/turkey/sanliurfa.html"},
    {"key": "turkey_sanliurfa_d5kzKHsf", "file": "turkey_sanliurfa_d5kzKHsf.mov", "title": "Şanlıurfa, Turkey — sacred pool", "page": "posts/turkey/sanliurfa.html"},
    {"key": "turkey_sanliurfa_TEGCgKwF", "file": "turkey_sanliurfa_TEGCgKwF.mov", "title": "Şanlıurfa, Turkey — street", "page": "posts/turkey/sanliurfa.html"},
    {"key": "turkey_sanliurfa_Z55ptMgr", "file": "turkey_sanliurfa_Z55ptMgr.mov", "title": "Şanlıurfa, Turkey — carpet weaving", "page": "posts/turkey/sanliurfa.html"},
    {"key": "turkey_sanliurfa_rhrcsyk1", "file": "turkey_sanliurfa_rhrcsyk1.mov", "title": "Şanlıurfa, Turkey — copper market", "page": "posts/turkey/sanliurfa.html"},
    {"key": "turkey_sanliurfa_3DHw6LJQ", "file": "turkey_sanliurfa_3DHw6LJQ.mov", "title": "Şanlıurfa, Turkey — dervishes", "page": "posts/turkey/sanliurfa.html"},
    {"key": "turkey_trabzon_9SjtQR6Q", "file": "turkey_trabzon_9SjtQR6Q.mov", "title": "Trabzon, Turkey — Black Sea", "page": "posts/turkey/trabzon.html"},
    {"key": "turkey_trabzon_U6UrTEjv", "file": "turkey_trabzon_U6UrTEjv.mov", "title": "Trabzon, Turkey — market", "page": "posts/turkey/trabzon.html"},
    {"key": "turkey_trabzon_x71SZN8m", "file": "turkey_trabzon_x71SZN8m.mov", "title": "Trabzon, Turkey — tea gardens", "page": "posts/turkey/trabzon.html"},
    {"key": "turkey_trabzon_acLhCMSp", "file": "turkey_trabzon_acLhCMSp.mov", "title": "Trabzon, Turkey — Sumela Monastery", "page": "posts/turkey/trabzon.html"},
    {"key": "turkey_trabzon_WjXi2is2", "file": "turkey_trabzon_WjXi2is2.mov", "title": "Trabzon, Turkey — waterfall", "page": "posts/turkey/trabzon.html"},
    {"key": "turkey_trabzon_xtRYaqwb", "file": "turkey_trabzon_xtRYaqwb.mov", "title": "Trabzon, Turkey — valley", "page": "posts/turkey/trabzon.html"},
    # Italy Langhe winery
    {"key": "italy_langhe_winery", "file": "italy_langhe_winery.mov", "title": "Langhe, Italy — Monforte d'Alba winery fondue", "page": "posts/italy/langhe.html"},
    # UK London
    {"key": "uk_london_1PkeROuj", "file": "uk_london_1PkeROuj.mov", "title": "London, England — city scene", "page": "posts/uk/london.html"},
    {"key": "uk_london_fynO605u", "file": "uk_london_fynO605u.mov", "title": "London, England — street scene", "page": "posts/uk/london.html"},
    # Mexico 2024
    {"key": "mexico2024_tulum_F8YzodmR", "file": "mexico2024_tulum_F8YzodmR.mp4", "title": "Tulum, Mexico — cenote", "page": "posts/mexico-2024/tulum.html"},
    {"key": "mexico2024_chichen_Ct24Waio", "file": "mexico2024_chichen_Ct24Waio.mov", "title": "Chichén Itzá, Mexico — pyramid", "page": "posts/mexico-2024/chichen-itza.html"},
    {"key": "mexico2024_valladolid_jF6nroqu", "file": "mexico2024_valladolid_jF6nroqu.mov", "title": "Valladolid, Mexico — marquesitas", "page": "posts/mexico-2024/valladolid.html"},
    # Canada/US 2023
    {"key": "canada2023_pei_Oov5RVhW", "file": "canada2023_pei_Oov5RVhW.mp4", "title": "Prince Edward Island, Canada", "page": "posts/canada-us-2023/pei.html"},
    {"key": "canada2023_bayoffundy_3u7TOQrG", "file": "canada2023_bayoffundy_3u7TOQrG.mp4", "title": "Bay of Fundy, Nova Scotia — tides", "page": "posts/canada-us-2023/bay-of-fundy.html"},
    {"key": "canada2023_sunshinecoast_yrQkEjhu", "file": "canada2023_sunshinecoast_yrQkEjhu.mp4", "title": "Sunshine Coast, BC, Canada", "page": "posts/canada-us-2023/sunshine-coast.html"},
    {"key": "canada2023_utah_9WaTntIh", "file": "canada2023_utah_9WaTntIh.mp4", "title": "Utah — canyon", "page": "posts/canada-us-2023/utah.html"},
    {"key": "canada2023_utah_I2ztrHK0", "file": "canada2023_utah_I2ztrHK0.mp4", "title": "Utah — desert", "page": "posts/canada-us-2023/utah.html"},
    # Australia 2023
    {"key": "australia2023_sydney_mpx7d2vf", "file": "australia2023_sydney_mpx7d2vf.mp4", "title": "Sydney, Australia — harbour", "page": "posts/australia-2023/sydney.html"},
    {"key": "australia2023_yulara_703S7DlX", "file": "australia2023_yulara_703S7DlX.mp4", "title": "Yulara, Australia — Uluru", "page": "posts/australia-2023/yulara.html"},
    {"key": "australia2023_flinders_F2tAUTkc", "file": "australia2023_flinders_F2tAUTkc.mp4", "title": "Flinders Ranges, Australia", "page": "posts/australia-2023/flinders-ranges.html"},
    {"key": "australia2023_flinders_GBFiIwDq", "file": "australia2023_flinders_GBFiIwDq.mp4", "title": "Flinders Ranges, Australia — wildlife", "page": "posts/australia-2023/flinders-ranges.html"},
    {"key": "australia2023_flinders_fRATKfa7", "file": "australia2023_flinders_fRATKfa7.mp4", "title": "Flinders Ranges, Australia — landscape", "page": "posts/australia-2023/flinders-ranges.html"},
    {"key": "australia2023_flinders_EZgsbUoz", "file": "australia2023_flinders_EZgsbUoz.mp4", "title": "Flinders Ranges, Australia — gorge", "page": "posts/australia-2023/flinders-ranges.html"},
    {"key": "australia2023_flinders_fbRbChtO", "file": "australia2023_flinders_fbRbChtO.mp4", "title": "Flinders Ranges, Australia — sunset", "page": "posts/australia-2023/flinders-ranges.html"},
    {"key": "australia2023_queensland_gdcjSPQY", "file": "australia2023_queensland_gdcjSPQY.mp4", "title": "Queensland, Australia — reef", "page": "posts/australia-2023/queensland.html"},
    # Cambodia/Vietnam 2023
    {"key": "vietnam2023_mekong_Z5hGWRd5", "file": "vietnam2023_mekong_Z5hGWRd5.mp4", "title": "Mekong Delta, Vietnam", "page": "posts/cambodia-vietnam-2023/mekong-delta.html"},
    {"key": "vietnam2023_mekong_XWZKPk06", "file": "vietnam2023_mekong_XWZKPk06.mp4", "title": "Mekong Delta, Vietnam — boat", "page": "posts/cambodia-vietnam-2023/mekong-delta.html"},
    {"key": "vietnam2023_mekong_2KC0hj8X", "file": "vietnam2023_mekong_2KC0hj8X.mp4", "title": "Mekong Delta, Vietnam — market", "page": "posts/cambodia-vietnam-2023/mekong-delta.html"},
    {"key": "vietnam2023_mekong_dOOBaOb7", "file": "vietnam2023_mekong_dOOBaOb7.mov", "title": "Mekong Delta, Vietnam — river", "page": "posts/cambodia-vietnam-2023/mekong-delta.html"},
    {"key": "cambodia2023_siemreap_DNfqrVwM", "file": "cambodia2023_siemreap_DNfqrVwM.mp4", "title": "Siem Reap, Cambodia — temple", "page": "posts/cambodia-vietnam-2023/siem-reap.html"},
    {"key": "cambodia2023_siemreap_vseLMqbH", "file": "cambodia2023_siemreap_vseLMqbH.mp4", "title": "Siem Reap, Cambodia — market", "page": "posts/cambodia-vietnam-2023/siem-reap.html"},
    {"key": "cambodia2023_angkorwat_8Og2bbNS", "file": "cambodia2023_angkorwat_8Og2bbNS.mp4", "title": "Angkor Wat, Cambodia — temples", "page": "posts/cambodia-vietnam-2023/angkor-wat.html"},
    # France 2016
    {"key": "france2016_paris_0srAxii5", "file": "france2016_paris_0srAxii5.mov", "title": "Paris, France — street scene", "page": "posts/france-2016/paris.html"},
    {"key": "france2016_paris_7paZ87iL", "file": "france2016_paris_7paZ87iL.mov", "title": "Paris, France — Eiffel Tower", "page": "posts/france-2016/paris.html"},
    {"key": "france2016_paris_FNXR65Du", "file": "france2016_paris_FNXR65Du.mov", "title": "Paris, France — river", "page": "posts/france-2016/paris.html"},
    {"key": "france2016_paris_RMEcpyk0", "file": "france2016_paris_RMEcpyk0.mov", "title": "Paris, France — café", "page": "posts/france-2016/paris.html"},
    {"key": "france2016_provence_GR3YaDGg", "file": "france2016_provence_GR3YaDGg.mov", "title": "Provence, France — lavender", "page": "posts/france-2016/provence.html"},
    {"key": "france2016_provence_eGq0mtIN", "file": "france2016_provence_eGq0mtIN.mov", "title": "Provence, France — village", "page": "posts/france-2016/provence.html"},
    {"key": "france2016_provence_ot5FXjlU", "file": "france2016_provence_ot5FXjlU.mov", "title": "Provence, France — countryside", "page": "posts/france-2016/provence.html"},
]

VIDEO_BLOCK = '''  <div class="video-block">
    <iframe src="https://www.youtube.com/embed/{vid_id}" frameborder="0" allowfullscreen loading="lazy"></iframe>
  </div>'''


def authenticate():
    creds = None
    if TOKEN.exists():
        with open(TOKEN, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def upload(youtube, video):
    path = VIDEOS_DIR / video["file"]
    if not path.exists():
        print(f"  SKIP (missing): {path.name}")
        return None
    print(f"\nUploading: {path.name} ({path.stat().st_size // 1_000_000}MB)...")
    body = {
        "snippet": {"title": video["title"], "description": f'{video["title"]}. From the Travels with Jessica blog.', "categoryId": "19"},
        "status": {"privacyStatus": "unlisted"},
    }
    media = MediaFileUpload(str(path), chunksize=5 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  {int(status.progress() * 100)}%", end="\r")
    vid_id = response["id"]
    print(f"  Done → https://www.youtube.com/watch?v={vid_id}")
    return vid_id


def embed_video_in_page(page_path, vid_id):
    """Insert a video-block before </article> in the page."""
    full_path = BASE / page_path
    with open(full_path) as f:
        html = f.read()
    block = VIDEO_BLOCK.format(vid_id=vid_id)
    # Insert before post-nav div
    html = html.replace('  <div class="post-nav">', block + '\n\n  <div class="post-nav">', 1)
    with open(full_path, 'w') as f:
        f.write(html)


def main():
    # Load existing results
    results = {}
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE) as f:
            results = json.load(f)

    print("Authenticating...")
    youtube = authenticate()

    for video in VIDEOS:
        key = video["key"]
        if key in results:
            print(f"Skip (already uploaded): {key} → {results[key]['youtube_id']}")
            continue
        vid_id = upload(youtube, video)
        if vid_id:
            results[key] = {"youtube_id": vid_id, "youtube_url": f"https://www.youtube.com/watch?v={vid_id}", "page": video["page"]}
            with open(RESULTS_FILE, "w") as f:
                json.dump(results, f, indent=2)
            embed_video_in_page(video["page"], vid_id)
            time.sleep(2)

    print(f"\nDone! {len(results)} videos uploaded.")


if __name__ == "__main__":
    main()
