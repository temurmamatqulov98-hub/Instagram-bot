import os
import glob
import time
import threading
from datetime import datetime, timezone
from flask import Flask
import telebot
import instaloader

# Render uchun web server
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot 24/7 rejimda faol!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# --- SOZLAMALAR ---
BOT_TOKEN = "9154702002:AAEP2gpIhAx9xxe4ry65EP1PqzvroCfXzxA"
DOWNLOAD_DIR = "temp_reels"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
bot = telebot.TeleBot(BOT_TOKEN)

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

# Agar zaxira Instagram akkauntingiz bo'lsa, quyidagi 2 qatordagi panjarani (#) olib, login-parolni yozsangiz 100% hech qanday cheklovlarsiz ishlaydi:
# L.login("INSTAGRAM_LOGIN", "INSTAGRAM_PAROL")

def clean_temp_files(shortcode):
    for f in glob.glob(os.path.join(DOWNLOAD_DIR, f"*{shortcode}*")):
        try:
            os.remove(f)
        except Exception:
            pass

def send_pure_video(chat_id, post):
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
    bot.reply_to(message, "Salom! Men Instagram Reels yuklovchi botman. Menga yulduzning profilini yoki heshtegni yozing (masalan: <code>cristiano</code> yoki <code>kimyoujung</code>).", parse_mode="HTML")

@bot.message_handler(func=lambda msg: True)
def handle_query(message):
    # Probellarni va belgilarni avtomatik tozalaymiz (kim you jung -> kimyoujung)
    query = message.text.strip().lower().replace("@", "").replace("#", "").replace(" ", "")

    status = bot.reply_to(message, f"⚡ '{query}' bo'yicha videolar qidirilmoqda...")

    found = []

    # 1. Profil sifatida tekshirish
    try:
        profile = instaloader.Profile.from_username(L.context, query)
        c = 0
        for p in profile.get_posts():
            if p.is_video:
                found.append((p.video_view_count or p.likes or 0, p))
            c += 1
            if c >= 15:
                break
    except Exception:
        pass

    # 2. Agar profildan topilmasa, toza heshtegdan qidirish
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
        except Exception:
            pass

    if not found:
        bot.edit_message_text(f"❌ '{query}' bo'yicha video topilmadi. Profil nomini to'g'ri kiritganingizga ishonch hosil qiling (masalan: cristiano, khaby00).", message.chat.id, status.message_id)
        return

    # Ko'rishlar bo'yicha saralash
    found.sort(key=lambda x: x[0], reverse=True)
    top_videos = [p for _, p in found[:10]]

    bot.edit_message_text(f"🔥 {len(top_videos)} ta sara video topildi! Bittalab yuborilmoqda...", message.chat.id, status.message_id)

    for p in top_videos:
        send_pure_video(message.chat.id, p)
        time.sleep(1)

if __name__ == "__main__":
    print("Bot ishga tushdi...")
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=20, skip_pending=True)
        except Exception:
            time.sleep(5)
