"""
SulwePrints Ultimate Marketing Agent v2.0
==========================================
A fully automated AI marketing agent that:
- Researches trending World Cup digital products
- Writes attention-grabbing copy using proven marketing frameworks
- Auto-promotes on Discord, Medium, Pinterest, Twitter/X, and Facebook Pages
- Sends you a Daily Marketing Brief via Telegram DM
- Never gets banned (avoids Reddit, avoids Groups spamming)

Mistakes fixed from v1:
- No Reddit auto-posting (caused bans)
- No Markdown in Telegram (caused message rejection)
- No Facebook Groups (caused bans) — uses Facebook Pages instead
- No generic copy — uses AIDA/PAS marketing frameworks
- No single AI fallback — tries Groq -> Gemini -> local fallback
"""

import os
import re
import json
import requests
from datetime import datetime
from pytrends.request import TrendReq

# Try optional imports
try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


# ============================================================
# CONFIGURATION — All secrets from GitHub Actions
# ============================================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
MY_PERSONAL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")
PAYHIP_LINK = os.environ.get("PAYHIP_LINK", "https://payhip.com/b/l1ZIk")

# Platform secrets (all optional — agent works with whatever you set up)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
MEDIUM_API_TOKEN = os.environ.get("MEDIUM_API_TOKEN", "")
PINTEREST_ACCESS_TOKEN = os.environ.get("PINTEREST_ACCESS_TOKEN", "")
PINTEREST_BOARD_ID = os.environ.get("PINTEREST_BOARD_ID", "")
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.environ.get("TWITTER_ACCESS_SECRET", "")
FACEBOOK_PAGE_TOKEN = os.environ.get("FACEBOOK_PAGE_TOKEN", "")
FACEBOOK_PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID", "")

# Product info
PRODUCT_NAME = "2026 Global Football Tournament Sweepstake Kit"
PRODUCT_PRICE = "$6.99"
PRODUCT_DESC = (
    "48 team draw cards, 3 scoring systems, full UTC match schedule, "
    "payout tracker, winner & wooden spoon certificates — instant PDF download"
)


# ============================================================
# 1. TREND RESEARCH ENGINE
# ============================================================
def check_trends():
    """Research trending keywords across multiple categories."""
    print("🔍 Researching trends...")

    results = {
        "top_countries": ["Global"],
        "trending_promo": [],
        "trending_ideas": [],
        "rising_searches": [],
        "related_queries": [],
    }

    try:
        pytrends = TrendReq(hl='en-US', tz=360)

        # Category 1: Core product keywords
        promo_keywords = [
            "football sweepstake", "world cup office pool",
            "2026 football kit", "world cup sweepstake kit",
            "football tournament bracket"
        ]
        pytrends.build_payload(promo_keywords, cat=0, timeframe='now 7-d', geo='', gprop='')
        promo_data = pytrends.interest_by_region(resolution='COUNTRY')
        if not promo_data.empty:
            results["top_countries"] = (
                promo_data.sum(axis=1)
                .sort_values(ascending=False)
                .head(5)
                .index.tolist()
            )

        # Category 2: Product expansion ideas
        idea_keywords = [
            "world cup bingo", "world cup wallpaper",
            "world cup bracket", "world cup quiz",
            "sweepstake template", "world cup predictor game",
            "football pool spreadsheet", "world cup sticker album"
        ]
        pytrends.build_payload(idea_keywords, cat=0, timeframe='now 7-d', geo='', gprop='')
        idea_data = pytrends.interest_over_time()
        if not idea_data.empty:
            for kw in idea_keywords:
                if kw in idea_data.columns:
                    latest = idea_data[kw].iloc[-1]
                    if latest > 30:
                        results["trending_ideas"].append({
                            "keyword": kw,
                            "score": int(latest)
                        })

        # Category 3: Rising related searches
        pytrends.build_payload(
            ["world cup 2026", "football tournament 2026"],
            cat=0, timeframe='now 7-d', geo='', gprop=''
        )
        related = pytrends.related_queries()
        for kw, data in related.items():
            if data.get("rising") is not None and not data["rising"].empty:
                top_rising = data["rising"].head(5)
                for _, row in top_rising.iterrows():
                    results["rising_searches"].append(
                        f"{row['query']} ({row.get('value', 'rising')})"
                    )

    except Exception as e:
        print(f"⚠️ Trend error: {e}")

    # Sort trending ideas by score
    results["trending_ideas"].sort(key=lambda x: x["score"], reverse=True)

    return results


def research_digital_products(trend_data):
    """Use AI to research what World Cup digital products are trending and worth making."""
    print("📦 Researching trending digital products...")

    ideas_str = ", ".join(
        f"{i['keyword']} (trend: {i['score']})" for i in trend_data["trending_ideas"]
    ) if trend_data["trending_ideas"] else "None detected"
    rising_str = ", ".join(trend_data["rising_searches"][:8]) if trend_data["rising_searches"] else "None"
    countries_str = ", ".join(trend_data["top_countries"][:3])

    prompt = f"""You are a digital product research expert. Analyze these Google Trends signals and recommend the BEST digital products to create and sell around the 2026 World Cup / Football Tournament.

CURRENT TREND DATA:
- Trending product ideas: {ideas_str}
- Rising searches: {rising_str}
- Hot countries: {countries_str}
- Existing product: {PRODUCT_NAME} ({PRODUCT_PRICE}) — {PRODUCT_DESC}

REQUIREMENTS:
1. Recommend exactly 3 digital products that are EASY to make as PDFs (can be made in Canva or Google Docs in under 2 hours)
2. Each product must have proven demand based on the trend data
3. Suggest a price point for each (between $2.99 and $9.99)
4. Explain WHY it will sell (what trend supports it)
5. Give a one-sentence marketing hook for each product

FORMAT for each product:
PRODUCT: [name]
PRICE: [suggested price]
WHY IT SELLS: [trend-backed reason]
HOOK: [attention-grabbing one-liner]
TIME TO MAKE: [estimated minutes]"""

    return ai_generate(prompt)


# ============================================================
# 2. AI COPYWRITING ENGINE (Proven Marketing Frameworks)
# ============================================================
def ai_generate(prompt, max_retries=2):
    """Generate text using Groq -> Gemini fallback chain."""
    # Try Groq first (fastest)
    if HAS_GROQ and GROQ_API_KEY:
        try:
            print("⚡ Trying Groq...")
            client = Groq(api_key=GROQ_API_KEY)
            response = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a world-class direct-response copywriter and digital marketing strategist. "
                            "You write copy that stops scrolling, triggers emotion, and drives action. "
                            "You use proven frameworks like AIDA (Attention-Interest-Desire-Action) and "
                            "PAS (Problem-Agitate-Solution). You never use generic marketing speak. "
                            "Every word earns its place. You sound like a real fan who happens to sell something great."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                model="llama3-8b-8192",
                temperature=0.8,
                max_tokens=2048,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"⚠️ Groq failed: {e}")

    # Fallback to Gemini
    if HAS_GEMINI and GEMINI_API_KEY:
        try:
            print("🔮 Falling back to Gemini...")
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"⚠️ Gemini failed: {e}")

    # Last resort: structured fallback
    print("🆘 Using fallback copy...")
    return (
        f"🔥 {PRODUCT_NAME} — {PRODUCT_PRICE}\n\n"
        f"Get your tournament sorted in 5 minutes: {PRODUCT_DESC}\n\n"
        f"Grab yours: {PAYHIP_LINK}"
    )


def generate_social_post(trend_data):
    """Generate an attention-grabbing social media post using AIDA framework."""
    countries = ", ".join(trend_data["top_countries"][:3])
    ideas = trend_data["trending_ideas"][:2]

    prompt = f"""Write a social media post that stops people from scrolling. Use the AIDA framework (Attention-Interest-Desire-Action).

PRODUCT: {PRODUCT_NAME}
PRICE: {PRODUCT_PRICE}
WHAT IT INCLUDES: {PRODUCT_DESC}
LINK: {PAYHIP_LINK}
HOT MARKETS: {countries}

RULES:
- Start with a HOOK that creates FOMO or curiosity (NOT "Check out my product")
- Make it sound like a passionate fan, NOT a salesperson
- Use 2-3 emojis max (not emoji soup)
- Include a specific detail that proves this kit saves time (e.g., "5 minutes to set up")
- End with a clear call-to-action
- Keep it under 280 characters for Twitter compatibility
- Do NOT use asterisks, underscores, tildes, or hashtags
- Write in plain text only"""

    return ai_generate(prompt)


def generate_medium_article(trend_data):
    """Generate an SEO-optimized Medium article that subtly promotes the product."""
    countries = ", ".join(trend_data["top_countries"][:3])
    ideas_str = ", ".join(i["keyword"] for i in trend_data["trending_ideas"][:3]) if trend_data["trending_ideas"] else "tournament brackets"

    prompt = f"""Write a Medium article that will rank on Google and drive traffic to a product. Use the PAS framework (Problem-Agitate-Solution).

PRODUCT: {PRODUCT_NAME} — {PRODUCT_PRICE}
LINK: {PAYHIP_LINK}
TARGET COUNTRIES: {countries}
TRENDING TOPICS: {ideas_str}

STRUCTURE:
1. TITLE: Click-worthy but not clickbait. Include "2026" and "World Cup" or "Football Tournament"
2. INTRO (2-3 sentences): State the problem — organizing a tournament pool is chaos
3. AGITATION (2-3 sentences): Paint the pain — spreadsheets break, people argue over rules, someone always loses track
4. SOLUTION (3-4 sentences): Present the kit as the answer. Mention specific features. Link to product.
5. BONUS TIPS (3 bullet points): Give genuine value — best scoring systems, how to handle 48 teams, payout ideas

RULES:
- Sound like an experienced office pool organizer, NOT a marketer
- The product mention should feel natural, like a recommendation from a friend
- Include the link ONCE, naturally in the solution section
- Do NOT use markdown formatting (no **, no __, no ##)
- Keep total length under 400 words
- Make it genuinely useful so Medium doesn't flag it as spam"""

    return ai_generate(prompt)


def generate_pinterest_description(trend_data):
    """Generate a Pinterest-optimized pin description with SEO keywords."""
    ideas_str = ", ".join(i["keyword"] for i in trend_data["trending_ideas"][:3]) if trend_data["trending_ideas"] else ""

    prompt = f"""Write a Pinterest pin description for this product. Pinterest is a visual search engine, so this needs SEO keywords.

PRODUCT: {PRODUCT_NAME} — {PRODUCT_PRICE}
LINK: {PAYHIP_LINK}
INCLUDES: {PRODUCT_DESC}
RELATED TRENDS: {ideas_str}

RULES:
- First line must be hook-worthy (this shows up in the feed)
- Include 5-8 relevant keywords naturally (world cup sweepstake, football pool kit, tournament bracket, etc.)
- Mention it's an instant PDF download
- End with the link
- No markdown, no hashtags, no asterisks
- Keep under 500 characters"""

    return ai_generate(prompt)


def generate_smart_reply(trend_data):
    """Generate a smart, helpful reply for community questions (Quora, forums, etc.)."""
    prompt = f"""Write a helpful answer to: "How do I run a World Cup office pool with 48 teams?"

You are a genuine football fan who has organized pools before. You are NOT selling anything — you are being helpful.

PRODUCT CONTEXT (mention ONCE at the very end, casually): {PRODUCT_NAME} — {PAYHIP_LINK}

RULES:
- Give genuinely useful advice (3-4 specific tips)
- Sound like a real person, not AI
- Mention the kit at the very end as a "by the way, this saved me time" — not a sales pitch
- Do NOT use markdown, asterisks, or formatting
- Keep under 200 words
- If someone read this on Quora, they would upvote it because it's genuinely helpful"""

    return ai_generate(prompt)


def generate_daily_brief(trend_data, product_research):
    """Generate the comprehensive Daily Marketing Brief sent to Telegram."""
    countries = ", ".join(trend_data["top_countries"][:5])
    ideas = trend_data["trending_ideas"]
    ideas_str = ", ".join(f"{i['keyword']} ({i['score']})" for i in ideas[:5]) if ideas else "None today"

    prompt = f"""You are an elite marketing strategist. Create a DAILY MARKETING BRIEF for a solo digital marketer selling a World Cup PDF kit.

PRODUCT: {PRODUCT_NAME} — {PRODUCT_PRICE}
LINK: {PAYHIP_LINK}
WHAT IT INCLUDES: {PRODUCT_DESC}

TODAY'S DATA:
- Hot Markets: {countries}
- Trending Product Ideas: {ideas_str}
- Rising Searches: {', '.join(trend_data['rising_searches'][:5]) if trend_data['rising_searches'] else 'None'}

PRODUCT RESEARCH RESULTS:
{product_research}

Create the brief with these EXACT sections:

MARKETS ON FIRE: List the top 3 countries and WHERE to find buyers in each (specific Facebook Pages, subreddits for manual posting, Quora topics, local forums). Be specific — not "post on Facebook" but "post on the 'World Cup 2026 Fans' Facebook Page".

TRENDING PRODUCT OPPORTUNITIES: Summarize the top 2 digital products to make next based on the research. Give a 1-sentence hook for each.

TODAY'S COPY-AND-PASTE POST: Write ONE ready-to-post social update that would make someone click. Use the PAS formula (Problem-Agitate-Solution). No generic language. Include the link.

SMART COMMUNITY REPLY: Write a 3-sentence helpful reply to "What's the best way to organize a football sweepstake?" that naturally mentions the kit at the end. Must sound like a real fan.

DAILY ACTION PLAN: Give exactly 3 specific tasks to do today (e.g., "Post the social update in X Facebook Page", "Answer 2 Quora questions with the smart reply", "Create a World Cup Bingo PDF")

RULES:
- No markdown, no asterisks, no underscores, no tildes, no hashtags
- Use plain text only
- Use line breaks for readability
- Every recommendation must be specific and actionable
- No fluff — every word must earn its place"""

    return ai_generate(prompt)


# ============================================================
# 3. MULTI-PLATFORM AUTO-POSTING ENGINE
# ============================================================
def sanitize_text(text):
    """Remove ALL characters that could break Telegram, Discord, or any platform."""
    # Remove markdown formatting characters
    clean = text
    clean = clean.replace("*", "")
    clean = clean.replace("_", "")
    clean = clean.replace("~", "")
    clean = clean.replace("`", "")
    clean = clean.replace("#", "")
    # Remove extra whitespace
    clean = re.sub(r'\n{3,}', '\n\n', clean)
    clean = clean.strip()
    return clean


def post_to_telegram(message):
    """Send DM to the user via Telegram (primary channel)."""
    if not TELEGRAM_BOT_TOKEN or not MY_PERSONAL_ID:
        print("⚠️ Telegram not configured, skipping")
        return False

    print(f"📱 Sending Telegram DM to {MY_PERSONAL_ID}...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    clean_message = sanitize_text(message)

    # Split long messages (Telegram limit is 4096 chars)
    if len(clean_message) > 4000:
        chunks = [clean_message[i:i+4000] for i in range(0, len(clean_message), 4000)]
    else:
        chunks = [clean_message]

    success = True
    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id": MY_PERSONAL_ID,
            "text": chunk
        }
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                print(f"  ✅ Telegram chunk {i+1}/{len(chunks)} sent")
            else:
                print(f"  ❌ Telegram chunk {i+1} failed: {response.text[:200]}")
                success = False
        except Exception as e:
            print(f"  ❌ Telegram error: {e}")
            success = False

    return success


def post_to_discord(message):
    """Post to Discord channel via webhook (free, no moderation issues)."""
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ Discord not configured, skipping")
        return False

    print("💬 Posting to Discord...")
    clean_message = sanitize_text(message)

    # Discord embed makes posts look professional
    payload = {
        "username": "SulwePrints Agent",
        "embeds": [{
            "title": f"Daily Marketing Brief — {datetime.now().strftime('%b %d, %Y')}",
            "description": clean_message[:2000],
            "color": 5763719,  # Green
            "footer": {"text": "SulwePrints AI Agent"}
        }]
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=30)
        if response.status_code == 204:
            print("  ✅ Discord posted")
            return True
        else:
            print(f"  ❌ Discord failed: {response.status_code} {response.text[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ Discord error: {e}")
        return False


def post_to_medium(article_text, title):
    """Publish an SEO article to Medium (drives Google traffic for months)."""
    if not MEDIUM_API_TOKEN:
        print("⚠️ Medium not configured, skipping")
        return False

    print("📝 Publishing to Medium...")
    try:
        # Step 1: Get user ID
        headers = {
            "Authorization": f"Bearer {MEDIUM_API_TOKEN}",
            "Content-Type": "application/json"
        }
        user_resp = requests.get("https://api.medium.com/v1/me", headers=headers, timeout=30)
        if user_resp.status_code != 200:
            print(f"  ❌ Medium auth failed: {user_resp.status_code}")
            return False

        user_id = user_resp.json()["data"]["id"]

        # Step 2: Publish article as draft (safe — won't get flagged)
        publish_data = {
            "title": sanitize_text(title),
            "contentFormat": "plain",
            "content": sanitize_text(article_text),
            "tags": ["World Cup", "Football", "Sports", "Sweepstake", "2026"],
            "publishStatus": "draft"  # Draft first — you review then publish manually
        }
        pub_resp = requests.post(
            f"https://api.medium.com/v1/users/{user_id}/posts",
            headers=headers,
            json=publish_data,
            timeout=30
        )

        if pub_resp.status_code == 201:
            post_url = pub_resp.json()["data"]["url"]
            print(f"  ✅ Medium draft created: {post_url}")
            return True
        else:
            print(f"  ❌ Medium publish failed: {pub_resp.status_code} {pub_resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ Medium error: {e}")
        return False


def post_to_pinterest(description):
    """Create a Pin on Pinterest (huge for visual/PDF products)."""
    if not PINTEREST_ACCESS_TOKEN or not PINTEREST_BOARD_ID:
        print("⚠️ Pinterest not configured, skipping")
        return False

    print("📌 Pinning to Pinterest...")
    try:
        headers = {
            "Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        pin_data = {
            "board_id": PINTEREST_BOARD_ID,
            "title": f"{PRODUCT_NAME} — Instant PDF Download",
            "description": sanitize_text(description),
            "link": PAYHIP_LINK,
            "media_source": {
                "source_type": "image_url",
                # Use Payhip product image or create one with the AI image tool
                "url": "https://payhip.com/b/l1ZIk"
            }
        }
        resp = requests.post(
            "https://api.pinterest.com/v5/pins",
            headers=headers,
            json=pin_data,
            timeout=30
        )
        if resp.status_code == 201:
            print("  ✅ Pinterest pin created")
            return True
        else:
            print(f"  ❌ Pinterest failed: {resp.status_code} {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ Pinterest error: {e}")
        return False


def post_to_twitter(tweet_text):
    """Post a tweet using Twitter/X API v2 (free tier)."""
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        print("⚠️ Twitter not configured, skipping")
        return False

    print("🐦 Posting to Twitter/X...")
    try:
        # OAuth 1.0a signing
        import oauthlib.oauth1
        from urllib.parse import urlencode

        oauth = oauthlib.oauth1.Client(
            TWITTER_API_KEY,
            client_secret=TWITTER_API_SECRET,
            resource_owner_key=TWITTER_ACCESS_TOKEN,
            resource_owner_secret=TWITTER_ACCESS_SECRET
        )

        clean_tweet = sanitize_text(tweet_text)[:280]  # Twitter limit
        body = {"text": clean_tweet}
        uri = "https://api.twitter.com/2/tweets"

        req_headers = {"Content-Type": "application/json"}
        uri_with_params, signed_headers, _ = oauth.sign(
            uri, http_method="POST", body=json.dumps(body), headers=req_headers
        )

        response = requests.post(
            uri, json=body, headers={**req_headers, **signed_headers}, timeout=30
        )
        if response.status_code == 201:
            print("  ✅ Tweet posted")
            return True
        else:
            print(f"  ❌ Twitter failed: {response.status_code} {response.text[:200]}")
            return False
    except ImportError:
        print("  ⚠️ oauthlib not installed, skipping Twitter")
        return False
    except Exception as e:
        print(f"  ❌ Twitter error: {e}")
        return False


def post_to_facebook(message):
    """Post to Facebook Page (NOT Groups — Pages don't get you banned)."""
    if not FACEBOOK_PAGE_TOKEN or not FACEBOOK_PAGE_ID:
        print("⚠️ Facebook Page not configured, skipping")
        return False

    print("📘 Posting to Facebook Page...")
    clean_message = sanitize_text(message)

    try:
        url = f"https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/feed"
        payload = {
            "message": clean_message,
            "link": PAYHIP_LINK,
            "access_token": FACEBOOK_PAGE_TOKEN
        }
        response = requests.post(url, data=payload, timeout=30)

        if response.status_code == 200:
            post_id = response.json().get("id", "")
            print(f"  ✅ Facebook Page post created: {post_id}")
            return True
        else:
            print(f"  ❌ Facebook failed: {response.status_code} {response.text[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ Facebook error: {e}")
        return False


# ============================================================
# 4. PLATFORM STATUS TRACKER
# ============================================================
def get_platform_status():
    """Check which platforms are configured and ready."""
    platforms = {
        "Telegram DM": bool(TELEGRAM_BOT_TOKEN and MY_PERSONAL_ID),
        "Discord": bool(DISCORD_WEBHOOK_URL),
        "Medium": bool(MEDIUM_API_TOKEN),
        "Pinterest": bool(PINTEREST_ACCESS_TOKEN and PINTEREST_BOARD_ID),
        "Twitter/X": bool(all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET])),
        "Facebook Page": bool(FACEBOOK_PAGE_TOKEN and FACEBOOK_PAGE_ID),
    }
    return platforms


# ============================================================
# 5. MAIN AGENT RUNNER
# ============================================================
def main():
    print("=" * 50)
    print(f"🚀 SulwePrints Agent v2.0 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    # Step 1: Research trends
    trend_data = check_trends()
    print(f"  📍 Hot markets: {trend_data['top_countries'][:3]}")
    print(f"  📦 Trending ideas: {[i['keyword'] for i in trend_data['trending_ideas'][:3]]}")

    # Step 2: Research digital product opportunities
    product_research = research_digital_products(trend_data)

    # Step 3: Generate all marketing content
    print("\n✍️ Generating marketing content...")

    daily_brief = generate_daily_brief(trend_data, product_research)
    social_post = generate_social_post(trend_data)
    medium_article = generate_medium_article(trend_data)
    pinterest_desc = generate_pinterest_description(trend_data)
    smart_reply = generate_smart_reply(trend_data)

    # Extract a title for the Medium article
    medium_title = f"How to Run a 48-Team World Cup Pool in 2026 (The Easy Way)"

    # Step 4: Post to all configured platforms
    print("\n📢 Auto-posting to platforms...")
    results = {}

    # ALWAYS send the daily brief to Telegram DM
    results["Telegram"] = post_to_telegram(daily_brief)

    # Auto-post to platforms (only if configured)
    results["Discord"] = post_to_discord(social_post)
    results["Medium"] = post_to_medium(medium_article, medium_title)
    results["Pinterest"] = post_to_pinterest(pinterest_desc)
    results["Twitter"] = post_to_twitter(social_post)
    results["Facebook"] = post_to_facebook(social_post)

    # Step 5: Send platform status + smart reply as separate Telegram message
    platform_status = get_platform_status()
    status_lines = ["📊 PLATFORM STATUS:"]
    for name, active in platform_status.items():
        icon = "✅" if active else "⬜"
        status_lines.append(f"  {icon} {name}")

    status_lines.append("\n💡 SMART REPLY (copy-paste for Quora/forums):")
    status_lines.append(smart_reply)

    # Send product research as another message
    status_lines.append("\n📦 PRODUCT RESEARCH:")
    status_lines.append(product_research[:2000])

    post_to_telegram("\n".join(status_lines))

    # Final summary
    print("\n" + "=" * 50)
    print("📊 RESULTS:")
    for platform, success in results.items():
        icon = "✅" if success else "⬜"
        print(f"  {icon} {platform}")
    print("=" * 50)
    print("🏁 Agent finished.")


if __name__ == "__main__":
    main()
