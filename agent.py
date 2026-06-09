import os
import requests
from pytrends.request import TrendReq
from groq import Groq
import google.generativeai as genai

# --- LOAD SECRETS ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
# We are ONLY using your personal ID now
MY_PERSONAL_ID = os.environ.get("TELEGRAM_CHANNEL_ID") 
PAYHIP_LINK = os.environ.get("PAYHIP_LINK", "https://payhip.com/b/l1ZIk")

# --- 1. CHECK TRENDS ---
def check_trends():
    print("Checking trends...")
    promo_keywords = ["football sweepstake", "world cup office pool", "2026 football kit"]
    idea_keywords = ["world cup bingo", "world cup wallpaper", "world cup bracket", "world cup quiz", "sweepstake template"]
    
    top_countries = ["Global"]
    trending_ideas = []
    
    try:
        pytrends = TrendReq(hl='en-US', tz=360)
        
        # Check main product trends
        pytrends.build_payload(promo_keywords, cat=0, timeframe='now 7-d', geo='', gprop='')
        promo_data = pytrends.interest_by_region(resolution='COUNTRY')
        top_countries = promo_data.sum(axis=1).sort_values(ascending=False).head(3).index.tolist()

        # Check product idea trends
        pytrends.build_payload(idea_keywords, cat=0, timeframe='now 7-d', geo='', gprop='')
        idea_data = pytrends.interest_over_time()
        
        if not idea_data.empty:
            for kw in idea_keywords:
                if kw in idea_data.columns and idea_data[kw].iloc[-1] > 40:
                    trending_ideas.append(kw.replace("world cup ", "").title())
                    
    except Exception as e:
        print(f"Trend error: {e}")

    return top_countries if top_countries else ["Global"], trending_ideas

# --- 2. GENERATE MARKETING BRIEF ---
def generate_brief(countries, trending_ideas):
    print("Generating Daily Marketing Brief...")
    
    ideas_str = ", ".join(trending_ideas) if trending_ideas else "None detected today"
    
    prompt = f"""You are an expert digital marketing assistant. Your client sells a '2026 Global Football Tournament Sweepstake & Office Pool Kit' (PDF) for $6.99. 
    Link: {PAYHIP_LINK}
    It includes: 48 team draw cards, 3 scoring systems, UTC match schedule, payout tracker, winner & wooden spoon certificates.

    Currently, the product is trending highest in: {', '.join(countries)}.
    Trending product ideas to consider making: {ideas_str}.

    Generate a concise Daily Marketing Brief with these exact sections:

    📍 HOT MARKETS: List the countries and suggest which Facebook Groups or Quora topics to target for those countries.

    📝 SOCIAL POST: Write a short, exciting Facebook/Twitter post with emojis and the link. No hashtags.

    💬 REDDIT/QUORA ANSWER: Write a helpful, 3-sentence answer to the question "How do I run a World Cup office pool with 48 teams?". Add value first, then naturally mention the kit and link at the very end. Do NOT use marketing language here, sound like a helpful fan.

    🎯 TODAY'S TASK: Give one specific, easy action step for the marketer to do right now."""

    # Try Groq
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
        # Fallback to Gemini
        try:
            print("Falling back to Gemini...")
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Gemini failed: {e}")
            return f"Marketing Brief: Push your kit {PAYHIP_LINK} to audiences in {', '.join(countries)} today!"

# --- 3. POST TO TELEGRAM (DM ONLY) ---
def send_dm(message):
    print(f"Sending DM to {MY_PERSONAL_ID}...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    # Clean markdown to prevent Telegram crashes
    clean_message = message.replace("*", "").replace("_", "").replace("~", "").replace("#", "")
    payload = {
        "chat_id": MY_PERSONAL_ID,
        "text": clean_message
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("Success! DM sent.")
    else:
        print(f"Failed: {response.text}")

# --- MAIN AGENT RUNNER ---
if __name__ == "__main__":
    print("Agent starting...")
    top_countries, trending_ideas = check_trends()
    brief = generate_brief(top_countries, trending_ideas)
    
    # Add Product Alert if applicable
    if trending_ideas:
        brief += f"\n\n🚀 PRODUCT ALERT: Consider making a PDF for {', '.join(trending_ideas)}! They are trending right now."

    send_dm(brief)
    print("Agent finished.")
