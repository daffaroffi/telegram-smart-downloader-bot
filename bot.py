import os
import sys
import shutil
import subprocess
import threading
import time
import re
import math
import json
from urllib.parse import urlparse
import requests
import telebot
from telebot import types

# ==================== CONFIGURATION ====================
BOT_TOKEN = "your_telegram_bot_token_here"
ALLOWED_USER_ID = 8927082329
DOWNLOAD_DIR = "/root/my-project/downloads"
YTDLP_BIN = "/usr/local/bin/yt-dlp"
if not os.path.exists(YTDLP_BIN):
    YTDLP_BIN = "yt-dlp"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Register Telegram Slash Command Menu
try:
    bot.set_my_commands([
        types.BotCommand("start", "🏠 Menu Utama & Panduan Bot"),
        types.BotCommand("traffic", "📈 Status Visitors & Traffic Website Portofolio"),
        types.BotCommand("files", "📁 Explorer & Kelola File VPS"),
        types.BotCommand("status", "📊 Status Storage Disk & RAM VPS"),
        types.BotCommand("clean", "🗑️ Hapus Semua File di VPS"),
        types.BotCommand("help", "ℹ️ Bantuan Penggunaan Bot")
    ])
except Exception as e:
    print(f"Warning setting commands menu: {e}")

USER_STATES = {}
PENDING_URLS = {}

# Security check
def is_authorized(user_id):
    return user_id == ALLOWED_USER_ID

def format_size(size_bytes):
    if not size_bytes or size_bytes == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

def format_duration(seconds):
    if not seconds:
        return "N/A"
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def make_progress_bar(percent, length=10):
    percent = max(0, min(100, percent))
    filled = int(round(length * percent / 100))
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {percent:.1f}%"

def get_file_emoji(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext in ['.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv', '.m4v']:
        return "🎬"
    elif ext in ['.mp3', '.m4a', '.flac', '.aac', '.ogg', '.wav']:
        return "🎵"
    elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.iso']:
        return "📦"
    elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        return "🖼️"
    elif ext in ['.pdf', '.doc', '.docx', '.txt', '.epub']:
        return "📄"
    elif ext in ['.apk', '.exe', '.deb', '.dmg', '.bin']:
        return "⚙️"
    return "📁"

# Helper: Parse single Nginx log line reliably
def parse_nginx_line(line):
    # Pattern matching Nginx combined format
    match = re.match(r'^(\S+) \S+ \S+ \[(.*?)\] "(\S+)\s+(\S+)\s+.*?" (\d+) (\S+) "(.*?)" "(.*?)"', line)
    if match:
        ip, date_str, method, path, status, size_str, ref, ua = match.groups()
        size_bytes = int(size_str) if size_str.isdigit() else 0
        return {
            "ip": ip,
            "date_str": date_str,
            "method": method,
            "path": path,
            "status": status,
            "size": size_bytes,
            "referer": ref,
            "user_agent": ua
        }
    return None

# GeoIP cache to avoid repeated lookups
GEO_CACHE = {}
def get_ip_location(ip):
    if ip in GEO_CACHE:
        return GEO_CACHE[ip]
    try:
        res = requests.get(f"http://ip-api.com/json/{ip}?fields=country,countryCode,city", timeout=2).json()
        if res and res.get("country"):
            city = res.get("city", "")
            code = res.get("countryCode", "")
            loc = f"{city}, {res['country']} ({code})" if city else f"{res['country']} ({code})"
            GEO_CACHE[ip] = loc
            return loc
    except Exception:
        pass
    GEO_CACHE[ip] = "Unknown Location"
    return "Unknown Location"

# Helper: Nginx Log Traffic Analytics
def get_traffic_stats():
    log_file = "/var/log/nginx/access.log"
    if not os.path.exists(log_file):
        return "❌ <b>Nginx access log tidak ditemukan di VPS.</b>"

    today_str = time.strftime("%d/%b/%Y")
    total_requests = 0
    unique_ips = set()
    total_bytes = 0
    pages = {}
    user_agents = {"Mobile": 0, "Desktop": 0, "Bot/Other": 0}
    recent_visitors = []

    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if today_str not in line:
                    continue
                parsed = parse_nginx_line(line)
                if not parsed:
                    continue
                
                ip = parsed["ip"]
                path = parsed["path"]
                ua = parsed["user_agent"]
                
                total_requests += 1
                unique_ips.add(ip)
                total_bytes += parsed["size"]
                
                # Filter static assets for top pages
                if not any(path.lower().endswith(ext) for ext in ['.css', '.js', '.png', '.jpg', '.ico', '.svg']):
                    pages[path] = pages.get(path, 0) + 1
                    
                # User Agent classification
                ua_lower = ua.lower()
                if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
                    user_agents["Mobile"] += 1
                elif "windows" in ua_lower or "macintosh" in ua_lower or "linux" in ua_lower:
                    user_agents["Desktop"] += 1
                else:
                    user_agents["Bot/Other"] += 1
                    
                recent_visitors.append((ip, parsed["date_str"], path))
    except Exception as e:
        return f"❌ <b>Error parsing log:</b> {str(e)}"

    top_pages_str = ""
    sorted_pages = sorted(pages.items(), key=lambda x: x[1], reverse=True)[:5]
    for p, c in sorted_pages:
        top_pages_str += f"• <code>{p}</code> — <b>{c} hits</b>\n"
    if not top_pages_str:
        top_pages_str = "• <code>/</code> (Home Page)\n"

    last_5_unique = []
    seen = set()
    for ip, date_str, path in reversed(recent_visitors):
        if ip not in seen:
            seen.add(ip)
            time_clean = date_str.split()[0].rsplit(':', 2)[1] + ":" + date_str.split()[0].rsplit(':', 2)[2] if ':' in date_str else date_str
            loc = get_ip_location(ip)
            last_5_unique.append(f"• IP: <code>{ip}</code> ({loc}) — {time_clean}")
        if len(last_5_unique) >= 5:
            break

    recent_str = "\n".join(last_5_unique) if last_5_unique else "Belum ada visitor hari ini."

    return (
        "📈 <b>WEBSITE TRAFFIC ANALYTICS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🌐 <b>Domain:</b> <code>https://daffaroffi.duckdns.org</code>\n"
        f"📅 <b>Hari Ini:</b> {today_str}\n\n"
        f"👥 <b>Total Pengunjung Unik (Unique IP):</b> <b>{len(unique_ips)} IP</b>\n"
        f"🔄 <b>Total HTTP Requests:</b> <b>{total_requests} Request</b>\n"
        f"💾 <b>Total Bandwidth Transfer:</b> <b>{format_size(total_bytes)}</b>\n\n"
        "📱 <b>Tipe Perangkat:</b>\n"
        f"• Mobile (HP): <b>{user_agents['Mobile']} hits</b>\n"
        f"• Desktop (PC/Laptop): <b>{user_agents['Desktop']} hits</b>\n"
        f"• Bot / Crawler / Search: <b>{user_agents['Bot/Other']} hits</b>\n\n"
        f"📄 <b>Halaman Terpopuler:</b>\n{top_pages_str}\n"
        f"👤 <b>Visitor Terakhir (IP & Lokasi):</b>\n{recent_str}"
    )

# Realtime Traffic Push Notifier Thread
def realtime_nginx_tailer():
    log_file = "/var/log/nginx/access.log"
    while not os.path.exists(log_file):
        time.sleep(5)
        
    last_notified_ip = {}
    print("Realtime Nginx Log Tailer Active!")
    
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            # Move to end of file to only monitor NEW incoming visits
            f.seek(0, os.SEEK_END)
            
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                
                parsed = parse_nginx_line(line)
                if not parsed:
                    continue
                    
                ip = parsed["ip"]
                path = parsed["path"]
                ua = parsed["user_agent"]
                
                # Ignore static assets (.css, .js, .svg, .png, .jpg, .ico)
                if any(path.lower().endswith(ext) for ext in ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.woff', '.woff2']):
                    continue
                if path.startswith("/stats"):
                    continue
                    
                # Rate limit per IP (1 alert per IP every 30 seconds)
                now = time.time()
                if ip in last_notified_ip and (now - last_notified_ip[ip]) < 30:
                    continue
                last_notified_ip[ip] = now
                
                # Clean User Agent description
                ua_lower = ua.lower()
                if "iphone" in ua_lower or "ipad" in ua_lower:
                    ua_clean = "📱 iPhone / iOS (Safari/Chrome)"
                elif "android" in ua_lower:
                    ua_clean = "📱 Android Mobile"
                elif "windows" in ua_lower:
                    ua_clean = "💻 Windows PC / Desktop"
                elif "macintosh" in ua_lower:
                    ua_clean = "💻 Mac / Apple Desktop"
                elif "linux" in ua_lower:
                    ua_clean = "💻 Linux System"
                else:
                    ua_clean = "🤖 Bot / Web Crawler"
                
                location = get_ip_location(ip)
                time_str = time.strftime('%H:%M:%S WIB')
                
                alert_text = (
                    "🚨 <b>NEW VISITOR DETECTED!</b> 🌐\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"👤 <b>Visitor IP:</b> <code>{ip}</code>\n"
                    f"🌍 <b>Lokasi:</b> <b>{location}</b>\n"
                    f"📍 <b>Halaman Target:</b> <code>{path}</code>\n"
                    f"📱 <b>Perangkat:</b> {ua_clean}\n"
                    f"🕒 <b>Waktu:</b> {time_str}\n\n"
                    f"🔍 <b>WHOIS & IP Details:</b>\nhttps://ipinfo.io/{ip}"
                )
                
                try:
                    bot.send_message(ALLOWED_USER_ID, alert_text, disable_web_page_preview=True)
                except Exception as e:
                    print(f"Error sending realtime alert to Telegram: {e}")
                    
    except Exception as e:
        print(f"Error in realtime_nginx_tailer loop: {e}")

# Helper: VPS System Health
def get_system_stats():
    total, used, free = shutil.disk_usage(DOWNLOAD_DIR)
    disk_percent = (used / total) * 100 if total else 0
    disk_bar = make_progress_bar(disk_percent, 12)
    
    mem_total, mem_available = 0, 0
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    mem_total = int(line.split()[1]) * 1024
                elif line.startswith("MemAvailable:"):
                    mem_available = int(line.split()[1]) * 1024
    except Exception:
        pass
    
    mem_used = mem_total - mem_available if mem_total else 0
    ram_percent = (mem_used / mem_total) * 100 if mem_total else 0
    ram_bar = make_progress_bar(ram_percent, 12)
    
    try:
        files = [f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))]
        file_count = len(files)
    except Exception:
        file_count = 0

    return (
        "📊 <b>DASHBOARD HEALTH VPS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💾 <b>Disk Storage (Folder Downloads):</b>\n"
        f"<code>{disk_bar}</code>\n"
        f"• Terpakai: <b>{format_size(used)}</b> / {format_size(total)}\n"
        f"• Sisa Bebas: <b>{format_size(free)}</b>\n\n"
        f"🧠 <b>RAM System Usage:</b>\n"
        f"<code>{ram_bar}</code>\n"
        f"• Terpakai: <b>{format_size(mem_used)}</b> / {format_size(mem_total)}\n"
        f"• Sisa Bebas: <b>{format_size(mem_available)}</b>\n\n"
        f"📂 <b>Total File VPS:</b> {file_count} File\n"
        f"📍 <b>Path:</b> <code>{DOWNLOAD_DIR}</code>"
    )

class MessageUpdater:
    def __init__(self, chat_id, msg_id):
        self.chat_id = chat_id
        self.msg_id = msg_id
        self.last_text = ""
        self.last_update = 0

    def update(self, text, markup=None, force=False):
        now = time.time()
        if not force and text == self.last_text:
            return
        if force or (now - self.last_update >= 2.0):
            try:
                bot.edit_message_text(text, self.chat_id, self.msg_id, reply_markup=markup)
                self.last_text = text
                self.last_update = now
            except Exception:
                pass

# Command: /start & /help
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if not is_authorized(message.from_user.id):
        bot.reply_to(message, "🚫 <b>Akses Ditolak!</b> Bot ini bersifat pribadi.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_traffic = types.InlineKeyboardButton("📈 Traffic Website", callback_data="cmd_traffic")
    btn_files = types.InlineKeyboardButton("📁 Explorer File", callback_data="cmd_files_p0")
    btn_status = types.InlineKeyboardButton("📊 System Health", callback_data="cmd_status")
    btn_clean = types.InlineKeyboardButton("🗑️ Hapus Semua File", callback_data="cmd_clean_all")
    markup.add(btn_traffic)
    markup.add(btn_files, btn_status)
    markup.add(btn_clean)
    
    text = (
        "⚡ <b>REALTIME TRAFFIC & AUTOMATION BOT PRO</b> ⚡\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔔 <b>Realtime Visitor Push Alert:</b>\n"
        "└ Bot otomatis mengabari IP Visitor & Lokasinya secara INSTAN setiap ada kunjungan ke website kamu!\n\n"
        "📈 <b>Laporan Traffic Website Portofolio:</b>\n"
        "└ Tekan /traffic untuk melihat statistik visitor & IP unik.\n\n"
        "🎬 <b>Smart Downloader Video / Sosmed:</b>\n"
        "└ Kirimkan link video/sosmed/direct link untuk mengunduh secara otomatis via VPS.\n\n"
        "🌐 <b>Website Portfolio:</b>\n"
        "<code>https://daffaroffi.duckdns.org</code>"
    )
    bot.send_message(message.chat.id, text, reply_markup=markup)

# Command: /traffic
@bot.message_handler(commands=['traffic'])
def handle_traffic(message):
    if not is_authorized(message.from_user.id):
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔄 Refresh Traffic", callback_data="cmd_traffic"),
        types.InlineKeyboardButton("📊 System Health", callback_data="cmd_status")
    )
    bot.reply_to(message, get_traffic_stats(), reply_markup=markup)

# Command: /status
@bot.message_handler(commands=['status'])
def handle_status(message):
    if not is_authorized(message.from_user.id):
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔄 Refresh Status", callback_data="cmd_status"),
        types.InlineKeyboardButton("📈 Traffic Website", callback_data="cmd_traffic")
    )
    bot.reply_to(message, get_system_stats(), reply_markup=markup)

# Command: /files
@bot.message_handler(commands=['files'])
def handle_files(message):
    if not is_authorized(message.from_user.id):
        return
    show_files_menu(message.chat.id, page=0)

# Paginated File Explorer
def show_files_menu(chat_id, page=0, message_id=None):
    try:
        files = [f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))]
    except Exception:
        files = []
    
    if not files:
        text = (
            "📁 <b>FILE EXPLORER VPS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📭 <i>Folder download di VPS masih kosong.</i>"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="cmd_files_p0"))
        if message_id:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
        else:
            bot.send_message(chat_id, text, reply_markup=markup)
        return
    
    files_info = []
    for f in files:
        path = os.path.join(DOWNLOAD_DIR, f)
        files_info.append((f, os.path.getmtime(path), os.path.getsize(path)))
    files_info.sort(key=lambda x: x[1], reverse=True)
    
    PER_PAGE = 5
    total_pages = math.ceil(len(files_info) / PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    
    start_idx = page * PER_PAGE
    end_idx = start_idx + PER_PAGE
    current_files = files_info[start_idx:end_idx]
    
    text = (
        "📂 <b>FILE EXPLORER VPS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Total File:</b> {len(files_info)} File | <b>Halaman:</b> {page + 1}/{total_pages}\n\n"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for i, (fname, mtime, fsize) in enumerate(current_files, start_idx + 1):
        emoji = get_file_emoji(fname)
        text += f"<b>{i}. {emoji} {fname}</b>\n└ 💾 {format_size(fsize)}\n\n"
        
        btn_label = f"{emoji} {fname[:26]}..." if len(fname) > 29 else f"{emoji} {fname}"
        markup.add(types.InlineKeyboardButton(btn_label, callback_data=f"fopt:{fname}"))
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton("◀️ Prev", callback_data=f"cmd_files_p{page - 1}"))
    nav_buttons.append(types.InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="cmd_ignore"))
    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton("Next ▶️", callback_data=f"cmd_files_p{page + 1}"))
    
    markup.row(*nav_buttons)
    markup.add(
        types.InlineKeyboardButton("📈 Traffic Website", callback_data="cmd_traffic"),
        types.InlineKeyboardButton("🗑️ Clean All", callback_data="cmd_clean_all")
    )
    
    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

# Command: /clean
@bot.message_handler(commands=['clean'])
def handle_clean(message):
    if not is_authorized(message.from_user.id):
        return
    confirm_clean_all(message.chat.id)

def confirm_clean_all(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ HAPUS SEMUA", callback_data="do_clean_all"),
        types.InlineKeyboardButton("❌ BATAL", callback_data="cmd_files_p0")
    )
    text = (
        "⚠️ <b>KONFIRMASI HAPUS SEMUA FILE!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Apakah Anda yakin ingin menghapus <b>SEMUA FILE</b> di folder download VPS?"
    )
    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

# Master Link Detector & Downloader Dispatcher
@bot.message_handler(func=lambda msg: msg.text and (msg.text.startswith("http://") or msg.text.startswith("https://")))
def handle_download_url(message):
    if not is_authorized(message.from_user.id):
        bot.reply_to(message, "🚫 <b>Akses Ditolak!</b>")
        return
    
    url = message.text.strip()
    status_msg = bot.reply_to(message, "🔍 <b>Menganalisis Link...</b> Memeriksa tipe & resolusi media.")
    
    thread = threading.Thread(target=analyze_link_and_prompt, args=(message.chat.id, url, status_msg.message_id))
    thread.start()

# Link Analyzer & Resolution Selector Menu
def analyze_link_and_prompt(chat_id, url, msg_id):
    updater = MessageUpdater(chat_id, msg_id)
    
    # 1. Direct Extension Instant Match
    parsed = urlparse(url)
    path = parsed.path.lower()
    direct_exts = [
        '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.iso', '.pdf', '.apk', '.exe',
        '.dmg', '.bin', '.deb'
    ]
    if any(path.endswith(ext) for ext in direct_exts):
        updater.update("⚡ <b>[Direct File Terdeteksi]</b> Mengunduh via Aria2c Multi-thread...", force=True)
        run_aria2c_engine(updater, url)
        return

    # 2. Media / Streaming Link -> Probe Metadata for Resolution Options
    updater.update("🔍 <b>[Memeriksa Info Media & Resolusi]</b> Mengambil metadata...", force=True)
    
    info = None
    try:
        cmd_probe = [YTDLP_BIN, "--dump-json", "--no-warnings", url]
        res = subprocess.run(cmd_probe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
        if res.returncode == 0 and res.stdout.strip():
            info = json.loads(res.stdout.splitlines()[0])
    except Exception:
        pass

    if info:
        title = info.get("title", "Media Video")
        duration = format_duration(info.get("duration"))
        uploader = info.get("uploader", info.get("extractor_key", "Unknown"))
        
        PENDING_URLS[msg_id] = {
            "url": url,
            "title": title
        }
        
        text = (
            "🎬 <b>MEDIA VIDEO TERDETEKSI!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📌 <b>Judul:</b> {title}\n"
            f"⏱️ <b>Durasi:</b> {duration} | 👤 <b>Uploader:</b> {uploader}\n\n"
            "👇 <b>Silakan pilih format/resolusi yang ingin di-download:</b>"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_1080 = types.InlineKeyboardButton("🎥 1080p Full HD", callback_data=f"res:1080:{msg_id}")
        btn_720  = types.InlineKeyboardButton("🎬 720p HD", callback_data=f"res:720:{msg_id}")
        btn_480  = types.InlineKeyboardButton("📱 480p SD", callback_data=f"res:480:{msg_id}")
        btn_360  = types.InlineKeyboardButton("⚡ 360p Compact", callback_data=f"res:360:{msg_id}")
        btn_mp3  = types.InlineKeyboardButton("🎵 MP3 Audio Only", callback_data=f"res:mp3:{msg_id}")
        btn_best = types.InlineKeyboardButton("🚀 Auto Best Quality", callback_data=f"res:best:{msg_id}")
        
        markup.add(btn_1080, btn_720)
        markup.add(btn_480, btn_360)
        markup.add(btn_mp3, btn_best)
        
        updater.update(text, markup=markup, force=True)
        return

    # 3. Direct Link / Unknown Link Fallback to Aria2c
    updater.update("⚡ <b>[Direct Link Terdeteksi]</b> Mengunduh via Aria2c Engine...", force=True)
    run_aria2c_engine(updater, url)

# Engine 1: Aria2c Downloader (16 Threads)
def run_aria2c_engine(updater, url):
    before_files = set(os.listdir(DOWNLOAD_DIR))
    start_time = time.time()

    cmd = [
        "aria2c",
        "-x", "16",
        "-s", "16",
        "-k", "1M",
        "--min-split-size=1M",
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "-d", DOWNLOAD_DIR,
        "--summary-interval=1",
        "--console-log-level=notice",
        url
    ]
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    for line in iter(process.stdout.readline, ''):
        if not line:
            break
        match = re.search(r'\[#[0-9a-f]+\s+([0-9\.\w]+)/([0-9\.\w]+)\((\d+)%\)\s+CN:\d+\s+DL:([0-9\.\w]+)\s+ETA:([^\]]+)\]', line)
        if match:
            dl_str, total_str, percent_num, speed_str, eta_str = match.groups()
            percent = float(percent_num)
            bar = make_progress_bar(percent, 10)
            
            text = (
                "📥 <b>DOWNLOADING (Aria2c Multi-thread)</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<code>{bar}</code>\n\n"
                f"⚡ <b>Kecepatan:</b> {speed_str}/s\n"
                f"📦 <b>Progress:</b> {dl_str} / {total_str}\n"
                f"⏱️ <b>ETA:</b> {eta_str}\n"
                f"📍 <b>Path VPS:</b> <code>{DOWNLOAD_DIR}</code>"
            )
            updater.update(text)
            
    process.wait()
    elapsed = round(time.time() - start_time, 1)

    after_files = set(os.listdir(DOWNLOAD_DIR))
    new_files = list(after_files - before_files)
    
    if new_files:
        fname = new_files[0]
        finalize_download_success(updater, fname, elapsed)
    elif process.returncode == 0:
        files = [os.path.join(DOWNLOAD_DIR, f) for f in os.listdir(DOWNLOAD_DIR)]
        if files:
            latest_file = max(files, key=os.path.getctime)
            fname = os.path.basename(latest_file)
            finalize_download_success(updater, fname, elapsed)
        else:
            updater.update("⚠️ <b>Download Selesai tetapi file tidak ditemukan.</b>", force=True)
    else:
        updater.update("❌ <b>Download Gagal via Aria2c.</b> Silakan periksa kembali link Anda.", force=True)

# Engine 2: yt-dlp Downloader with Specific Resolution & Fast Remux
def run_ytdlp_engine(updater, url, mode="best"):
    before_files = set(os.listdir(DOWNLOAD_DIR))
    start_time = time.time()

    output_template = os.path.join(DOWNLOAD_DIR, "%(title).100s.%(ext)s")
    
    cmd = [
        YTDLP_BIN,
        "-o", output_template,
        "--no-playlist",
        "--newline",
        "--no-mtime",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "--downloader", "aria2c",
        "--downloader-args", "aria2c:-x 16 -s 16 -k 1M"
    ]
    
    if mode == "mp3":
        cmd.extend(["-x", "--audio-format", "mp3", "--audio-quality", "0"])
        mode_title = "MP3 Audio"
    elif mode == "1080":
        cmd.extend(["-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/best[height<=1080]", "--merge-output-format", "mp4"])
        mode_title = "1080p Full HD"
    elif mode == "720":
        cmd.extend(["-f", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/bv*[height<=720]+ba/best[height<=720]", "--merge-output-format", "mp4"])
        mode_title = "720p HD"
    elif mode == "480":
        cmd.extend(["-f", "bv*[height<=480][ext=mp4]+ba[ext=m4a]/bv*[height<=480]+ba/best[height<=480]", "--merge-output-format", "mp4"])
        mode_title = "480p SD"
    elif mode == "360":
        cmd.extend(["-f", "bv*[height<=360][ext=mp4]+ba[ext=m4a]/bv*[height<=360]+ba/best[height<=360]", "--merge-output-format", "mp4"])
        mode_title = "360p Compact"
    else: # "best"
        cmd.extend(["-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bestvideo+bestaudio/best", "--merge-output-format", "mp4"])
        mode_title = "Auto Best Quality"

    cmd.append(url)

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    for line in iter(process.stdout.readline, ''):
        if not line:
            break
        match = re.search(r'\[download\]\s+(\d+\.\d+)%\s+of\s+~?([0-9\.\w]+)\s+at\s+([0-9\.\w]+/s)\s+ETA\s+([0-9:]+)', line)
        if match:
            percent_str, total_str, speed_str, eta_str = match.groups()
            percent = float(percent_str)
            bar = make_progress_bar(percent, 10)
            
            text = (
                f"📥 <b>DOWNLOADING ({mode_title})</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<code>{bar}</code>\n\n"
                f"⚡ <b>Kecepatan:</b> {speed_str}\n"
                f"📦 <b>Ukuran:</b> ~{total_str}\n"
                f"⏱️ <b>ETA:</b> {eta_str}\n"
                f"📍 <b>Path VPS:</b> <code>{DOWNLOAD_DIR}</code>"
            )
            updater.update(text)
            
    process.wait()
    elapsed = round(time.time() - start_time, 1)

    after_files = set(os.listdir(DOWNLOAD_DIR))
    new_files = list(after_files - before_files)
    
    if new_files:
        fname = new_files[0]
        finalize_download_success(updater, fname, elapsed)
    elif process.returncode == 0:
        files = [os.path.join(DOWNLOAD_DIR, f) for f in os.listdir(DOWNLOAD_DIR)]
        if files:
            latest_file = max(files, key=os.path.getctime)
            fname = os.path.basename(latest_file)
            finalize_download_success(updater, fname, elapsed)
        else:
            updater.update("⚠️ <b>Media berhasil di-download tetapi file tidak ditemukan.</b>", force=True)
    else:
        updater.update("⚠️ <b>yt-dlp gagal, mengalihkan otomatis ke Aria2c Direct...</b>", force=True)
        run_aria2c_engine(updater, url)

# Completion Card Renderer
def finalize_download_success(updater, fname, elapsed):
    fpath = os.path.join(DOWNLOAD_DIR, fname)
    fsize = os.path.getsize(fpath) if os.path.exists(fpath) else 0
    emoji = get_file_emoji(fname)
    
    text = (
        "✅ <b>DOWNLOAD SELESAI & TERSIMPAN!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📄 <b>Nama File:</b> {emoji} <code>{fname}</code>\n"
        f"📊 <b>Ukuran:</b> 💾 {format_size(fsize)}\n"
        f"⏱️ <b>Waktu Transaksi:</b> 🕒 {elapsed} detik\n"
        f"📍 <b>Path VPS:</b> <code>{fpath}</code>"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_tg = types.InlineKeyboardButton("📤 Kirim ke Telegram", callback_data=f"send_fn:{fname}")
    btn_del = types.InlineKeyboardButton("🗑️ Hapus File", callback_data=f"del_fn:{fname}")
    btn_exp = types.InlineKeyboardButton("📁 Explorer File VPS", callback_data="cmd_files_p0")
    
    markup.add(btn_tg, btn_del)
    
    ext = os.path.splitext(fname)[1].lower()
    if ext in ['.mp4', '.mkv', '.webm', '.avi', '.mov']:
        markup.add(types.InlineKeyboardButton("🎵 Extract Ke MP3 Audio", callback_data=f"convert_mp3:{fname}"))
        
    markup.add(btn_exp)
    
    updater.update(text, markup=markup, force=True)

# Convert Video to MP3 Audio
def convert_to_mp3(chat_id, fname, msg_id):
    fpath = os.path.join(DOWNLOAD_DIR, fname)
    if not os.path.exists(fpath):
        bot.send_message(chat_id, "❌ File tidak ditemukan di VPS.")
        return

    base_name = os.path.splitext(fname)[0]
    out_mp3_name = f"{base_name}.mp3"
    out_mp3_path = os.path.join(DOWNLOAD_DIR, out_mp3_name)

    updater = MessageUpdater(chat_id, msg_id)
    updater.update(f"🔄 <b>Mengonversi</b> <code>{fname}</code> ke MP3...", force=True)

    cmd = ["ffmpeg", "-y", "-i", fpath, "-vn", "-acodec", "libmp3lame", "-q:a", "2", out_mp3_path]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if res.returncode == 0 and os.path.exists(out_mp3_path):
        mp3_size = os.path.getsize(out_mp3_path)
        text = (
            "✅ <b>EKSTRAKSI MP3 BERHASIL!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎵 <b>File Audio:</b> <code>{out_mp3_name}</code>\n"
            f"📊 <b>Ukuran:</b> 💾 {format_size(mp3_size)}\n"
            f"📍 <b>Path VPS:</b> <code>{out_mp3_path}</code>"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📤 Kirim MP3 ke TG", callback_data=f"send_fn:{out_mp3_name}"),
            types.InlineKeyboardButton("📁 Explorer File", callback_data="cmd_files_p0")
        )
        updater.update(text, markup=markup, force=True)
    else:
        updater.update("❌ <b>Gagal mengonversi file ke MP3.</b>", force=True)

# Callback Router
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if not is_authorized(call.from_user.id):
        bot.answer_callback_query(call.id, "🚫 Akses ditolak!", show_alert=True)
        return
    
    data = call.data
    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    
    if data == "cmd_ignore":
        bot.answer_callback_query(call.id)
        return

    elif data == "cmd_traffic":
        bot.answer_callback_query(call.id, "Mengambil data traffic terbaru...")
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🔄 Refresh Traffic", callback_data="cmd_traffic"),
            types.InlineKeyboardButton("📊 System Health", callback_data="cmd_status")
        )
        try:
            bot.edit_message_text(get_traffic_stats(), chat_id, msg_id, reply_markup=markup)
        except Exception:
            bot.send_message(chat_id, get_traffic_stats(), reply_markup=markup)
        
    elif data.startswith("res:"):
        parts = data.split(":")
        mode = parts[1]
        target_msg_id = int(parts[2])
        
        url_data = PENDING_URLS.pop(target_msg_id, None)
        if not url_data:
            bot.answer_callback_query(call.id, "⚠️ Sesi pilihan resolusi telah kadaluarsa.", show_alert=True)
            return
            
        url = url_data["url"]
        bot.answer_callback_query(call.id, f"Memulai download ({mode})...")
        
        updater = MessageUpdater(chat_id, msg_id)
        updater.update(f"⏳ <b>Memulai Download ({mode})...</b>", force=True)
        
        threading.Thread(target=run_ytdlp_engine, args=(updater, url, mode)).start()

    elif data.startswith("cmd_files_p"):
        bot.answer_callback_query(call.id)
        page = int(data.replace("cmd_files_p", ""))
        show_files_menu(chat_id, page=page, message_id=msg_id)
        
    elif data == "cmd_status":
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🔄 Refresh Status", callback_data="cmd_status"),
            types.InlineKeyboardButton("📈 Traffic Website", callback_data="cmd_traffic")
        )
        try:
            bot.edit_message_text(get_system_stats(), chat_id, msg_id, reply_markup=markup)
        except Exception:
            bot.send_message(chat_id, get_system_stats(), reply_markup=markup)
            
    elif data == "cmd_clean_all":
        bot.answer_callback_query(call.id)
        confirm_clean_all(chat_id, msg_id)
        
    elif data == "do_clean_all":
        bot.answer_callback_query(call.id, "Menghapus semua file...")
        count = 0
        for f in os.listdir(DOWNLOAD_DIR):
            fp = os.path.join(DOWNLOAD_DIR, f)
            try:
                if os.path.isfile(fp):
                    os.remove(fp)
                    count += 1
                elif os.path.isdir(fp):
                    shutil.rmtree(fp)
                    count += 1
            except Exception:
                pass
        text = f"✅ <b>BERHASIL DIBERSIHKAN!</b>\nBerhasil menghapus {count} file dari VPS."
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📁 Explorer File", callback_data="cmd_files_p0"))
        bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup)

    elif data.startswith("convert_mp3:"):
        fname = data.split("convert_mp3:", 1)[1]
        bot.answer_callback_query(call.id, "Memproses ekstraksi MP3...")
        threading.Thread(target=convert_to_mp3, args=(chat_id, fname, msg_id)).start()

    elif data.startswith("fopt:"):
        fname = data.split("fopt:", 1)[1]
        fpath = os.path.join(DOWNLOAD_DIR, fname)
        bot.answer_callback_query(call.id)
        
        if not os.path.exists(fpath):
            bot.answer_callback_query(call.id, "File tidak ditemukan di VPS!", show_alert=True)
            show_files_menu(chat_id, page=0, message_id=msg_id)
            return
            
        fsize = os.path.getsize(fpath)
        mtime_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(fpath)))
        emoji = get_file_emoji(fname)
        
        text = (
            f"📄 <b>DETAIL FILE VPS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>File:</b> {emoji} <code>{fname}</code>\n"
            f"<b>Ukuran:</b> 💾 {format_size(fsize)}\n"
            f"<b>Tgl Simpan:</b> 🕒 {mtime_str}\n"
            f"<b>Path VPS:</b> <code>{fpath}</code>"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_send = types.InlineKeyboardButton("📤 Kirim Ke TG", callback_data=f"send_fn:{fname}")
        btn_rename = types.InlineKeyboardButton("✏️ Ubah Nama", callback_data=f"rename_fn:{fname}")
        btn_del = types.InlineKeyboardButton("🗑️ Hapus File", callback_data=f"del_fn:{fname}")
        btn_back = types.InlineKeyboardButton("⬅️ Kembali", callback_data="cmd_files_p0")
        
        markup.add(btn_send, btn_rename)
        
        ext = os.path.splitext(fname)[1].lower()
        if ext in ['.mp4', '.mkv', '.webm', '.avi', '.mov']:
            markup.add(types.InlineKeyboardButton("🎵 Extract Ke MP3 Audio", callback_data=f"convert_mp3:{fname}"))

        markup.add(btn_del, btn_back)
        
        bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup)

    elif data.startswith("send_fn:"):
        fname = data.split("send_fn:", 1)[1]
        fpath = os.path.join(DOWNLOAD_DIR, fname)
        if not os.path.exists(fpath):
            bot.answer_callback_query(call.id, "File tidak ditemukan di VPS!", show_alert=True)
            return
        
        fsize = os.path.getsize(fpath)
        if fsize > 50 * 1024 * 1024:
            bot.answer_callback_query(call.id, "Ukuran file > 50MB (Batas Maksimal Bot API Standard Telegram)!", show_alert=True)
            bot.send_message(
                chat_id,
                f"⚠️ <b>FILE MELEBIHI LIMIT TELEGRAM BOT API (50 MB)!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📄 <b>File:</b> <code>{fname}</code>\n"
                f"💾 <b>Ukuran:</b> {format_size(fsize)}\n\n"
                "<i>Telegram Bot API membatasi pengunggahan file dari Bot hingga maksimal 50 MB.</i>\n\n"
                "📍 <b>File tersimpan dengan aman di VPS:</b>\n"
                f"<code>{fpath}</code>"
            )
            return
        
        bot.answer_callback_query(call.id, "Mengunggah file ke Telegram...")
        status_sending = bot.send_message(chat_id, f"📤 <b>Mengunggah</b> <code>{fname}</code> ({format_size(fsize)})...")
        
        def upload_thread():
            try:
                ext = os.path.splitext(fname)[1].lower()
                with open(fpath, 'rb') as f:
                    if ext in ['.mp4', '.mkv', '.webm', '.mov']:
                        bot.send_video(chat_id, f, caption=f"🎬 <code>{fname}</code>")
                    elif ext in ['.mp3', '.m4a', '.flac', '.wav', '.aac']:
                        bot.send_audio(chat_id, f, caption=f"🎵 <code>{fname}</code>")
                    else:
                        bot.send_document(chat_id, f, caption=f"📄 <code>{fname}</code>")
                bot.delete_message(chat_id, status_sending.message_id)
            except Exception as e:
                bot.edit_message_text(f"❌ <b>Gagal mengirim file:</b> {str(e)}", chat_id, status_sending.message_id)

        threading.Thread(target=upload_thread).start()

    elif data.startswith("rename_fn:"):
        fname = data.split("rename_fn:", 1)[1]
        bot.answer_callback_query(call.id)
        
        USER_STATES[call.from_user.id] = {
            "action": "rename",
            "old_filename": fname
        }
        
        bot.send_message(
            chat_id,
            f"✏️ <b>UBAH NAMA FILE</b>\n\n"
            f"File Asal: <code>{fname}</code>\n\n"
            "Ketikkan nama file baru yang Anda inginkan:"
        )

    elif data.startswith("del_fn:"):
        fname = data.split("del_fn:", 1)[1]
        fpath = os.path.join(DOWNLOAD_DIR, fname)
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
                bot.answer_callback_query(call.id, "File berhasil dihapus dari VPS!", show_alert=True)
            except Exception as e:
                bot.answer_callback_query(call.id, f"Gagal menghapus: {str(e)}", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "File sudah dihapus.", show_alert=True)
        
        show_files_menu(chat_id, page=0, message_id=msg_id)

if __name__ == '__main__':
    print(f"Starting Smart Downloader PRO & IP Traffic Notifier for User ID {ALLOWED_USER_ID}...")
    
    # Start Realtime Nginx Log Tailer Thread in background
    tailer_thread = threading.Thread(target=realtime_nginx_tailer, daemon=True)
    tailer_thread.start()
    
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
