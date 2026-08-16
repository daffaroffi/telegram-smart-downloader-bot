# Smart Downloader PRO & Realtime Traffic Bot

[English](README.md) | [Bahasa Indonesia](README-id.md)

A high-performance Telegram bot for a Linux VPS that provides multi-threaded media downloading (yt-dlp + Aria2c) and real-time Nginx web traffic push alerts.

## Features

- Multi-threaded download engine: Aria2c with 16 parallel connections for direct files, and yt-dlp resolution selector (1080p, 720p, 480p, 360p, MP3 audio).
- Realtime visitor push alerts: background Nginx log streamer sends an instant Telegram alert whenever a visitor hits your site.
- VPS health and file manager: in-chat file explorer, storage meter, RAM usage, and instant file cleanup.
- Secure and private: restricted to authorized Telegram user IDs; credentials managed via environment variables.

## Commands

| Command | Description |
|---|---|
| /start, /help | Show help |
| /status | Show server status |
| /files | Browse and manage downloaded files |
| /clean | Clean up downloaded files |

## Requirements

- Python 3.8+
- Aria2c (multi-thread download engine)
- yt-dlp (media extractor and remuxing)
- A Telegram bot token from @BotFather

## Quick Setup

### 1. Clone the repository

```bash
git clone https://github.com/daffaroffi/telegram-smart-downloader-bot.git
cd telegram-smart-downloader-bot
```

### 2. Configure environment variables

Create your configuration file from the example:

```bash
cp .env.example .env
```

Then edit `.env` and fill in your values:

```env
BOT_TOKEN=123456789:AA...your-token-from-botfather
ALLOWED_USER_ID=8927082329
DOWNLOAD_DIR=/path/to/downloads
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `BOT_TOKEN` | Yes | - | Bot token from @BotFather |
| `ALLOWED_USER_ID` | Yes | - | Telegram user ID allowed to use the bot |
| `DOWNLOAD_DIR` | No | - | Directory where downloads are stored |

### 3. Install dependencies and run

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python bot.py
```

## Run as a systemd service

Create `/etc/systemd/system/telegram-smart-downloader-bot.service`:

```ini
[Unit]
Description=Smart Downloader Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/my-project/telegram-smart-downloader-bot
EnvironmentFile=/root/my-project/telegram-smart-downloader-bot/.env
ExecStart=/root/my-project/telegram-smart-downloader-bot/venv/bin/python /root/my-project/telegram-smart-downloader-bot/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-smart-downloader-bot.service
sudo systemctl start telegram-smart-downloader-bot.service
```

## Security

- The bot rejects messages from any user not matching `ALLOWED_USER_ID`.
- The bot token is read from `.env`, which is excluded from version control.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
