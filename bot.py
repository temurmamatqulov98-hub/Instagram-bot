import os
import glob
import time
import threading
from datetime import datetime, timezone
from flask import Flask
import telebot
import instaloader

# Render.com da 24/7 uxlab qolmasligi uchun fon Web-serveri
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot 24/7 rejimda faol ishlayapti!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# --- SOZLAMALAR ---
BOT_TOKEN = "9154702002:AAEP2gpIhAx9xxe4ry65EP1PqzvroCfXzxA"
DOWNLOAD_DIR = "temp_reels"
CHECK_INTERVAL_SECONDS = 300
RECENT_HOURS_LIMIT = 5

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

tracked_queries = {}
lock = threading.Lock()

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
        print(f"Yuklashda xato ({shortcode}): {e}")
        clean_temp_files(shortcode)
        return False

def is_recent(post, hours=5):
    try:
        now = datetime.now(timezone.utc)
        post_time = post.date_utc.replace(tzinfo=timezone.utc)
        return (now - post_time).total_seconds() / 3600 <= hours
    except Exception:
        return False

def scan_all_instagram(query):
    candidates = {}
    recent_videos = []

    try:
        profile = instaloader.Profile.from_username(L.context, query)
        p_count = 0
        for post in profile.get_posts():
            if post.is_video:
                candidates[post.shortcode] = post
                if is_recent(post, RECENT_HOURS_LIMIT):
                    recent_videos.append(post)
            p_count += 1
            if p_count >= 25:
                break

        try:
            t_count = 0
            for post in profile.get_tagged_posts():
                if post.is_video and post.shortcode not in candidates:
                    candidates[post.shortcode] = post
                    if is_recent(post, RECENT_HOURS_LIMIT):
                        recent_videos.append(post)
                t_count += 1
                if t_count >= 15:
                    break
        except Exception:
            pass
    except Exception as e:
        print(f"Profil xatosi: {e}")

    hashtags = [query, f"{query}reels"]
    for tag in hashtags:
        try:
            ht = instaloader.Hashtag.from_name(L.context, tag)
            for post in ht.get_top_posts():
                if post.is_video and post.shortcode not in candidates:
                    candidates[post.shortcode] = post
                    if is_recent(post, RECENT_HOURS_LIMIT):
                        recent_videos.append(post)
                if len(candidates) >= 40:
                    break
        except Exception:
            continue

    return candidates, recent_videos

def monitor_loop():
    while True:
        try:
            time.sleep(CHECK_INTERVAL_SECONDS)
            with lock:
                items = list(tracked_queries.items())

            for query, data in items:
                all_found, _ = scan_all_instagram(query)
                for sc, post in all_found.items():
                    if sc not in data["seen_shortcodes"]:
                        data["seen_shortcodes"].add(sc)
                        for chat_id in data["chat_ids"]:
                            send_pure_video(chat_id, post)
                            time.sleep(2)
        except Exception as e:
            print(f"Monitoring xatosi: {e}")
            time.sleep(60)

@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.reply_to(message, "Tayyorman! Menga istalgan nomni yozing (masalan: <code>cristiano</code>).", parse_mode="HTML")

@bot.message_handler(func=lambda msg: True)
def handle_query(message):
    query = message.text.strip().lower().replace("@", "").replace("#", "")
    status_msg = bot.reply_to(message, f"⚡ '{query}' bo'yicha qidirilmoqda, videolar hoziroq kela boshlaydi...")

    all_found, recent_videos = scan_all_instagram(query)

    if not all_found:
        bot.edit_message_text(f"❌ '{query}' bo'yicha video topilmadi.", message.chat.id, status_msg.message_id)
        return

    sorted_by_views = sorted(
        all_found.values(),
        key=lambda p: (p.video_view_count or p.likes or 0),
        reverse=True
    )

    to_send = []
    sent_ids = set()

    for p in recent_videos:
        if p.shortcode not in sent_ids:
            to_send.append(p)
            sent_ids.add(p.shortcode)

    for p in sorted_by_views:
        if p.shortcode not in sent_ids:
            to_send.append(p)
            sent_ids.add(p.shortcode)
        if len(to_send) >= 12:
            break

    try:
        bot.delete_message(message.chat.id, status_msg.message_id)
    except Exception:
        pass

    for post in to_send:
        send_pure_video(message.chat.id, post)
        time.sleep(1)

    with lock:
        seen = set(all_found.keys())
        if query not in tracked_queries:
            tracked_queries[query] = {"chat_ids": {message.chat.id}, "seen_shortcodes": seen}
        else:
            tracked_queries[query]["chat_ids"].add(message.chat.id)
            tracked_queries[query]["seen_shortcodes"].update(seen)

if __name__ == "__main__":
    threading.Thread(target=monitor_loop, daemon=True).start()
    print("Bot 24/7 rejimda ishga tushdi...")
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=20, skip_pending=True)
        except Exception as e:
            time.sleep(5)