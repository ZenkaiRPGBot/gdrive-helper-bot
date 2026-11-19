import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Startup timestamp for uptime calculation
BOT_START_TIME = datetime.now(timezone.utc)

# Telegram Bot Token from @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Owner Telegram ID
OWNER_ID = int(os.getenv("OWNER_ID", "986380678"))

# Port for web server (Render provides PORT automatically)
PORT = int(os.getenv("PORT", "8080"))

# Uptime ping target (e.g. https://my-bot.onrender.com)
PING_URL = os.getenv("PING_URL") or os.getenv("RENDER_EXTERNAL_URL")

# Turkish drama series abbreviations and aliases mapping
SERIES_MAP = {
    "MFS": "Mehmed: Fetihler Sultanı",
    "MEHMED": "Mehmed: Fetihler Sultanı",
    "KO": "Kuruluş Osman",
    "KURULUS": "Kuruluş Osman",
    "OSMAN": "Kuruluş Osman",
    "DE": "Diriliş Ertuğrul",
    "ERTUGRUL": "Diriliş Ertuğrul",
    "DIRILIS": "Diriliş Ertuğrul",
    "ABS": "Alparslan: Büyük Selçuklu",
    "ALPARSLAN": "Alparslan: Büyük Selçuklu",
    "UBS": "Uyanış: Büyük Selçuklu",
    "UYANIS": "Uyanış: Büyük Selçuklu",
    "KBS": "Kudüs Fatihi Selahaddin Eyyubi",
    "SELAHADDIN": "Kudüs Fatihi Selahaddin Eyyubi",
    "DESTAN": "Destan",
    "BARBAROS": "Barbaroslar: Akdeniz'in Kılıcı",
    "BS": "Barbaroslar: Akdeniz'in Kılıcı",
    "TESKILAT": "Teşkilat",
    "YUREK": "Yürek Çıkmazı",
    "GAZI": "Gazi",
    "YAVUZ": "Yavuz Sultan Selim",
}

# Changelog & active release details for the restart notification
LATEST_CHANGELOG = [
    "<b>Auto Link Processor:</b> Automatic detection of Google Drive links and file IDs",
    "<b>Metadata & Size Parser:</b> Direct Google Drive file size scraping without API credentials",
    "<b>Series Formatter:</b> Automatic translation of series codes (MFS, KO, DE) with Episode / Bölüm details",
    "<b>Ping & Diagnostics:</b> Added <code>/ping</code> latency check and system uptime tracking",
    "<b>Render Keep-Alive:</b> Integrated HTTP health server and 10-minute self-ping cycle to prevent idle shutdown",
    "<b>Owner Notifications:</b> Automatic deployment and restart alert dispatch system"
]
