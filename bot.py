import os
import sys
import time
import html
import asyncio
from datetime import datetime, timezone
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    BotCommand, BotCommandScopeDefault
)
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramBadRequest

from config import (
    BOT_TOKEN, OWNER_ID, LOG_CHANNEL_ID, BOT_START_TIME,
    SERIES_MAP, RENDER_EMAIL, RENDER_SERVICE_NAME, RENDER_REPO,
    RENDER_USED_HOURS, IST
)
from parser import process_text_and_format, extract_gdrive_ids
from uploader import is_uploader_request, generate_uploader_data
from keep_alive import start_web_server

dp = Dispatcher()

HTTP_SESSION: aiohttp.ClientSession | None = None

def get_uptime_string() -> str:
    uptime_sec = int((datetime.now(IST) - BOT_START_TIME).total_seconds())
    days, rem = divmod(uptime_sec, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0 or days > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)

def get_process_memory_mb() -> float:
    try:
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024.0
    except Exception:
        pass
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:
        return 38.4

async def measure_gateway_latency(bot: Bot) -> float:
    t0 = time.perf_counter()
    try:
        await bot.get_me()
    except Exception:
        pass
    return (time.perf_counter() - t0) * 1000.0

async def build_usage_card_text(bot: Bot) -> tuple[str, InlineKeyboardMarkup]:
    now = datetime.now(IST)
    uptime_str = get_uptime_string()

    # Calculate live accurate usage from baseline RENDER_USED_HOURS + live session hours
    session_hours = (now - BOT_START_TIME).total_seconds() / 3600.0
    total_used_hours = min(750.0, RENDER_USED_HOURS + session_hours)
    remaining_hours = max(0.0, 750.0 - total_used_hours)
    used_pct = min(100.0, (total_used_hours / 750.0) * 100.0)
    days_left_capacity = remaining_hours / 24.0

    mem_mb = get_process_memory_mb()
    mem_pct = min(100.0, (mem_mb / 512.0) * 100.0)
    ping_ms = await measure_gateway_latency(bot)

    text = (
        "<b>GDrive Helper — Service & Host Metrics</b>\n\n"
        "<b>Host & Account:</b>\n"
        "• <b>Cloud:</b> Render (Frankfurt, EU-Central)\n"
        f"• <b>Account Email:</b> <code>{html.escape(RENDER_EMAIL)}</code>\n"
        f"• <b>Service Name:</b> <code>{html.escape(RENDER_SERVICE_NAME)}</code>\n"
        f"• <b>Repository:</b> <code>{html.escape(RENDER_REPO)}</code>\n\n"
        "<b>Monthly Free Usage (Render Limit: 750h):</b>\n"
        f"• <b>Active Uptime:</b> <code>{uptime_str}</code>\n"
        f"• <b>Hours This Month:</b> <code>{total_used_hours:.1f}h / 750h ({used_pct:.1f}%)</code>\n"
        f"• <b>Remaining Free:</b> <code>{remaining_hours:.1f}h (~{days_left_capacity:.1f} days)</code>\n"
        f"• <b>Memory (RAM):</b> <code>{mem_mb:.1f} MB / 512 MB ({mem_pct:.1f}%)</code>\n\n"
        "<b>Bot Activity:</b>\n"
        "• <b>Modules:</b> GDrive Scraper · Fastmotion · Yandex Splitter\n"
        f"• <b>Gateway Ping:</b> <code>{ping_ms:.1f} ms</code>"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Refresh Stats", callback_data="usage:refresh", style="primary")],
        [InlineKeyboardButton(text="Check Ping", callback_data="ping:refresh", style="success")]
    ])
    return text, markup

async def register_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="View bot introduction & guide"),
        BotCommand(command="convert", description="Format Google Drive links"),
        BotCommand(command="upload", description="Prepare uploader links & captions"),
        BotCommand(command="ping", description="Check bot latency and uptime"),
        BotCommand(command="usage", description="Render hosting & account usage"),
        BotCommand(command="series", description="List supported series codes"),
        BotCommand(command="help", description="Detailed usage instructions")
    ]
    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        print("[commands] Registered official Telegram bot commands.")
    except Exception as e:
        print(f"[commands] Failed to register commands: {e}")

async def send_restart_notification(bot: Bot):
    if not OWNER_ID:
        return

    reason_file = os.path.join(os.path.dirname(__file__), "restart_reason.txt")
    custom_reason = None
    if os.path.exists(reason_file):
        try:
            with open(reason_file, "r", encoding="utf-8") as f:
                custom_reason = f.read().strip()
            os.remove(reason_file)
        except Exception:
            pass

    ping_ms = await measure_gateway_latency(bot)
    now_str = datetime.now(IST).strftime("%I:%M:%S %p IST · %b %d")

    if custom_reason:
        content = (
            "<b>GDrive Helper · System Restart</b>\n\n"
            "<b>Status:</b> 🟢 Online\n"
            "<b>Cluster:</b> Frankfurt (EU-Central)\n"
            f"<b>Gateway Ping:</b> <code>{ping_ms:.1f} ms</code>\n"
            f"<b>Timestamp:</b> <code>{now_str}</code>\n\n"
            f"<blockquote><b>Restart Reason</b>\n{html.escape(custom_reason)}</blockquote>\n\n"
            "<i>Uploader interface and link parsers active.</i>"
        )
    else:
        content = (
            "<b>GDrive Helper · System Restart</b>\n\n"
            "<b>Status:</b> 🟢 Online\n"
            "<b>Cluster:</b> Frankfurt (EU-Central)\n"
            f"<b>Gateway Ping:</b> <code>{ping_ms:.1f} ms</code>\n"
            f"<b>Timestamp:</b> <code>{now_str}</code>\n\n"
            "<blockquote><b>What's New in this Build</b>\n"
            "• <b>Ultra-Low Latency:</b> Persistent TCP keep-alive socket\n"
            "• <b>Resource Monitor:</b> New /usage & /render stats command\n"
            "• <b>Standardized IST:</b> All timestamps in Indian Standard Time\n"
            "• <b>Multi-Bot Ready:</b> Unified hosting metrics card for groups</blockquote>\n\n"
            "<i>Ready to process Google Drive, Fastmotion, and Yandex links.</i>"
        )

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Check Ping", callback_data="ping:refresh", style="primary"),
            InlineKeyboardButton(text="Service Usage", callback_data="usage:refresh", style="success")
        ]
    ])

    targets = [OWNER_ID]
    if LOG_CHANNEL_ID:
        try:
            targets.append(int(LOG_CHANNEL_ID))
        except ValueError:
            pass

    for chat_id in set(targets):
        try:
            await bot.send_message(chat_id=chat_id, text=content, parse_mode=ParseMode.HTML, reply_markup=markup)
            print(f"[restart] Sent restart notification to {chat_id}")
        except Exception as e:
            print(f"[restart] Could not notify {chat_id}: {e}")

# ==============================================================================
# COMMAND HANDLERS
# ==============================================================================

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
        "• <code>/usage</code> — Render hosting & account metrics\n"
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
    latency_ms = await measure_gateway_latency(bot)
    uptime_str = get_uptime_string()

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Refresh Ping", callback_data="ping:refresh", style="primary")],
        [InlineKeyboardButton(text="Service Usage", callback_data="usage:show", style="success")]
    ])

    text = (
        "<b>Pong!</b> ⚡\n\n"
        f"<b>Gateway Latency:</b> <code>{latency_ms:.1f} ms</code>\n"
        f"<b>Server Region:</b> <code>Frankfurt (EU)</code>\n"
        f"<b>Uptime:</b> <code>{uptime_str}</code>\n\n"
        "<i>Optimized TCP keep-alive connection to Telegram edge.</i>"
    )
    await message.reply(text, parse_mode=ParseMode.HTML, reply_markup=markup)

@dp.callback_query(F.data == "ping:refresh")
async def cb_ping_refresh(callback: types.CallbackQuery, bot: Bot):
    latency_ms = await measure_gateway_latency(bot)
    uptime_str = get_uptime_string()

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Refresh Ping", callback_data="ping:refresh", style="primary")],
        [InlineKeyboardButton(text="Service Usage", callback_data="usage:show", style="success")]
    ])

    text = (
        "<b>Pong!</b> ⚡\n\n"
        f"<b>Gateway Latency:</b> <code>{latency_ms:.1f} ms</code>\n"
        f"<b>Server Region:</b> <code>Frankfurt (EU)</code>\n"
        f"<b>Uptime:</b> <code>{uptime_str}</code>\n\n"
        "<i>Optimized TCP keep-alive connection to Telegram edge.</i>"
    )
    try:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except TelegramBadRequest:
        pass
    await callback.answer(f"Ping: {latency_ms:.1f} ms")

@dp.message(Command("usage"))
@dp.message(Command("render"))
@dp.message(Command("status"))
async def cmd_usage(message: types.Message, bot: Bot):
    text, markup = await build_usage_card_text(bot)
    await message.reply(text, parse_mode=ParseMode.HTML, reply_markup=markup)

@dp.callback_query(F.data == "usage:refresh")
@dp.callback_query(F.data == "usage:show")
async def cb_usage_refresh(callback: types.CallbackQuery, bot: Bot):
    text, markup = await build_usage_card_text(bot)
    try:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except TelegramBadRequest:
        pass
    await callback.answer("Metrics refreshed.")

@dp.message(Command("restart"))
async def cmd_restart(message: types.Message, bot: Bot):
    if message.from_user.id != OWNER_ID:
        await message.reply("Access denied. Owner only.")
        return

    reason = message.text.partition(" ")[2].strip() or "Manual owner restart"
    reason_file = os.path.join(os.path.dirname(__file__), "restart_reason.txt")
    try:
        with open(reason_file, "w", encoding="utf-8") as f:
            f.write(reason)
    except Exception:
        pass

    await message.reply(f"<b>Restarting bot...</b>\n<i>Reason: {html.escape(reason)}</i>", parse_mode=ParseMode.HTML)
    print(f"[bot] Owner initiated restart. Reason: {reason}")

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
        "<b>2. Uploader Assistant:</b>\n"
        "Send your episode message containing <code>fastmotion.io</code> or <code>yandex.com.tr</code> links.\n\n"
        "<b>Commands:</b>\n"
        "• <code>/convert</code> — Paste links to convert\n"
        "• <code>/upload</code> — Uploader helper guide\n"
        "• <code>/ping</code> — Gateway latency & uptime\n"
        "• <code>/usage</code> — Render account & host metrics\n"
        "• <code>/series</code> — Show all recognized drama codes"
    )
    await message.reply(help_text, parse_mode=ParseMode.HTML)

@dp.message(Command("series"))
async def cmd_series(message: types.Message):
    lines = ["<b>Supported Drama Series Codes:</b>\n"]
    seen = set()
    for code, full_name in sorted(SERIES_MAP.items()):
        if full_name not in seen:
            lines.append(f"• <b>{code}</b>: {full_name}")
            seen.add(full_name)
    await message.reply("\n".join(lines), parse_mode=ParseMode.HTML)

@dp.message(Command("convert"))
async def cmd_convert(message: types.Message):
    payload = message.text.partition(" ")[2].strip()
    if not payload:
        await message.reply("Please paste your Google Drive message after <code>/convert</code>.", parse_mode=ParseMode.HTML)
        return
    await handle_text_message(message, custom_text=payload)

@dp.message(Command("upload"))
async def cmd_upload(message: types.Message):
    payload = message.text.partition(" ")[2].strip()
    if not payload:
        await message.reply("Please paste your episode message with links after <code>/upload</code>.", parse_mode=ParseMode.HTML)
        return
    await handle_text_message(message, custom_text=payload)

@dp.message(F.text)
async def handle_text_message(message: types.Message, custom_text: str | None = None):
    text = custom_text or message.text
    if not text:
        return

    # Check for uploader request
    if is_uploader_request(text):
        uploader_blocks = generate_uploader_data(text)
        if uploader_blocks:
            for block in uploader_blocks:
                await message.reply(
                    block,
                    parse_mode=ParseMode.HTML,
                    link_preview_options=types.LinkPreviewOptions(is_disabled=True)
                )
            return

    # Check for Google Drive links
    gdrive_ids = extract_gdrive_ids(text)
    if not gdrive_ids:
        return

    formatted_text = await process_text_and_format(text, HTTP_SESSION)
    await message.reply(
        formatted_text,
        parse_mode=ParseMode.HTML,
        link_preview_options=types.LinkPreviewOptions(is_disabled=True)
    )

# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================

async def main():
    global HTTP_SESSION
    if not BOT_TOKEN:
        print("\nERROR: BOT_TOKEN is missing in .env!\n")
        sys.exit(1)

    print("Launching Google Drive & Uploader Helper Bot...")

    bot = Bot(token=BOT_TOKEN)

    connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300, ssl=False, enable_cleanup_closed=True)
    HTTP_SESSION = aiohttp.ClientSession(connector=connector)

    runner = await start_web_server()
    await bot.delete_webhook(drop_pending_updates=True)

    await register_bot_commands(bot)
    await send_restart_notification(bot)

    print("Bot is actively polling. Ready to process messages.")
    try:
        await dp.start_polling(bot)
    finally:
        if HTTP_SESSION and not HTTP_SESSION.closed:
            await HTTP_SESSION.close()
            await asyncio.sleep(0.25)
        await bot.session.close()
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nBot process halted.")
