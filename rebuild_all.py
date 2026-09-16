#!/usr/bin/env python3
"""
rebuild_all.py — Full rebuild of all Travels with Jessica static pages.

Phases:
  1. Fetch all 121 WordPress posts (content + featured image)
  2. Parse each post into blocks (h2, p, photo, video)
  3. Download all images → local wp-content/uploads/ (served at same URLs)
  4. Rebuild every post's static HTML (preserving manual YouTube iframes)
  5. Rebuild every destination index.html
  6. Report completeness + failures

Run:  python3 rebuild_all.py
      python3 rebuild_all.py --images-only     (skip HTML rebuild, just download images)
      python3 rebuild_all.py --post 9884        (rebuild one post by WP ID)
"""

import requests, re, html as html_lib, json, os, sys, time
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
WP_API  = 'https://travel119239170.wpcomstaging.com/wp-json/wp/v2'
AUTH    = ('robynlorant@gmail.com', 'Vk66 wRAX ITQO RaF1 PVHa L2WU')
BASE    = Path('/Users/adamlorant/Documents/Claude/travelswithjessica')
PROD    = 'travelswithjessica.ca'
STAGING = 'travel119239170.wpcomstaging.com'

SESS = requests.Session()
SESS.auth = AUTH
SESS.headers.update({'User-Agent': 'Mozilla/5.0 rebuild-script/1.0'})

NAV_HTML = '''<nav>
  <div class="nav-inner">
    <a class="nav-logo" href="/">
      <img src="https://travelswithjessica.ca/wp-content/uploads/2022/09/My-Travel-Stories-copy-3.png" alt="Travels with Jessica logo">
      <div class="nav-logo-text">
        <span class="site-title">My Travel Stories</span>
        <span class="site-sub"></span>
      </div>
    </a>
    <ul>
      <li><a href="/">Home</a></li>
      <li><a href="/#posts">Blog</a></li>
      <li><a href="/#map">Map</a></li>
      <li><a href="/#contact">Contact</a></li>
    </ul>
  </div>
</nav>'''

# ── WP ID → relative file path (121 posts; V2 replaces V1 for SA) ─────────────
WP_TO_PATH = {
    # Thailand
    177:   'posts/thailand/bangkok.html',
    2066:  'posts/thailand/phuket.html',
    2089:  'posts/thailand/chiang-mai.html',
    2150:  'posts/thailand/mae-rim.html',
    2171:  'posts/thailand/samoeng-tai.html',
    # China
    2194:  'posts/china/hong-kong.html',
    # South Africa (V2 replaces V1; V1 IDs 2287 and 2361 are skipped)
    12208: 'posts/south-africa/cape-town.html',
    2314:  'posts/south-africa/clanwilliam.html',
    2343:  'posts/south-africa/stellenbosch.html',
    12198: 'posts/south-africa/plett.html',
    2378:  'posts/south-africa/oudtshoorn.html',
    2392:  'posts/south-africa/moses-kotane.html',
    # Canada BC
    2413:  'posts/canada-bc/pemberton.html',
    3546:  'posts/canada-bc/harrison.html',
    3561:  'posts/canada-bc/haida-gwaii.html',
    7365:  'posts/canada-bc/sunshine-coast.html',
    # Canada Maritimes / East
    3032:  'posts/canada-ns/hubbards.html',
    3044:  'posts/canada-ns/lunenburg.html',
    3576:  'posts/canada-ns/cape-split.html',
    3591:  'posts/canada-ns/cape-breton.html',
    7239:  'posts/canada-ns/prince-edward-island.html',
    7308:  'posts/canada-ns/bay-of-fundy.html',
    # Yukon
    10937: 'posts/yukon/whitehorse.html',
    # Hungary
    2452:  'posts/hungary-2016/budapest.html',
    # France
    2480:  'posts/france-2016/paris.html',
    2499:  'posts/france-2016/saint-remy.html',
    2524:  'posts/france-2016/provence.html',
    3874:  'posts/france-2016/bordeaux.html',
    3901:  'posts/france-2016/dordogne.html',
    # Belize 2017 (slug-to-path from rebuild_captions.py)
    2558:  'posts/belize-2017/tobacco-caye.html',
    2571:  'posts/belize-2017/south-water-caye.html',
    2583:  'posts/belize-2017/hopkins.html',
    # Belize 2025
    9884:  'posts/belize-2025/belize.html',
    # Japan
    2605:  'posts/japan-2017/tokyo.html',
    2650:  'posts/japan-2017/kyoto.html',
    2663:  'posts/japan-2017/hiroshima.html',
    2674:  'posts/japan-2017/hakone.html',
    # California
    2690:  'posts/california-2017/hollywood.html',
    # Mexico
    2713:  'posts/mexico-2017/puerto-vallarta.html',
    4641:  'posts/mexico/mexico-city.html',
    5234:  'posts/mexico/zihuantanejo.html',
    7886:  'posts/mexico/tulum.html',
    7949:  'posts/mexico/chichen-itza.html',
    7989:  'posts/mexico/valladolid.html',
    8061:  'posts/mexico/cancun.html',
    # Italy (all 15)
    2810:  'posts/italy/florence.html',
    3342:  'posts/italy/sicily.html',
    3658:  'posts/italy/ravenna.html',
    3677:  'posts/italy/bologna.html',
    3733:  'posts/italy/cinque-terre.html',
    3757:  'posts/italy/umbria.html',
    3785:  'posts/italy/puglia.html',
    3806:  'posts/italy/positano.html',
    3836:  'posts/italy/naples.html',
    3850:  'posts/italy/pompeii.html',
    9425:  'posts/italy/milan.html',
    9446:  'posts/italy/turin.html',
    9511:  'posts/italy/langhe.html',
    9630:  'posts/italy/genoa.html',
    9665:  'posts/italy/liguria.html',
    # Croatia (all 8)
    2925:  'posts/croatia-2018/dubrovnik.html',
    2934:  'posts/croatia-2018/mljet.html',
    2942:  'posts/croatia-2018/korcula.html',
    2952:  'posts/croatia-2018/stari-grad.html',
    2961:  'posts/croatia-2018/brac.html',
    2980:  'posts/croatia-2018/zadar.html',
    2992:  'posts/croatia-2018/trogir.html',
    3009:  'posts/croatia-2018/zagreb.html',
    # New York (2)
    3018:  'posts/new-york/new-york.html',
    7415:  'posts/new-york/brooklyn.html',
    # Morocco
    3064:  'posts/morocco/marrakech.html',
    3093:  'posts/morocco/ouarzazate.html',
    3106:  'posts/morocco/zagora.html',
    # Spain
    3124:  'posts/spain/barcelona.html',
    3145:  'posts/spain/costa-brava.html',
    # Finland
    3297:  'posts/finland/helsinki.html',
    3308:  'posts/finland/lapland.html',
    # Denmark
    3320:  'posts/denmark/copenhagen.html',
    # Vietnam — earlier trip
    5824:  'posts/vietnam/hanoi.html',
    5945:  'posts/vietnam/sa-pa.html',
    5977:  'posts/vietnam/ninh-binh.html',
    6015:  'posts/vietnam/ha-long-bay.html',
    6183:  'posts/vietnam/hue.html',
    6196:  'posts/vietnam/hoi-an.html',
    6333:  'posts/vietnam/saigon.html',
    # Cambodia & Vietnam 2023 trip
    6372:  'posts/cambodia-vietnam-2023/mekong-delta.html',
    6549:  'posts/cambodia-vietnam-2023/can-tho.html',
    6607:  'posts/cambodia-vietnam-2023/phnom-penh.html',
    6662:  'posts/cambodia-vietnam-2023/siem-reap.html',
    6718:  'posts/cambodia-vietnam-2023/angkor-wat.html',
    # Australia
    6802:  'posts/australia-2023/sydney.html',
    6865:  'posts/australia-2023/yulara.html',
    6925:  'posts/australia-2023/adelaide.html',
    6978:  'posts/australia-2023/flinders-ranges.html',
    7182:  'posts/australia-2023/queensland.html',
    # Hawaii
    4737:  'posts/hawaii/oahu.html',
    # Colorado
    10053: 'posts/colorado/vail.html',
    # UK (9)
    8252:  'posts/uk/london.html',
    8341:  'posts/uk/brighton.html',
    11117: 'posts/uk/oxford.html',
    11132: 'posts/uk/cotswolds.html',
    11183: 'posts/uk/york.html',
    11226: 'posts/uk/lake-district.html',
    11266: 'posts/uk/edinburgh.html',
    11323: 'posts/uk/fort-william.html',
    11370: 'posts/uk/isle-of-skye.html',
    # Turkey (10)
    8587:  'posts/turkey/istanbul.html',
    8708:  'posts/turkey/cappadocia.html',
    8783:  'posts/turkey/ephesus.html',
    8827:  'posts/turkey/pamukkale.html',
    8851:  'posts/turkey/antalya.html',
    8969:  'posts/turkey/kas.html',
    9026:  'posts/turkey/fethiye.html',
    9065:  'posts/turkey/sanliurfa.html',
    9169:  'posts/turkey/gobeklitepe.html',
    9208:  'posts/turkey/trabzon.html',
    # Peru (4)
    11762: 'posts/peru/lima.html',
    11829: 'posts/peru/cusco.html',
    11876: 'posts/peru/chinchero.html',
    11918: 'posts/peru/pisaq.html',
}

# Folder display names (used in breadcrumbs and destination index titles)
FOLDER_NAMES = {
    'posts/australia-2023':        'Australia',
    'posts/belize-2017':           'Belize 2017',
    'posts/belize-2025':           'Belize 2025',
    'posts/california-2017':       'California',
    'posts/cambodia-vietnam-2023': 'Cambodia & Vietnam',
    'posts/canada-bc':             'Canada (BC)',
    'posts/canada-ns':             'Canada (Maritimes)',
    'posts/china':                 'China',
    'posts/colorado':              'Colorado',
    'posts/croatia-2018':          'Croatia',
    'posts/denmark':               'Denmark',
    'posts/finland':               'Finland',
    'posts/france-2016':           'France',
    'posts/germany':               'Germany',
    'posts/hawaii':                'Hawaii',
    'posts/hungary-2016':          'Hungary',
    'posts/italy':                 'Italy',
    'posts/japan-2017':            'Japan',
    'posts/mexico-2017':           'Mexico (2017)',
    'posts/mexico':                'Mexico',
    'posts/morocco':               'Morocco',
    'posts/new-york':              'New York',
    'posts/peru':                  'Peru',
    'posts/south-africa':          'South Africa',
    'posts/spain':                 'Spain',
    'posts/thailand':              'Thailand',
    'posts/turkey':                'Turkey',
    'posts/uk':                    'United Kingdom',
    'posts/vietnam':               'Vietnam',
    'posts/yukon':                 'Yukon',
}

# ── URL helpers ───────────────────────────────────────────────────────────────

def norm_img_url(url):
    """Normalize any WordPress image URL to canonical travelswithjessica.ca URL."""
    url = html_lib.unescape(str(url or ''))
    if not url or 'wp-content' not in url:
        return None
    url = re.sub(r'https?://i\d+\.wp\.com/', 'https://', url)  # strip Jetpack CDN
    url = url.replace(STAGING, PROD)                             # staging → production
    url = re.sub(r'\?.*$', '', url)                             # strip query params
    url = re.sub(r'-\d+x\d+(\.[a-zA-Z]{2,5})$', r'\1', url)  # strip size suffix
    return url.strip() if url.startswith('http') else None

def staging_url(canonical):
    """Get staging download URL for a canonical image URL."""
    return canonical.replace(PROD, STAGING)

def local_path_for(canonical):
    """Local filesystem path for a canonical image URL."""
    parsed = urlparse(canonical)
    return BASE / parsed.path.lstrip('/')

def get_img_src(img_tag):
    """Extract best image URL from an img tag."""
    for attr in ('src', 'data-src', 'data-lazy-src', 'data-orig-file'):
        v = img_tag.get(attr, '')
        result = norm_img_url(v)
        if result:
            return result
    return None

# ── Image downloader ──────────────────────────────────────────────────────────

_downloaded = set()   # canonical URLs already downloaded this run
_failed_imgs = []

def download_image(canonical_url):
    """Download image to local wp-content/uploads/. Returns True on success."""
    if canonical_url in _downloaded:
        return True
    local = local_path_for(canonical_url)
    if local.exists() and local.stat().st_size > 0:
        _downloaded.add(canonical_url)
        return True
    local.parent.mkdir(parents=True, exist_ok=True)
    dl_url = staging_url(canonical_url)
    try:
        r = requests.get(dl_url, timeout=30, stream=True)
        if r.status_code == 200:
            with open(local, 'wb') as f:
                for chunk in r.iter_content(65536):
                    f.write(chunk)
            _downloaded.add(canonical_url)
            return True
        else:
            _failed_imgs.append((canonical_url, f'HTTP {r.status_code}'))
            return False
    except Exception as e:
        _failed_imgs.append((canonical_url, str(e)))
        return False

def download_images_bulk(urls, workers=12):
    """Download a list of image URLs in parallel."""
    unique = [u for u in dict.fromkeys(urls) if u]
    ok = fail = skip = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {}
        for u in unique:
            local = local_path_for(u)
            if local.exists() and local.stat().st_size > 0:
                skip += 1
                _downloaded.add(u)
                continue
            futures[ex.submit(download_image, u)] = u
        for fut in as_completed(futures):
            if fut.result():
                ok += 1
            else:
                fail += 1
    return ok, fail, skip

# ── Content parser ────────────────────────────────────────────────────────────

def extract_blocks(wp_html):
    """
    Parse Elementor/WordPress HTML into a list of blocks:
      ('h2', text)
      ('p',  inner_html)
      ('img', {'src': ..., 'alt': ..., 'caption': ...})
      ('video', iframe_html)
    Preserves sequence, deduplicates images/text.
    """
    soup = BeautifulSoup(wp_html, 'html.parser')
    blocks = []
    seen_imgs = set()
    seen_texts = set()

    def in_carousel(tag):
        return bool(tag.find_parent('div', class_='swiper-slide'))

    def walk(node):
        if isinstance(node, NavigableString):
            return
        if not isinstance(node, Tag):
            return
        tag = node.name
        classes = ' '.join(node.get('class', []))

        if tag in ('script', 'style', 'noscript'):
            return

        # Swiper carousel slide → one image with optional caption
        if tag == 'div' and 'swiper-slide' in classes:
            img = node.find('img')
            cap = node.find('figcaption')
            if img:
                src = get_img_src(img)
                if src and src not in seen_imgs:
                    seen_imgs.add(src)
                    blocks.append(('img', {
                        'src': src,
                        'alt': img.get('alt', '') or '',
                        'caption': cap.get_text(strip=True) if cap else ''
                    }))
            return

        # YouTube iframe
        if tag == 'iframe':
            src = node.get('src', '')
            if 'youtube.com/embed' in src:
                clean_src = re.sub(r'\?.*$', '', src)
                blocks.append(('video', str(node)))
            return

        # Standalone img (not in carousel)
        if tag == 'img' and not in_carousel(node):
            src = get_img_src(node)
            if src and src not in seen_imgs:
                seen_imgs.add(src)
                blocks.append(('img', {
                    'src': src,
                    'alt': node.get('alt', '') or '',
                    'caption': ''
                }))
            return

        # Headings
        if tag in ('h2', 'h3'):
            text = node.get_text(strip=True)
            if text and len(text) > 2 and text not in seen_texts:
                seen_texts.add(text)
                blocks.append(('h2', text))
            return

        # Paragraphs (not in carousel)
        if tag == 'p' and not in_carousel(node):
            # Skip if just contains an image
            if node.find('img') and not node.get_text(strip=True):
                for child in node.children:
                    walk(child)
                return
            text = node.get_text(strip=True)
            if text and len(text) > 2 and text not in seen_texts:
                seen_texts.add(text)
                blocks.append(('p', str(node.decode_contents())))
            return

        # Recurse into children
        for child in node.children:
            walk(child)

    walk(soup)
    return blocks

def render_blocks(blocks):
    """Render block list to HTML string."""
    parts = []
    for typ, content in blocks:
        if typ == 'h2':
            parts.append(f'\n  <h2>{html_lib.escape(content)}</h2>')
        elif typ == 'p':
            parts.append(f'  <p>{content}</p>')
        elif typ == 'img':
            src  = content['src']
            alt  = html_lib.escape(content.get('alt', ''))
            cap  = content.get('caption', '')
            if cap:
                parts.append(
                    f'  <div class="photo-block">\n'
                    f'    <img src="{src}" alt="{alt}" loading="lazy">\n'
                    f'    <p class="caption">{html_lib.escape(cap)}</p>\n'
                    f'  </div>'
                )
            else:
                parts.append(
                    f'  <div class="photo-block">\n'
                    f'    <img src="{src}" alt="{alt}" loading="lazy">\n'
                    f'  </div>'
                )
        elif typ == 'video':
            # Re-render iframe cleanly
            iframe_soup = BeautifulSoup(content, 'html.parser')
            iframe = iframe_soup.find('iframe')
            if iframe:
                src = iframe.get('src', '')
                title = iframe.get('title', 'YouTube video')
                parts.append(
                    f'  <div class="video-block">\n'
                    f'    <iframe src="{src}" title="{html_lib.escape(title)}" '
                    f'frameborder="0" allow="accelerometer; autoplay; clipboard-write; '
                    f'encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>\n'
                    f'  </div>'
                )
    return '\n\n'.join(parts)

# ── HTML builders ─────────────────────────────────────────────────────────────

def build_post_html(post_data, blocks, rel_path, preserved_yt=None):
    """Build a complete post HTML page."""
    title   = html_lib.unescape(post_data['title']['rendered'])
    folder  = str(Path(rel_path).parent)  # e.g. 'posts/italy'
    dest    = FOLDER_NAMES.get(folder, folder.split('/')[-1].replace('-', ' ').title())

    # Featured image
    fm_list = post_data.get('_embedded', {}).get('wp:featuredmedia', [])
    featured = fm_list[0].get('source_url', '') if fm_list else ''
    featured = norm_img_url(featured) or featured

    # Date
    date_str = post_data.get('date', '')[:10]
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        display_date = dt.strftime('%B %Y')
    except Exception:
        display_date = date_str

    # Content
    content_html = render_blocks(blocks)

    # Append preserved YouTube iframes not already in blocks
    if preserved_yt:
        existing_yt_srcs = {b[1] if b[0] == 'video' else '' for b in blocks}
        for yt_html in preserved_yt:
            yt_soup = BeautifulSoup(yt_html, 'html.parser')
            iframe = yt_soup.find('iframe')
            if iframe:
                src = iframe.get('src', '')
                if src not in existing_yt_srcs:
                    content_html += (
                        f'\n\n  <div class="video-block">\n'
                        f'    <iframe src="{src}" title="YouTube video" '
                        f'frameborder="0" allow="accelerometer; autoplay; clipboard-write; '
                        f'encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>\n'
                        f'  </div>'
                    )

    # Header image HTML
    header_img_html = ''
    if featured:
        header_img_html = f'  <img src="{featured}" alt="{html_lib.escape(title)}">'

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html_lib.escape(title)} — My Travel Stories</title>
  <link rel="stylesheet" href="../../css/style.css">
</head>
<body>

{NAV_HTML}

<div class="post-header">
{header_img_html}
  <div class="post-header-text">
    <h1>{html_lib.escape(title)}</h1>
  </div>
</div>

<article class="post-content">

  <nav class="breadcrumb" aria-label="breadcrumb">
    <a href="/">Home</a> <span>›</span> <a href="index.html">{html_lib.escape(dest)}</a> <span>›</span> <span>{html_lib.escape(title)}</span>
  </nav>

{content_html}

</article>

<footer>
  <p>© Travels with Jessica</p>
</footer>

</body>
</html>'''

def build_dest_index_html(folder, posts_info):
    """
    Build destination index.html listing all posts in the folder.
    posts_info: list of dict with keys: title, url (relative), featured_img, excerpt, date
    """
    dest_name = FOLDER_NAMES.get(folder, folder.split('/')[-1].replace('-', ' ').title())
    first_img = posts_info[0]['featured_img'] if posts_info else ''

    cards = []
    for p in posts_info:
        excerpt = p.get('excerpt', '')
        title_escaped = html_lib.escape(p['title'])
        excerpt_html = f'<p>{html_lib.escape(excerpt)}</p>' if excerpt else ''
        img_html = f'<img src="{p["featured_img"]}" alt="{title_escaped}">' if p.get('featured_img') else ''
        cards.append(f'''    <div class="country-card">
      {img_html}
      <div class="country-card-body">
        <h3><a href="{p["url"]}">{title_escaped}</a></h3>
        {excerpt_html}
        <a href="{p["url"]}" class="read-more">Read More »</a>
      </div>
    </div>''')

    cards_html = '\n\n'.join(cards)
    header_img_html = f'  <img src="{first_img}" alt="{html_lib.escape(dest_name)}">' if first_img else ''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html_lib.escape(dest_name)} — My Travel Stories</title>
  <link rel="stylesheet" href="../../css/style.css">
</head>
<body>

{NAV_HTML}

<div class="post-header">
{header_img_html}
  <div class="post-header-text">
    <h1>{html_lib.escape(dest_name)}</h1>
  </div>
</div>

<section class="post-content">

  <nav class="breadcrumb" aria-label="breadcrumb">
    <a href="/">Home</a> <span>›</span> <span>{html_lib.escape(dest_name)}</span>
  </nav>

  <div class="country-grid">

{cards_html}

  </div>

</section>

<footer>
  <p>© Travels with Jessica</p>
</footer>

</body>
</html>'''

# ── Existing file helpers ─────────────────────────────────────────────────────

def extract_existing_yt(html_path):
    """Extract YouTube iframe HTML strings from an existing static HTML file."""
    if not html_path.exists():
        return []
    content = html_path.read_text(encoding='utf-8')
    soup = BeautifulSoup(content, 'html.parser')
    return [str(iframe) for iframe in soup.find_all('iframe', src=lambda x: x and 'youtube.com/embed' in x)]

def extract_all_img_urls(html_path):
    """Extract all wp-content image URLs from an existing HTML file (canonical form)."""
    if not html_path.exists():
        return []
    content = html_path.read_text(encoding='utf-8')
    urls = re.findall(r'src="(https?://[^"]+wp-content/uploads/[^"]+)"', content)
    return [norm_img_url(u) for u in urls if norm_img_url(u)]

# ── Main orchestration ────────────────────────────────────────────────────────

def fetch_post(wp_id):
    """Fetch full post data from WordPress API including embedded media."""
    url = f'{WP_API}/posts/{wp_id}?_embed'
    r = SESS.get(url, timeout=60)
    r.raise_for_status()
    return r.json()

def clean_excerpt(wp_excerpt_html):
    """Strip HTML tags from WordPress excerpt."""
    soup = BeautifulSoup(wp_excerpt_html, 'html.parser')
    text = soup.get_text(strip=True)
    # Remove "[…]" or "Read more" artifacts
    text = re.sub(r'\[…\].*$', '…', text)
    text = re.sub(r'Read more.*$', '', text, flags=re.I)
    return text.strip()

def main():
    images_only = '--images-only' in sys.argv
    single_id   = None
    for arg in sys.argv[1:]:
        if arg.startswith('--post'):
            idx = sys.argv.index(arg)
            single_id = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else None

    target_map = {single_id: WP_TO_PATH[single_id]} if single_id and single_id in WP_TO_PATH else WP_TO_PATH

    print(f'\n{"="*60}')
    print(f'Travels with Jessica — Full Rebuild')
    print(f'  Posts to process: {len(target_map)}')
    print(f'  Images only: {images_only}')
    print(f'{"="*60}\n')

    # ── Phase 1: Collect all image URLs from existing HTML files ──────────────
    print('Phase 1: Scanning existing HTML for image URLs…')
    all_img_urls = set()
    for wp_id, rel_path in target_map.items():
        html_path = BASE / rel_path
        for u in extract_all_img_urls(html_path):
            all_img_urls.add(u)
    print(f'  Found {len(all_img_urls)} unique image URLs in existing HTML\n')

    # ── Phase 2: Fetch all posts from WordPress ───────────────────────────────
    print('Phase 2: Fetching posts from WordPress API…')
    posts = {}
    errors = []
    for i, (wp_id, rel_path) in enumerate(target_map.items(), 1):
        print(f'  [{i:3d}/{len(target_map)}] WP {wp_id}: {rel_path}', end=' ')
        try:
            data = fetch_post(wp_id)
            posts[wp_id] = data
            # Collect featured image URL
            fm_list = data.get('_embedded', {}).get('wp:featuredmedia', [])
            if fm_list:
                canonical = norm_img_url(fm_list[0].get('source_url', ''))
                if canonical:
                    all_img_urls.add(canonical)
            # Collect content image URLs
            content = data['content']['rendered']
            for url in re.findall(r'(?:src|data-src|data-lazy-src)="([^"]+wp-content[^"]+)"', content):
                canonical = norm_img_url(url)
                if canonical:
                    all_img_urls.add(canonical)
            print(f'✓ ({len(content):,} chars)')
        except Exception as e:
            print(f'✗ ERROR: {e}')
            errors.append((wp_id, rel_path, str(e)))
        time.sleep(0.1)  # be gentle with the API

    print(f'\n  Fetched {len(posts)}/{len(target_map)} posts')
    print(f'  Total unique image URLs: {len(all_img_urls)}\n')

    # ── Phase 3: Download all images ──────────────────────────────────────────
    print(f'Phase 3: Downloading {len(all_img_urls)} images (12 workers)…')
    ok, fail, skip = download_images_bulk(list(all_img_urls), workers=12)
    print(f'  Downloaded: {ok}  Failed: {fail}  Already had: {skip}\n')

    if images_only:
        print('Images-only mode — skipping HTML rebuild.\n')
        _report(errors, fail)
        return

    # ── Phase 4: Rebuild post HTML ────────────────────────────────────────────
    print('Phase 4: Rebuilding post HTML…')
    rebuilt = []
    skipped = []
    rebuild_errors = []

    # Group posts by folder for destination index building
    folder_posts = {}  # folder → list of post info dicts (for index pages)

    for wp_id, rel_path in target_map.items():
        if wp_id not in posts:
            rebuild_errors.append((wp_id, rel_path, 'fetch failed'))
            continue

        data = posts[wp_id]
        html_path = BASE / rel_path
        folder = str(Path(rel_path).parent)

        print(f'  {rel_path}…', end=' ')

        # Preserve existing YouTube iframes
        existing_yt = extract_existing_yt(html_path)

        # Parse WordPress blocks
        content = data['content']['rendered']
        blocks = extract_blocks(content)

        img_count   = sum(1 for t, _ in blocks if t == 'img')
        video_count = sum(1 for t, _ in blocks if t == 'video')

        # Build HTML
        try:
            new_html = build_post_html(data, blocks, rel_path, preserved_yt=existing_yt)
            html_path.parent.mkdir(parents=True, exist_ok=True)
            html_path.write_text(new_html, encoding='utf-8')
            rebuilt.append(rel_path)
            print(f'✓ ({img_count} imgs, {video_count + len(existing_yt)} videos, {len(blocks)} blocks)')
        except Exception as e:
            print(f'✗ ERROR: {e}')
            rebuild_errors.append((wp_id, rel_path, str(e)))
            continue

        # Collect info for destination index
        fm_list = data.get('_embedded', {}).get('wp:featuredmedia', [])
        featured = fm_list[0].get('source_url', '') if fm_list else ''
        featured = norm_img_url(featured) or featured
        excerpt = clean_excerpt(data.get('excerpt', {}).get('rendered', ''))
        title = html_lib.unescape(data['title']['rendered'])
        post_file = Path(rel_path).name

        folder_posts.setdefault(folder, []).append({
            'title':       title,
            'url':         post_file,
            'featured_img': featured,
            'excerpt':     excerpt,
            'wp_id':       wp_id,
        })

    print(f'\n  Rebuilt: {len(rebuilt)}  Errors: {len(rebuild_errors)}\n')

    # ── Phase 5: Rebuild destination index pages ──────────────────────────────
    print('Phase 5: Rebuilding destination index pages…')
    idx_built = 0
    for folder, posts_info in sorted(folder_posts.items()):
        index_path = BASE / folder / 'index.html'
        # Sort by WP ID (chronological order within destination)
        posts_info_sorted = sorted(posts_info, key=lambda p: p['wp_id'])
        try:
            idx_html = build_dest_index_html(folder, posts_info_sorted)
            index_path.write_text(idx_html, encoding='utf-8')
            print(f'  ✓ {folder}/index.html ({len(posts_info_sorted)} posts)')
            idx_built += 1
        except Exception as e:
            print(f'  ✗ {folder}/index.html: {e}')

    print(f'\n  Index pages built: {idx_built}\n')

    # ── Phase 6: Verify ───────────────────────────────────────────────────────
    print('Phase 6: Verifying local image files…')
    missing_local = []
    for url in sorted(all_img_urls):
        lp = local_path_for(url)
        if not lp.exists() or lp.stat().st_size == 0:
            missing_local.append(url)
    print(f'  Images verified: {len(all_img_urls) - len(missing_local)}/{len(all_img_urls)}')
    if missing_local:
        print(f'  Still missing: {len(missing_local)}')
        for u in missing_local[:10]:
            print(f'    {u}')
        if len(missing_local) > 10:
            print(f'    … and {len(missing_local) - 10} more')

    _report(errors + rebuild_errors, len(missing_local))

def _report(errors, missing_img_count):
    print(f'\n{"="*60}')
    print('SUMMARY')
    print(f'{"="*60}')
    if errors:
        print(f'\nFailed posts ({len(errors)}):')
        for wp_id, path, msg in errors:
            print(f'  WP {wp_id} {path}: {msg}')
    else:
        print('\nAll posts processed successfully.')
    if missing_img_count:
        print(f'\nMissing images: {missing_img_count} (check _failed_imgs list above)')
    if _failed_imgs:
        print(f'\nFailed image downloads ({len(_failed_imgs)}):')
        for url, reason in _failed_imgs[:20]:
            print(f'  {reason}: {url}')
    print()

if __name__ == '__main__':
    main()
