# Google Drive Link Helper Telegram Bot

A Telegram bot that detects Google Drive links, extracts the Google Drive file ID, queries the exact file size directly from Google Drive, parses series / season / episode / bölüm / quality info, and formats everything into clean, ready-to-share cards.

---

## Features
- **Automatic Detection:** Any message containing a Google Drive link is automatically processed.
- **Manual `/convert` Command:** Reply to any message with `/convert` or use `/convert <link>`.
- **Latency & Uptime (`/ping`):** Precise ping response time measurement and formatted uptime.
- **Owner Restart Notifications:** Sends a clean, rich system status and changelog report to the owner upon startup or restart.
- **Direct File Size Extraction:** Automatically extracts the exact file size (e.g. `3.0 GB`) and file name without needing an API key.
- **Series & Episode Parsing:** Parses Turkish drama abbreviations (`MFS`, `KO`, `DE`, `KBS`, `ABS`, etc.), Season, Episode, Bölüm, and video quality (`1080p`, `720p`, `4K`).
- **Dual Link Generation:** Generates standard G-drive export links and direct browser download links.
- **Render 15-Minute Uptime Keep-Alive:** Built-in web server with an automatic self-ping loop every 10 minutes to prevent Render free-tier from idling/sleeping.

---

## Local Setup & Testing

### 1. Configure Credentials
1. Open Telegram and message [@BotFather](https://t.me/BotFather) to get your bot token.
2. Open the `.env` file in this directory and set your credentials:
   ```env
   BOT_TOKEN=your_bot_token_here
   OWNER_ID=986380678
   PORT=8080
   PING_URL=
   ```

### 2. Run the Bot
In your terminal, run:
```bash
python bot.py
```

### 3. Test in Telegram
1. Open your bot in Telegram and send `/start` (ensure the owner account sends `/start` once so the bot can send notifications).
2. Check bot latency and uptime:
   ```text
   /ping
   ```
3. Test your link formatting:
   ```text
   Uploaded to Google drive ✅

   MFS S04 - E09 - Bölüm 92 - English Subtitles - 1080p - KayiTV.mp4
   Link: https://drive.google.com/uc?id=1dwhDmyqy1Az2Ffxvp16UIvuUBDZgR-M1&export=download
   ```
4. Test owner process reboot:
   ```text
   /restart
   ```

---

## Deployment on Render (with 24/7 Keep-Alive)

1. **Push this folder to a GitHub repository:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/your-username/your-repo.git
   git push -u origin main
   ```

2. **Create a Web Service on [Render](https://render.com):**
   - Click **New +** > **Web Service**.
   - Connect your GitHub repository.
   - Set **Runtime** to `Python 3`.
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Instance Type:** Free.

3. **Set Environment Variables on Render:**
   Under the **Environment Variables** tab:
   - `BOT_TOKEN` = `your_telegram_bot_token`
   - `OWNER_ID` = `986380678`
   - `PING_URL` = `https://your-service-name.onrender.com` *(your Render web service URL)*

4. **Render Uptime (Prevent 15-minute Sleep):**
   - When `PING_URL` is set, the bot automatically pings itself every 10 minutes to stay awake.
   - *(Optional Backup)*: You can also add your Render service URL to a free uptime monitor like [UptimeRobot](https://uptimerobot.com) with a 5-minute interval check.
