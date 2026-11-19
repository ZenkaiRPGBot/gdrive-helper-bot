import re
from config import SERIES_MAP

# Extended mapping to handle clean series names
SERIES_DISPLAY = {
    "MFS": "Mehmed: Fetihler Sultani",
    "MEHMED": "Mehmed: Fetihler Sultani",
    "KO": "Kurulus Osman",
    "KURULUS": "Kurulus Osman",
    "DE": "Dirilis Ertugrul",
    "ABS": "Alparslan: Büyük Selcuklu",
    "UBS": "Uyanis: Büyük Selcuklu",
    "KBS": "Kudüs Fatihi Selahaddin Eyyubi",
    "DESTAN": "Destan",
    "BARBAROS": "Barbaroslar",
    "TESKILAT": "Teskilat"
}

def is_uploader_request(text: str) -> bool:
    """Detects if message is meant for the uploader generator."""
    if not text:
        return False
    lower = text.lower()
    return "fastmotion.io" in lower or ".m3u8" in lower or "disk.yandex" in lower or "yadi.sk" in lower

def generate_uploader_data(text: str) -> dict:
    """Parses input message and builds uploader bot blocks + video captions."""
    # 1. Fastmotion link
    fm_match = re.search(r'https?://[^\s]+fastmotion\.io/[^\s]+/(?:360p|480p|720p|1080p)/video\.m3u8', text, re.IGNORECASE)
    if not fm_match:
        fm_match = re.search(r'https?://[^\s]+\.m3u8', text, re.IGNORECASE)
    fastmotion_raw = fm_match.group(0) if fm_match else ""

    # 2. Yandex link (for 1080p)
    yandex_match = re.search(r'https?://(?:disk\.yandex\.[^\s]+|yadi\.sk/[^\s]+)', text, re.IGNORECASE)
    yandex_link = yandex_match.group(0) if yandex_match else ""

    # 3. Optional Telegram post link for Google Drive link in 1080p caption
    tg_match = re.search(r'https?://t\.me/(?!kayitv\b|\+F0ifLckdLMs1YWZl\b)[a-zA-Z0-9_+/]+', text, re.IGNORECASE)
    gdrive_tg_link = tg_match.group(0) if tg_match else "https://t.me/mehmed_fetihler_sultani_kayitv/352"

    # 4. Extract Season, Episode, Bölüm, Series
    s_match = re.search(r'\bS(?:eason)?\s*0*(\d+)\b', text, re.IGNORECASE)
    season_num = int(s_match.group(1)) if s_match else 4
    
    e_match = re.search(r'\bE(?:pisode)?\s*0*(\d+)\b', text, re.IGNORECASE)
    ep_num = int(e_match.group(1)) if e_match else 9
    
    b_match = re.search(r'(?:Bölüm|Bolum)\s*0*(\d+)', text, re.IGNORECASE)
    bolum_str = f"Bölüm {b_match.group(1)}" if b_match else "Bölüm 92"

    # Match series acronym or title
    series_code = "MFS"
    series_name = "Mehmed: Fetihler Sultani"
    for code, full_name in SERIES_DISPLAY.items():
        if re.search(rf'\b{re.escape(code)}\b', text, re.IGNORECASE):
            series_code = code
            series_name = full_name
            break

    # Build 4 quality Fastmotion links
    fm_links = {}
    for q in ["360p", "480p", "720p", "1080p"]:
        if fastmotion_raw:
            fm_links[q] = re.sub(r'/(?:360p|480p|720p|1080p)/', f'/{q}/', fastmotion_raw)
        else:
            fm_links[q] = ""

    # 1080p link priority: Yandex first, fallback to Fastmotion
    link_1080p = yandex_link if yandex_link else fm_links.get("1080p", "")

    # Standard episode filename
    def make_filename(quality: str) -> str:
        return f"{series_code} S{season_num:02d} - E{ep_num:02d} - {bolum_str} - English Subtitles - {quality} - KayiTV.mp4"

    # Output Blocks
    gdrive_line = f"{make_filename('1080p')} | {link_1080p}"
    bot1_block = f"{make_filename('360p')} | {fm_links['360p']}\n{make_filename('480p')} | {fm_links['480p']}"
    bot2_block = f"{make_filename('720p')} | {fm_links['720p']}\n{make_filename('1080p')} | {link_1080p}"

    # Captions
    def make_caption(quality: str) -> str:
        is_1080 = (quality == "1080p")
        link_line = f'<a href="{gdrive_tg_link}">Google Drive Link</a>' if is_1080 else '<a href="https://t.me/+F0ifLckdLMs1YWZl">Download links Channel</a>'
        return (
            f"<b>{series_name}</b>\n\n"
            f"✯ ━━━━━✧━━━━━ ✯\n"
            f"SEASON {season_num} | EPISODE {ep_num:02d} | {quality}\n\n"
            f"• {bolum_str}\n\n"
            f"• English Subtitles\n\n"
            f"{link_line}\n\n"
            f"➤ Join Kayi TV channel 👇\n"
            f"https://t.me/kayitv"
        )

    # Clean plain captions (for copying directly to Telegram input box if needed)
    def make_plain_caption(quality: str) -> str:
        is_1080 = (quality == "1080p")
        link_md = f"[Google Drive Link]({gdrive_tg_link})" if is_1080 else "[Download links Channel](https://t.me/+F0ifLckdLMs1YWZl)"
        return (
            f"**{series_name}**\n\n"
            f"✯ ━━━━━✧━━━━━ ✯\n"
            f"SEASON {season_num} | EPISODE {ep_num:02d} | {quality}\n\n"
            f"• {bolum_str}\n\n"
            f"• English Subtitles\n\n"
            f"{link_md}\n\n"
            f"➤ Join Kayi TV channel 👇\n"
            f"https://t.me/kayitv"
        )

    return {
        "series_name": series_name,
        "gdrive_line": gdrive_line,
        "bot1_block": bot1_block,
        "bot2_block": bot2_block,
        "captions_html": {q: make_caption(q) for q in ["360p", "480p", "720p", "1080p"]},
        "captions_plain": {q: make_plain_caption(q) for q in ["360p", "480p", "720p", "1080p"]}
    }
