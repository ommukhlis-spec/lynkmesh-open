import tweepy
import json
import os
import sys

# Ambil API Keys dari Environment Variables (aman!)
API_KEY = os.getenv("TWITTER_API_KEY")
API_SECRET = os.getenv("TWITTER_API_SECRET")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

def run_scheduler():
    # 1. Load postingan
    path = "content/posts.json"
    with open(path, "r") as f:
        posts = json.load(f)

    if not posts:
        print("Antrean kosong, Muk!")
        return

    # 2. Ambil post pertama & sisa
    current_tweet = posts.pop(0)

    # 3. Eksekusi Post ke X
    try:
        client = tweepy.Client(
            consumer_key=API_KEY, consumer_secret=API_SECRET,
            access_token=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET
        )
        client.create_tweet(text=current_tweet)
        print(f"Berhasil posting: {current_tweet[:30]}...")

        # 4. Simpan sisa post kembali ke file
        with open(path, "w") as f:
            json.dump(posts, f, indent=2)
            
    except Exception as e:
        print(f"Gagal posting: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_scheduler()
