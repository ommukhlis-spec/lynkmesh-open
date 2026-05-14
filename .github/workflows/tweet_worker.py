import tweepy
import json
import os
import sys

# Ambil API Keys dari GitHub Secrets
API_KEY = os.getenv("TWITTER_API_KEY")
API_SECRET = os.getenv("TWITTER_API_SECRET")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

def run_scheduler():
    # Karena file ini ada di .github/workflows/, kita arahkan path-nya ke sana
    # Script ini akan mencari posts.json di folder yang sama
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, "posts.json")

    if not os.path.exists(json_path):
        print(f"Error: File {json_path} tidak ditemukan!")
        sys.exit(1)

    # 1. Load postingan
    with open(json_path, "r") as f:
        posts = json.load(f)

    if not posts:
        print("Antrean kosong, Muk! Saatnya isi ulang posts.json.")
        return

    # 2. Ambil post pertama & sisa
    current_tweet = posts.pop(0)

    # 3. Eksekusi Post ke X
    try:
        client = tweepy.Client(
            consumer_key=API_KEY, 
            consumer_secret=API_SECRET,
            access_token=ACCESS_TOKEN, 
            access_token_secret=ACCESS_TOKEN_SECRET
        )
        
        # Kirim tweet
        response = client.create_tweet(text=current_tweet)
        print(f"Berhasil posting: {current_tweet[:50]}...")

        # 4. Simpan sisa post kembali ke file
        with open(json_path, "w") as f:
            json.dump(posts, f, indent=2)
            
    except Exception as e:
        print(f"Gagal posting ke X: {e}")
        # Jika gagal karena otentikasi atau izin, kita stop workflow agar tidak terus mencoba
        sys.exit(1)

if __name__ == "__main__":
    run_scheduler()
