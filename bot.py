import os
import sys
import time
import asyncio
from datetime import datetime, timezone
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode

from config import BOT_TOKEN, OWNER_ID, BOT_START_TIME, SERIES_MAP
from parser import process_text_and_format, extract_gdrive_ids
from uploader import is_uploader_request, generate_uploader_data
from keep_alive import start_web_server

dp = Dispatcher()

# Global shared session for fast connection reuse
HTTP_SESSION: aiohttp.ClientSession | None = None

def get_uptime_string() -> str:
    delta = datetime.now(timezone.utc) - BOT_START_TIME
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0 or days > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)

def build_enhanced_rich_markdown() -> str:
    """Clean, simple, non-technical rich message layout."""
    return """# GDrive Bot Online

| Feature | Status |
| :--- | :---: |
| Bot Status | Online 🟢 |
| Link Formatter | Ready 🟢 |
| Uploader Assistant | Active 🟢 |

### What's New
- Automatic formatting for Google Drive episode links
- Instant Fastmotion & Yandex uploader link splitter
- One-tap copy captions for 360p-1080p
- Fast cloud response times

*Ready for links.*"""

async def send_rich_restart_notification(bot: Bot):
    """Sends native rich message table via sendRichMessage endpoint."""
    if not OWNER_ID:
        return
        
    rich_md = build_enhanced_rich_markdown()
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendRichMessage"
    payload = {
        "chat_id": OWNER_ID,
        "rich_message": {
            "markdown": rich_md
        }
    }
    
    try:
        if HTTP_SESSION:
            async with HTTP_SESSION.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                data = await resp.json()
                if data.get("ok"):
                    print(f"[restart] Clean rich restart message delivered to owner ({OWNER_ID})")
                else:
                    print(f"[restart] Notice: sendRichMessage returned: {data}")
    except Exception as e:
        print(f"[restart] Failed to send rich restart notification: {e}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = (
        "<b>Google Drive & Uploader Helper Bot</b>\n\n"
        "<b>Core Features:</b>\n"
        "• <b>GDrive Formatter:</b> Send any Google Drive link to generate the formatted post with exact file size.\n"
        "• <b>Uploader Assistant:</b> Send your Fastmotion + Yandex links to get 1-tap copy blocks for Bot 1 & Bot 2 and ready-to-use captions.\n\n"
        "<b>Commands:</b>\n"
        "• <code>/convert</code> — Format Google Drive links\n"
        "• <code>/upload</code> — Prepare uploader links & captions\n"
        "• <code>/ping</code> — Check bot speed and uptime\n"
        "• <code>/series</code> — Supported series names\n"
        "• <code>/help</code> — Detailed instructions\n\n"
        "Paste your links below to start."
    )
    await message.reply(
        welcome_text,
        parse_mode=ParseMode.HTML,
        link_preview_options=types.LinkPreviewOptions(is_disabled=True)
    )

@dp.message(Command("ping"))
async def cmd_ping(message: types.Message, bot: Bot):
    t0 = time.perf_counter()
    await bot.get_me()
    latency = (time.perf_counter() - t0) * 1000
    uptime = get_uptime_string()
    
    response = (
        "<b>Pong!</b>\n\n"
        f"• <b>Speed:</b> <code>{latency:.1f} ms</code>\n"
        f"• <b>Uptime:</b> <code>{uptime}</code>\n"
        f"• <b>Status:</b> <code>Healthy</code>"
    )
    await message.reply(
        response,
        parse_mode=ParseMode.HTML,
        link_preview_options=types.LinkPreviewOptions(is_disabled=True)
    )

@dp.message(Command("restart"))
async def cmd_restart(message: types.Message, bot: Bot):
    if message.from_user.id != OWNER_ID:
        await message.reply("Access denied. Owner only.")
        return

    await message.reply("<b>Restarting...</b>", parse_mode=ParseMode.HTML)
    print(f"[bot] Owner initiated restart. Re-executing...")
    
    if HTTP_SESSION and not HTTP_SESSION.closed:
        await HTTP_SESSION.close()
    await bot.session.close()
    
    os.execv(sys.executable, [sys.executable] + sys.argv)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "<b>Help & Usage Instructions</b>\n\n"
        "<b>1. Google Drive Post Formatter:</b>\n"
        "Send your episode message containing a Google Drive link. The bot extracts the file size and formats it.\n\n"
        "<b>2. Uploader Assistant (Fastmotion / Yandex):</b>\n"
        "Send your Fastmotion link + optional Yandex link + episode info:\n"
        "<code>MFS S04 E09 92\n"
        "https://s.fastmotion.io/.../360p/video.m3u8\n"
        "https://disk.yandex.com.tr/i/...</code>\n"
        "The bot will output ready-to-copy lines for GDrive, Bot 1, Bot 2, and the 4 quality captions!"
    )
    await message.reply(
        help_text,
        parse_mode=ParseMode.HTML,
        link_preview_options=types.LinkPreviewOptions(is_disabled=True)
    )

@dp.message(Command("series"))
async def cmd_series(message: types.Message):
    lines = [f"• <code>{code}</code> ➔ <b>{name}</b>" for code, name in sorted(SERIES_MAP.items())]
    text = (
        "<b>Recognized Series:</b>\n\n"
        + "\n".join(lines)
    )
    await message.reply(
        text,
        parse_mode=ParseMode.HTML,
        link_preview_options=types.LinkPreviewOptions(is_disabled=True)
    )

async def send_uploader_response(message: types.Message, raw_text: str):
    """Processes episode uploader request and replies with tap-to-copy blocks and captions."""
    data = generate_uploader_data(raw_text)
    
    # Message 1: Uploader Bot Links
    links_msg = (
        "<b>🚀 Uploader Bot Links</b> <i>(Tap code box to copy)</i>\n\n"
        "<b>📁 Google Drive (1080p):</b>\n"
        f"<code>{data['gdrive_line']}</code>\n\n"
        "<b>🤖 Bot 1 (360p & 480p):</b>\n"
        f"<pre>{data['bot1_block']}</pre>\n\n"
        "<b>🤖 Bot 2 (720p & 1080p):</b>\n"
        f"<pre>{data['bot2_block']}</pre>"
    )
    await message.reply(
        links_msg,
        parse_mode=ParseMode.HTML,
        link_preview_options=types.LinkPreviewOptions(is_disabled=True)
    )
    
    # Message 2: Formatted Captions
    captions_msg = (
        "<b>📝 Video Captions</b> <i>(Tap box to copy)</i>\n\n"
        "<b>📺 360p / 480p / 720p Caption:</b>\n"
        f"<pre>{data['captions_plain']['720p']}</pre>\n\n"
        "<b>📺 1080p Caption:</b>\n"
        f"<pre>{data['captions_plain']['1080p']}</pre>"
    )
    await message.reply(
        captions_msg,
        parse_mode=ParseMode.HTML,
        link_preview_options=types.LinkPreviewOptions(is_disabled=True)
    )

@dp.message(Command("upload", "uploader"))
async def cmd_upload(message: types.Message):
    target_text = ""
    if message.reply_to_message:
        target_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    if not target_text:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            target_text = parts[1]
            
    if not target_text:
        await message.reply(
            "Send or reply with your Fastmotion link and episode info to generate uploader lines.",
            parse_mode=ParseMode.HTML
        )
        return

    await send_uploader_response(message, target_text)

@dp.message(Command("convert", "format"))
async def cmd_convert(message: types.Message):
    target_text = ""
    if message.reply_to_message:
        target_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    if not target_text:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            target_text = parts[1]
            
    if not target_text:
        await message.reply(
            "Reply to a message with <code>/convert</code> or send <code>/convert &lt;link&gt;</code>.",
            parse_mode=ParseMode.HTML
        )
        return

    ids = extract_gdrive_ids(target_text)
    if not ids:
        await message.reply("No Google Drive link found.")
        return

    cards = await process_text_and_format(HTTP_SESSION, target_text)
    if cards:
        for card in cards:
            await message.reply(
                card,
                parse_mode=ParseMode.HTML,
                link_preview_options=types.LinkPreviewOptions(is_disabled=True)
            )
    else:
        await message.reply("Could not extract details. Check that the link is accessible.")

@dp.message(F.text)
async def handle_all_messages(message: types.Message):
    if message.text.startswith("/"):
        return

    # 1. Check if it's an uploader request (Fastmotion / Yandex / m3u8)
    if is_uploader_request(message.text):
        await send_uploader_response(message, message.text)
        return

    # 2. Check if it's a Google Drive link request
    ids = extract_gdrive_ids(message.text)
    if ids:
        cards = await process_text_and_format(HTTP_SESSION, message.text)
        if cards:
            for card in cards:
                await message.reply(
                    card,
                    parse_mode=ParseMode.HTML,
                    link_preview_options=types.LinkPreviewOptions(is_disabled=True)
                )

async def main():
    global HTTP_SESSION
    if not BOT_TOKEN:
        print("\nERROR: BOT_TOKEN is missing in .env!\n")
        sys.exit(1)

    print("Launching Google Drive & Uploader Helper Bot...")
    
    # Connection pool for ultra-fast response times
    connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300, ssl=False, enable_cleanup_closed=True)
    HTTP_SESSION = aiohttp.ClientSession(connector=connector)
    
    bot = Bot(token=BOT_TOKEN)
    
    # Start Keep-Alive web server in background
    runner = await start_web_server()
    
    # Ensure any conflicting webhook is cleared before polling
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Dispatch clean rich restart notification to owner
    await send_rich_restart_notification(bot)
    
    print("Bot is actively polling. Ready to process messages.")
    try:
        await dp.start_polling(bot)
    finally:
        if HTTP_SESSION and not HTTP_SESSION.closed:
            await HTTP_SESSION.close()
        await bot.session.close()
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nBot process halted.")
