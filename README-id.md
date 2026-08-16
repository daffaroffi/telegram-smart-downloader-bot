# Smart Downloader PRO & Realtime Traffic Bot

[English](README.md) | [Bahasa Indonesia](README-id.md)

---

Engine Bot Telegram berperforma tinggi yang dijalankan di VPS Linux untuk pengunduhan media multi-thread (yt-dlp + Aria2c) dan notifikasi push traffic web Nginx secara real-time.

## Fitur Utama

- **Mesin Pengunduhan Multi-Thread**: Didukung oleh Aria2c (16 koneksi paralel) untuk file langsung dan pemilih resolusi yt-dlp (1080p, 720p, 480p, 360p, Audio MP3).
- **Notifikasi Push Pengunjung Real-time**: Streamer log Nginx di latar belakang yang mengirim alert instan ke Telegram setiap kali ada pengunjung mengakses web portfolio Anda.
- **Kesehatan VPS & Manajer File**: Explorer file di chat, meter penyimpanan disk, penggunaan RAM, dan penghapusan/pembersihan file instan.
- **Aman & Privat**: Dibatasi hanya untuk User ID Telegram yang terotorisasi. Kredensial sensitif dikelola melalui variabel lingkungan.

## Tech Stack

- **Python 3.12** / `pyTelegramBotAPI` (`telebot`)
- **Aria2c** (Mesin Multi-Thread 16 Koneksi)
- **yt-dlp** (Ekstraktor Media & Remuxing)
- **Nginx Access Log Parser** (Deteksi Pengunjung Real-Time)
- **Systemd** (Manajemen Layanan Linux Otomatis)

## Setup Cepat

1. **Clone Repository**:
   ```bash
   git clone https://github.com/daffaroffi/telegram-smart-downloader-bot.git
   cd telegram-smart-downloader-bot
   ```

2. **Konfigurasi Variabel Lingkungan**:
   Salin `.env.example` ke `.env` dan isi Bot Token serta User ID Telegram Anda:
   ```bash
   cp .env.example .env
   ```

3. **Instal Dependensi**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install pyTelegramBotAPI requests
   ```

4. **Jalankan Bot**:
   ```bash
   python bot.py
   ```

## Integrasi Systemd

Untuk menjalankan sebagai layanan sistem di Ubuntu/Debian:
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

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
