# Smart Downloader PRO & Realtime Traffic Bot

High-performance Telegram Bot engine deployed on Linux VPS for multi-threaded media downloading (yt-dlp + Aria2c) and instant real-time Nginx web traffic push alerts.

## 🌟 Key Features

- **⚡ Multi-Threaded Downloading Engine**: Powered by Aria2c (16 parallel connections) for direct files and yt-dlp resolution selector (1080p, 720p, 480p, 360p, MP3 Audio).
- **🔔 Realtime Visitor Push Alerts**: Background Nginx log streamer pushing instant alerts to Telegram whenever a visitor hits your web portfolio.
- **📊 VPS Health & File Manager**: In-chat file explorer, storage disk meter, RAM usage, and instant file deletion/cleaning.
- **🛡️ Secure & Private**: Restricted to authorized Telegram User IDs only. Sensitive credentials managed via environment variables.

## 🛠️ Tech Stack

- **Python 3.12** / `pyTelegramBotAPI` (`telebot`)
- **Aria2c** (16-Connection Multi-Thread Engine)
- **yt-dlp** (Media Extractor & Remuxing)
- **Nginx Access Log Parser** (Real-Time Visitor Detection)
- **Systemd** (Automated Linux Service Management)

## 🚀 Quick Setup

1. **Clone Repository**:
   ```bash
   git clone https://github.com/daffaroffi/telegram-smart-downloader-bot.git
   cd telegram-smart-downloader-bot
   ```

2. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and fill in your Telegram Bot Token and User ID:
   ```bash
   cp .env.example .env
   ```

3. **Install Dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install pyTelegramBotAPI requests
   ```

4. **Run Bot**:
   ```bash
   python bot.py
   ```

## 📜 Systemd Integration

To run as a system service on Ubuntu/Debian:
```ini
[Unit]
Description=Smart Downloader Telegram Bot
After=network.target

[Service]
User=root
WorkingDirectory=/root/my-project/telegram-smart-downloader-bot
EnvironmentFile=/root/my-project/telegram-smart-downloader-bot/.env
ExecStart=/root/my-project/telegram-smart-downloader-bot/venv/bin/python /root/my-project/telegram-smart-downloader-bot/bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

---
***REMOVED***
