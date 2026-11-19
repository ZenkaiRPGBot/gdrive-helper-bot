import re
import aiohttp
from config import SERIES_MAP

# Pre-compiled regex patterns for maximum execution speed
RE_GDRIVE_UC = re.compile(r'drive\.google\.com/uc\?[^ \n\r\t]*id=([-\w]{25,})')
RE_GDRIVE_FILE = re.compile(r'drive\.google\.com/file/d/([-\w]{25,})')
RE_GDRIVE_OPEN = re.compile(r'drive\.google\.com/open\?[^ \n\r\t]*id=([-\w]{25,})')
RE_GDRIVE_USERCONTENT = re.compile(r'drive\.usercontent\.google\.com/download\?[^ \n\r\t]*id=([-\w]{25,})')

RE_QUALITY = re.compile(r'\b(4K|2160p|1080p|720p|480p|360p)\b', re.IGNORECASE)
RE_SEASON = re.compile(r'\bS(?:eason)?\s*0*(\d+)\b', re.IGNORECASE)
RE_EPISODE = re.compile(r'\bE(?:pisode)?\s*0*(\d+)\b', re.IGNORECASE)
RE_BOLUM = re.compile(r'(?:Bölüm|Bolum)\s*0*(\d+)', re.IGNORECASE)
RE_SIZE_STR = re.compile(r'^([\d.]+)\s*([GMKB])(?:B)?$', re.IGNORECASE)
RE_FILENAME = re.compile(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';]+)["\']?', re.IGNORECASE)
RE_NAME_SIZE = re.compile(r'class=["\']uc-name-size["\'][^>]*>.*?<a[^>]*>(.*?)</a>\s*\((.*?)\)', re.DOTALL)
RE_SPLIT_TITLE = re.compile(r'\bS\d+| - ', re.IGNORECASE)

GDRIVE_PATTERNS = [
    RE_GDRIVE_UC,
    RE_GDRIVE_FILE,
    RE_GDRIVE_OPEN,
    RE_GDRIVE_USERCONTENT
]

def extract_gdrive_ids(text: str) -> list[str]:
    """Finds all unique Google Drive file IDs instantly using pre-compiled regex."""
    found_ids = []
    for pattern in GDRIVE_PATTERNS:
        for m in pattern.findall(text):
            if m not in found_ids:
                found_ids.append(m)
    return found_ids

def normalize_size_str(raw_size: str) -> str:
    """Normalizes size units like '3.0G' or '750M' to '3.0 GB' or '750 MB'."""
    raw_size = raw_size.strip()
    m = RE_SIZE_STR.match(raw_size)
    if m:
        num, unit = m.group(1), m.group(2).upper()
        return f"{num} {unit}B"
    return raw_size

def format_bytes(size_bytes: int) -> str:
    """Formats raw bytes into human-readable MB / GB string."""
    if size_bytes >= 1024**3:
        return f"{size_bytes / (1024**3):.1f} GB"
    elif size_bytes >= 1024**2:
        return f"{size_bytes / (1024**2):.1f} MB"
    else:
        return f"{size_bytes / 1024:.1f} KB"

async def fetch_gdrive_info(session: aiohttp.ClientSession, file_id: str) -> dict:
    """
    High-speed Google Drive metadata resolver.
    Reads minimal chunks from stream for instant extraction without downloading full payload.
    """
    url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&authuser=0"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Encoding": "identity"
    }
    
    info = {"size": None, "name": None}
    try:
        async with session.get(url, headers=headers, ssl=False, timeout=aiohttp.ClientTimeout(total=5, connect=2)) as resp:
            content_type = resp.headers.get("Content-Type", "")
            content_length = resp.headers.get("Content-Length")
            content_disposition = resp.headers.get("Content-Disposition", "")
            
            if content_disposition:
                fn_match = RE_FILENAME.search(content_disposition)
                if fn_match:
                    info["name"] = fn_match.group(1).strip()
            
            # If direct download (< 100MB)
            if "text/html" not in content_type:
                if content_length:
                    info["size"] = format_bytes(int(content_length))
            else:
                # Virus scan confirmation page (> 100MB)
                # Read only first 8KB where the filename and size span resides
                chunk = await resp.content.read(8192)
                html_snippet = chunk.decode("utf-8", errors="ignore")
                
                name_size_match = RE_NAME_SIZE.search(html_snippet)
                if name_size_match:
                    if not info["name"]:
                        info["name"] = name_size_match.group(1).strip()
                    raw_size = name_size_match.group(2).strip()
                    info["size"] = normalize_size_str(raw_size)
    except Exception as e:
        print(f"[parser] Quick fetch notice for {file_id}: {e}")
        
    return info

def parse_media_details(text: str, gdrive_name: str | None = None) -> dict:
    """Fast extraction of series title, season, episode, bolum, and quality."""
    source_text = text or ""
    if gdrive_name:
        source_text += "\n" + gdrive_name
        
    details = {
        "title": "Mehmed: Fetihler Sultanı",
        "season": None,
        "episode": None,
        "bolum": None,
        "quality": "1080p"
    }
    
    # 1. Quality detection
    q_match = RE_QUALITY.search(source_text)
    if q_match:
        val = q_match.group(1)
        details["quality"] = "4K" if val.upper() == "4K" else val.lower()
        
    # 2. Season detection
    s_match = RE_SEASON.search(source_text)
    if s_match:
        details["season"] = f"Season {int(s_match.group(1)):02d}"
        
    # 3. Episode detection
    e_match = RE_EPISODE.search(source_text)
    if e_match:
        details["episode"] = f"Episode {int(e_match.group(1)):02d}"
        
    # 4. Bölüm detection
    b_match = RE_BOLUM.search(source_text)
    if b_match:
        details["bolum"] = f"Bölüm {b_match.group(1)}"
        
    # 5. Title / Series name detection
    found_title = None
    for code, full_name in SERIES_MAP.items():
        if re.search(rf'\b{re.escape(code)}\b', source_text, re.IGNORECASE):
            found_title = full_name
            break
            
    if found_title:
        details["title"] = found_title
    else:
        for line in source_text.splitlines():
            line = line.strip()
            if (line 
                and not line.startswith("Uploaded") 
                and not line.startswith("Link:") 
                and not line.startswith("http") 
                and not line.startswith("/convert")):
                cleaned = RE_SPLIT_TITLE.split(line)[0].strip()
                if cleaned and len(cleaned) > 2:
                    details["title"] = cleaned
                    break
                    
    return details

def format_card(file_id: str, g_info: dict, details: dict) -> str:
    """
    Formats the card exactly matching the bold style in Image 1.
    """
    ep_parts = []
    if details["season"] and details["episode"]:
        ep_parts.append(f"{details['season']} • {details['episode']}")
    elif details["season"]:
        ep_parts.append(details["season"])
    elif details["episode"]:
        ep_parts.append(details["episode"])
        
    if details["bolum"]:
        if ep_parts:
            ep_line = f"{ep_parts[0]} | {details['bolum']}"
        else:
            ep_line = details["bolum"]
    else:
        ep_line = ep_parts[0] if ep_parts else ""
        
    size_str = g_info.get("size") or "Unknown"
    quality_str = details["quality"]
    
    gdrive_link = f"https://drive.google.com/uc?id={file_id}&export=download"
    better_link = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&authuser=0"
    
    ep_section = f"\n<b>{ep_line}</b>\n" if ep_line else ""
    
    return f"""<b>{details['title']}</b>
{ep_section}
<b>Size : {size_str} | Quality : {quality_str}</b>

<b>G-drive Link -</b>
{gdrive_link}

<b>Better link -</b>
{better_link}

{{Copy paste in browser}}

Please don't share this link with anyone."""

async def process_text_and_format(session: aiohttp.ClientSession, text: str) -> list[str]:
    file_ids = extract_gdrive_ids(text)
    if not file_ids:
        return []
        
    results = []
    for file_id in file_ids:
        g_info = await fetch_gdrive_info(session, file_id)
        details = parse_media_details(text, g_info.get("name"))
        card = format_card(file_id, g_info, details)
        results.append(card)
        
    return results
