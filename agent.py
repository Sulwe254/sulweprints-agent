import os
import requests
from pytrends.request import TrendReq
from groq import Groq
import google.generativeai as genai

# --- LOAD SECRETS ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NVIDIA_API_KEY = os.environ.get("NVIDIA_GLM_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")
PAYHIP_LINK = os.environ.get("PAYHIP_LINK", "https://payhip.com/b/l1ZIk")

# --- 1. CHECK GOOGLE TRENDS ---
def check_trends():
    print("Checking trends...")
    try:
        pytrends = TrendReq(hl='en-US', tz=360)
        keywords = ["football sweepstake", "world cup office pool", "2026 football kit"]
        pytrends.build_payload(keywords, cat=0, timeframe='now 7-d', geo='', gprop='')
        data = pytrends.interest_by_region(resolution='COUNTRY')
        top_countries = data.sum(axis=1).sort_values(ascending=False).head(3).index.tolist()
        return top_countries if top_countries else ["Global"]
    except Exception as e:
        print(f"Trend error: {e}")
        return ["Global"]

# --- 2. GENERATE POST (Try Groq -> NVIDIA -> Gemini) ---
def generate_post(countries):
    print(f"Generating post for: {countries}")
    
    prompt = f"""You are a marketing agent for Sulwe Prints. We sell a '2026 Global Football Tournament Sweepstake & Office Pool Kit' (PDF download).
    It includes team draw cards for all 48 teams, 3 scoring systems, UTC match schedule, payout tracker, winner certificate, and wooden spoon award.
    It is currently trending in {', '.join(countries)}.
    Write a short, engaging social media post to promote it. Include this link: {PAYHIP_LINK}. 
    Make it sound natural, exciting, and not spammy. Use 2-3 relevant emojis."""
    
    # TRY GROQ FIRST
    try:
        print("Trying Groq...")
        client = Groq(api_key=GROQ_API_KEY)
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192",
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Groq failed: {e}")
    
    # TRY NVIDIA SECOND
    try:
        print("Trying NVIDIA...")
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        payload = {
            "model": "meta/llama-3.1-8b-instruct",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200
        }
        headers = {
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json"
        }
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        print(f"NVIDIA failed: {e}")

    # FALLBACK TO GEMINI
    try:
        print("Falling back to Gemini...")
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini failed: {e}")
        return f"🏆 Get your 2026 Football Sweepstake Kit! All 48 teams, 3 scoring systems, and certificates. Download here: {PAYHIP_LINK}"

# --- 3. POST TO TELEGRAM ---
def post_to_telegram(message):
    print("Posting to Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("Success! Posted to Telegram.")
    else:
        print(f"Failed: {response.text}")

# --- MAIN AGENT RUNNER ---
if __name__ == "__main__":
    print("Agent starting...")
    countries = check_trends()
    post = generate_post(countries)
    post_to_telegram(post)
    print("Agent finished.")
