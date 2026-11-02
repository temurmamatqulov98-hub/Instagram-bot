import os
import glob
import time
import threading
from datetime import datetime, timezone
from flask import Flask
import telebot
import instaloader

# Render serveri uxlab qolmasligi uchun web server
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Render'da 24/7 faol ishlamoqda!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# --- SOZLAMALAR ---
BOT_TOKEN = "9154702002:AAEP2gpIhAx9xxe4ry65EP1PqzvroCfXzxA"
DOWNLOAD_DIR = "temp_reels"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
bot = telebot.TeleBot(BOT_TOKEN)

# Instaloader
L = instaloader.Instaloader(
    download_pictures=False,
    download_videos=True,
    download_video_thumbnails=False,
    download_geotags=False,
    download_comments=False,
    save_metadata=False,
    dirname_pattern=DOWNLOAD_DIR,
    filename_pattern="{shortcode}"
)

L.context.max_connection_attempts = 1

# Render Environment'dan login va parolni yuklash
INSTA_USER = os.environ.get("INSTA_USER", "music_dj_nexor")
INSTA_PASS = os.environ.get("INSTA_PASS")

if INSTA_USER and INSTA_PASS:
    try:
        print(f"Instagram akkauntiga kirilmoqda (@{INSTA_USER})...", flush=True)
        L.login(INSTA_USER, INSTA_PASS)
        print("✅ Instagram tizimiga muvaffaqiyatli kirildi!", flush=True)
    except Exception as e:
        print(f"⚠️ Kirish holati: {e}", flush=True)

def clean_temp_files(shortcode):
    for f in glob.glob(os.path.join(DOWNLOAD_DIR, f"*{shortcode}*")):
        try:
            os.remove(f)
        except Exception:
            pass

def send_pure_video(chat_id, post):
    """Faqat toza video faylini Telegramga yuborish"""
    shortcode = post.shortcode
    try:
        L.download_post(post, target=DOWNLOAD_DIR)
        video_files = glob.glob(os.path.join(DOWNLOAD_DIR, f"*{shortcode}*.mp4"))

        if not video_files:
            return False

        with open(video_files[0], "rb") as video:
            bot.send_video(
                chat_id=chat_id,
                video=video,
                caption=None,
                supports_streaming=True
            )

        clean_temp_files(shortcode)
        return True
    except Exception as e:
        clean_temp_files(shortcode)
        return False

@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.reply_to(
        message,
        "Assalomu alaykum! Men to'liq onlayn ishlovchi Reels yuklovchi botman.\n\n"
        "Menga yulduzning profilini yoki heshtegni yozing (masalan: <code>you_r_love</code> yoki <code>cristiano</code>).",
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda msg: True)
def handle_query(message):
    query = message.text.strip().lower().replace("@", "").replace("#", "").replace(" ", "")

    status = bot.reply_to(message, f"⚡ '{query}' bo'yicha Instagram tahlil qilinmoqda...")

    found = []

    # 1. Profil sifatida tekshirish
    try:
        profile = instaloader.Profile.from_username(L.context, query)
        c = 0
        for p in profile.get_posts():
            if p.is_video:
                found.append((p.video_view_count or p.likes or 0, p))
            c += 1
            if c >= 20:
                break
    except Exception as e:
        print(f"Profil xatosi: {e}", flush=True)

    # 2. Heshteglardan eng ko'p ko'rilganlarini qidirish
    if len(found) < 3:
        try:
            ht = instaloader.Hashtag.from_name(L.context, query)
            c = 0
            for p in ht.get_top_posts():
                if p.is_video:
                    found.append((p.video_view_count or p.likes or 0, p))
                c += 1
                if c >= 15:
                    break
        except Exception as e:
            print(f"Heshteg xatosi: {e}", flush=True)

    if not found:
        bot.edit_message_text(
            f"❌ '{query}' bo'yicha video topilmadi. Nom to'g'ri yozilganini tekshiring.",
            message.chat.id,
            status.message_id
        )
        return

    # Ko'rishlar soni bo'yicha saralash
    found.sort(key=lambda x: x[0], reverse=True)
    top_videos = [p for _, p in found[:10]]

    bot.edit_message_text(f"🔥 {len(top_videos)} ta sara video topildi! Bittalab yuborilmoqda...", message.chat.id, status.message_id)

    for p in top_videos:
        send_pure_video(message.chat.id, p)
        time.sleep(1)

if __name__ == "__main__":
    print("Bot Render'da ishga tushdi...", flush=True)
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=20, skip_pending=True)
        except Exception:
            time.sleep(5)
