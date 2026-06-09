"""
SulwePrints Auto-Engagement Agent v3.0
========================================
This agent FINDS people already talking about World Cup sweepstakes/pools
and ENGAGES them with genuinely helpful replies that naturally promote your product.

NO creating channels. NO building audiences. NO manual posting.
The bot goes WHERE THE PEOPLE ALREADY ARE.

AUTO-ENGAGEMENT PLATFORMS:
1. Reddit — Searches subreddits, finds questions, replies helpfully
2. Twitter/X — Searches tweets, replies to people asking about pools
3. Mastodon — Searches the fediverse, engages with relevant posts

SAFETY RULES (learned from past mistakes):
- NEVER post direct links on Reddit (causes bans)
- NEVER sound like a marketer (causes bans)
- ALWAYS be genuinely helpful first
- ONLY mention product casually, like a fan sharing a find
- MAX 1 reply per platform per run (avoids spam detection)
- Track replied posts to never reply twice
- Rate limit strictly
"""

import os
import re
import json
import requests
import time
import random
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

try:
    import praw
    HAS_PRAW = True
except ImportError:
    HAS_PRAW = False


# ============================================================
# CONFIGURATION
# ============================================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
MY_PERSONAL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")
PAYHIP_LINK = os.environ.get("PAYHIP_LINK", "https://payhip.com/b/l1ZIk")

# Reddit credentials (free at reddit.com/prefs/apps)
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")
REDDIT_USERNAME = os.environ.get("REDDIT_USERNAME", "")
REDDIT_PASSWORD = os.environ.get("REDDIT_PASSWORD", "")

# Twitter/X (free tier)
TWITTER_BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN", "")
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.environ.get("TWITTER_ACCESS_SECRET", "")

# Mastodon (free)
MASTODON_INSTANCE = os.environ.get("MASTODON_INSTANCE", "mastodon.social")
MASTODON_ACCESS_TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN", "")

# Product info
PRODUCT_NAME = "2026 Global Football Tournament Sweepstake Kit"
PRODUCT_PRICE = "$6.99"
PRODUCT_DESC = (
    "48 team draw cards, 3 scoring systems, full UTC match schedule, "
    "payout tracker, winner & wooden spoon certificates — instant PDF download"
)

# Track what we've already replied to (stored in a simple file)
REPLIED_FILE = "replied_posts.json"


# ============================================================
# 0. UTILITY FUNCTIONS
# ============================================================
def sanitize_text(text):
    """Remove ALL markdown/formatting that could crash any platform."""
    clean = text
    for char in ["*", "_", "~", "`", "#", "|", ">"]:
        clean = clean.replace(char, "")
    clean = re.sub(r'\n{3,}', '\n\n', clean)
    clean = clean.strip()
    return clean


def load_replied_posts():
    """Load the list of posts we've already replied to."""
    try:
        with open(REPLIED_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"reddit": [], "twitter": [], "mastodon": []}


def save_replied_posts(data):
    """Save the list of replied posts."""
    # Keep only last 200 entries per platform to prevent file from growing forever
    for platform in data:
        data[platform] = data[platform][-200:]
    with open(REPLIED_FILE, 'w') as f:
        json.dump(data, f)


def ai_generate(prompt, temperature=0.8):
    """Generate text using Groq -> Gemini fallback."""
    system_prompt = (
        "You are a genuine football fan and sweepstake enthusiast. You are NOT a marketer. "
        "You are NOT a salesperson. You are a real person who loves football and organizes "
        "office pools every tournament. You found a great kit that saved you time and you "
        "casually mention it the way a friend would recommend something — never pushy, "
        "never salesy. You write like you talk: casual, helpful, enthusiastic but authentic. "
        "You never use marketing language like 'amazing', 'revolutionary', 'game-changer'. "
        "You use words like 'handy', 'solid', 'pretty useful', 'made things easier'."
    )

    if HAS_GROQ and GROQ_API_KEY:
        try:
            print("⚡ Trying Groq...")
            client = Groq(api_key=GROQ_API_KEY)
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                model="llama3-8b-8192",
                temperature=temperature,
                max_tokens=1024,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"  Groq failed: {e}")

    if HAS_GEMINI and GEMINI_API_KEY:
        try:
            print("🔮 Falling back to Gemini...")
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(f"{system_prompt}\n\n{prompt}")
            return response.text
        except Exception as e:
            print(f"  Gemini failed: {e}")

    return "I found a pretty handy sweepstake kit that made my office pool way easier to set up."


def send_telegram(message):
    """Send DM to user via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not MY_PERSONAL_ID:
        print("⚠️ Telegram not configured")
        return False

    print(f"📱 Sending Telegram DM...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    clean = sanitize_text(message)

    # Split if too long
    chunks = [clean[i:i+4000] for i in range(0, len(clean), 4000)] if len(clean) > 4000 else [clean]

    for chunk in chunks:
        try:
            requests.post(url, json={"chat_id": MY_PERSONAL_ID, "text": chunk}, timeout=30)
        except Exception as e:
            print(f"  Telegram error: {e}")
    return True


# ============================================================
# 1. TREND RESEARCH
# ============================================================
def check_trends():
    """Research what's trending around World Cup sweepstakes."""
    print("🔍 Researching trends...")
    results = {
        "top_countries": ["Global"],
        "trending_ideas": [],
        "rising_searches": [],
    }

    try:
        pytrends = TrendReq(hl='en-US', tz=360)

        # Core product trends
        promo_keywords = [
            "football sweepstake", "world cup office pool",
            "world cup sweepstake kit", "football tournament bracket",
            "world cup predictor"
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

        # Product idea trends
        idea_keywords = [
            "world cup bingo", "world cup bracket",
            "world cup quiz", "sweepstake template",
            "football pool spreadsheet", "world cup predictor game",
            "world cup sticker album", "world cup wall chart"
        ]
        pytrends.build_payload(idea_keywords, cat=0, timeframe='now 7-d', geo='', gprop='')
        idea_data = pytrends.interest_over_time()
        if not idea_data.empty:
            for kw in idea_keywords:
                if kw in idea_data.columns:
                    latest = idea_data[kw].iloc[-1]
                    if latest > 30:
                        results["trending_ideas"].append({
                            "keyword": kw, "score": int(latest)
                        })

        # Rising searches
        pytrends.build_payload(
            ["world cup 2026", "football tournament 2026"],
            cat=0, timeframe='now 7-d', geo='', gprop=''
        )
        related = pytrends.related_queries()
        for kw, data in related.items():
            if data.get("rising") is not None and not data["rising"].empty:
                for _, row in data["rising"].head(5).iterrows():
                    results["rising_searches"].append(str(row['query']))

    except Exception as e:
        print(f"  Trend error: {e}")

    results["trending_ideas"].sort(key=lambda x: x["score"], reverse=True)
    return results


def research_digital_products(trend_data):
    """Research what World Cup digital products are trending."""
    print("📦 Researching trending digital products...")
    ideas_str = ", ".join(
        f"{i['keyword']} ({i['score']})" for i in trend_data["trending_ideas"]
    ) if trend_data["trending_ideas"] else "None detected"
    rising_str = ", ".join(trend_data["rising_searches"][:5]) if trend_data["rising_searches"] else "None"

    prompt = f"""You are a digital product research expert. Based on these trends, recommend the 3 BEST digital products to make and sell around the 2026 World Cup.

TREND DATA:
- Trending ideas: {ideas_str}
- Rising searches: {rising_str}
- My current product: {PRODUCT_NAME} ({PRODUCT_PRICE}) — {PRODUCT_DESC}

For each product, give:
1. PRODUCT NAME
2. PRICE ($2.99 - $9.99)
3. WHY IT WILL SELL (what trend backs it)
4. HOOK (one attention-grabbing sentence, not salesy)
5. TIME TO MAKE (minutes, using Canva or Google Docs)

Keep it concise. No markdown. No asterisks."""

    return ai_generate(prompt, temperature=0.7)


# ============================================================
# 2. REDDIT AUTO-ENGAGEMENT
# ============================================================
# Subreddits where people discuss sweepstakes, office pools, football
REDDIT_SUBREDDITS = [
    "soccer", "football", "worldcup", "sportsbook",
    "fantasypl", "soccerbetting", "premierleague",
    "AskReddit", "onylusefulwebsites", "coolwebsites",
]

# Search queries to find people asking about pools/sweepstakes
REDDIT_SEARCH_QUERIES = [
    "world cup sweepstake",
    "world cup office pool",
    "football sweepstake kit",
    "how to run a world cup pool",
    "world cup 2026 bracket",
    "football tournament predictor",
    "world cup betting pool",
    "sweepstake template",
]


def reddit_find_and_reply(trend_data):
    """Search Reddit for relevant posts and reply with genuinely helpful comments."""
    if not HAS_PRAW or not all([REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD]):
        print("⚠️ Reddit not configured, skipping")
        return None

    print("🔎 Searching Reddit for conversations to engage...")

    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            username=REDDIT_USERNAME,
            password=REDDIT_PASSWORD,
            user_agent="SulwePrintsHelper/1.0 (helpful football fan bot)"
        )

        # Verify authentication
        reddit.user.me()

    except Exception as e:
        print(f"  ❌ Reddit auth failed: {e}")
        return None

    replied = load_replied_posts()
    best_post = None
    best_score = 0

    # Search across subreddits and queries
    search_pairs = list(zip(
        random.sample(REDDIT_SUBREDDITS, min(5, len(REDDIT_SUBREDDITS))),
        random.sample(REDDIT_SEARCH_QUERIES, min(5, len(REDDIT_SEARCH_QUERIES)))
    ))

    for subreddit_name, query in search_pairs:
        try:
            subreddit = reddit.subreddit(subreddit_name)
            for post in subreddit.search(query, sort="new", time_filter="week", limit=5):
                # Skip if already replied
                if post.id in replied["reddit"]:
                    continue

                # Skip stickied/mod posts
                if post.stickied:
                    continue

                # Score = relevance (we prefer questions and new posts)
                score = 0
                title_lower = post.title.lower()
                selftext_lower = (post.selftext or "").lower()

                # Higher score for questions
                if any(q in title_lower for q in ["how", "what", "where", "anyone", "help", "looking for", "recommend"]):
                    score += 3

                # Higher score for sweepstake/pool keywords
                if any(kw in title_lower or kw in selftext_lower for kw in ["sweepstake", "office pool", "bracket", "predictor", "template"]):
                    score += 3

                # Prefer newer posts (less likely to be archived)
                hours_old = (time.time() - post.created_utc) / 3600
                if hours_old < 24:
                    score += 2
                elif hours_old < 72:
                    score += 1

                # Prefer posts with some engagement but not too much
                if 1 <= post.num_comments <= 20:
                    score += 1

                if score > best_score:
                    best_score = score
                    best_post = post

        except Exception as e:
            print(f"  Search error in r/{subreddit_name}: {e}")
            continue

    if not best_post or best_score < 2:
        print("  ℹ️ No good Reddit posts found this run")
        return None

    # Generate a genuinely helpful reply
    post_title = best_post.title
    post_body = (best_post.selftext or "")[:500]

    prompt = f"""You are a real football fan on Reddit. You found this post and want to help:

POST TITLE: {post_title}
POST CONTENT: {post_body}

Write a genuinely helpful comment. RULES:
- Be AUTHENTIC. Sound like a real person, not AI or a marketer
- Give ACTUAL useful advice first (2-3 specific tips about running a football pool/sweepstake)
- At the very end, casually mention: "Found this sweepstake kit that made setup way easier — it's a PDF with 48 team cards and scoring systems" (adapt wording to feel natural)
- DO NOT include any links (Reddit flags links as spam)
- DO NOT mention the price
- DO NOT use marketing words like "amazing", "best", "must-have"
- DO NOT use markdown, asterisks, or formatting
- Keep it under 150 words
- If someone reads this, they should think "helpful fan" not "salesperson"
- Write in a casual Reddit tone (contractions, friendly, not formal)"""

    reply_text = ai_generate(prompt, temperature=0.9)

    try:
        # Post the reply
        comment = best_post.reply(sanitize_text(reply_text))
        print(f"  ✅ Replied on Reddit: r/{best_post.subreddit.display_name} — {post_title[:60]}")
        print(f"  Link: https://reddit.com{comment.permalink}")

        # Track this reply
        replied["reddit"].append(best_post.id)
        save_replied_posts(replied)

        return {
            "platform": "Reddit",
            "subreddit": f"r/{best_post.subreddit.display_name}",
            "title": post_title,
            "link": f"https://reddit.com{best_post.permalink}",
            "reply": reply_text[:200]
        }

    except Exception as e:
        print(f"  ❌ Reddit reply failed: {e}")
        # If rate limited or blocked, still track the post
        replied["reddit"].append(best_post.id)
        save_replied_posts(replied)
        return None


# ============================================================
# 3. TWITTER/X AUTO-ENGAGEMENT
# ============================================================
def twitter_find_and_reply(trend_data):
    """Search Twitter for tweets about World Cup pools and reply."""
    if not TWITTER_BEARER_TOKEN:
        print("⚠️ Twitter not configured, skipping")
        return None

    print("🐦 Searching Twitter for conversations...")

    replied = load_replied_posts()
    headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}

    # Search for recent tweets
    search_queries = [
        "world cup sweepstake",
        "world cup office pool",
        "football sweepstake 2026",
        "world cup bracket pool",
    ]
    query = random.choice(search_queries)

    try:
        # Search recent tweets (free tier: 1 request per 15 min)
        search_url = "https://api.twitter.com/2/tweets/search/recent"
        params = {
            "query": f"{query} -is:retweet lang:en",
            "max_results": 10,
            "tweet.fields": "created_at,public_metrics,author_id",
        }
        response = requests.get(search_url, headers=headers, params=params, timeout=30)

        if response.status_code != 200:
            print(f"  ⚠️ Twitter search failed: {response.status_code}")
            return None

        tweets = response.json().get("data", [])
        if not tweets:
            print("  ℹ️ No tweets found")
            return None

        # Find the best tweet to reply to (most engaging, asking a question)
        best_tweet = None
        best_score = 0

        for tweet in tweets:
            if tweet["id"] in replied["twitter"]:
                continue

            score = 0
            text_lower = tweet["text"].lower()

            # Prefer questions
            if any(q in text_lower for q in ["how", "what", "anyone", "help", "looking"]):
                score += 3

            # Prefer sweepstake/pool content
            if any(kw in text_lower for kw in ["sweepstake", "pool", "bracket", "predictor"]):
                score += 2

            # Prefer some engagement
            metrics = tweet.get("public_metrics", {})
            if metrics.get("like_count", 0) > 0 or metrics.get("reply_count", 0) > 0:
                score += 1

            if score > best_score:
                best_score = score
                best_tweet = tweet

        if not best_tweet:
            print("  ℹ️ No good tweets found this run")
            return None

        # Generate reply
        prompt = f"""You are a real football fan on Twitter. You saw this tweet:

TWEET: {best_tweet['text']}

Write a short, helpful reply. RULES:
- Be AUTHENTIC and casual (Twitter tone, use contractions)
- Be genuinely helpful — give a quick tip or answer their question
- At the end, casually say something like "I used this kit that made it super easy, it's a PDF with all 48 teams and scoring systems" — adapt to feel natural
- DO NOT include links (Twitter flags automated links)
- DO NOT use hashtags
- DO NOT use marketing language
- Keep under 200 characters if possible, max 280
- No markdown, no asterisks"""

        reply_text = ai_generate(prompt, temperature=0.9)
        clean_reply = sanitize_text(reply_text)[:280]

        # Post the reply (requires OAuth 1.0a for posting)
        if all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
            import oauthlib.oauth1

            oauth = oauthlib.oauth1.Client(
                TWITTER_API_KEY,
                client_secret=TWITTER_API_SECRET,
                resource_owner_key=TWITTER_ACCESS_TOKEN,
                resource_owner_secret=TWITTER_ACCESS_SECRET
            )

            body = {
                "text": clean_reply,
                "reply": {"in_reply_to_tweet_id": best_tweet["id"]}
            }
            uri = "https://api.twitter.com/2/tweets"
            req_headers = {"Content-Type": "application/json"}
            _, signed_headers, _ = oauth.sign(
                uri, http_method="POST", body=json.dumps(body), headers=req_headers
            )

            post_resp = requests.post(
                uri, json=body,
                headers={**req_headers, **signed_headers},
                timeout=30
            )

            if post_resp.status_code == 201:
                print(f"  ✅ Replied on Twitter to: {best_tweet['text'][:60]}")
                replied["twitter"].append(best_tweet["id"])
                save_replied_posts(replied)
                return {
                    "platform": "Twitter",
                    "tweet": best_tweet['text'][:100],
                    "link": f"https://twitter.com/i/status/{best_tweet['id']}",
                    "reply": clean_reply
                }
            else:
                print(f"  ❌ Twitter reply failed: {post_resp.status_code} {post_resp.text[:200]}")
                replied["twitter"].append(best_tweet["id"])
                save_replied_posts(replied)
                return None
        else:
            # Can't post, but send the opportunity to user via Telegram
            print("  ℹ️ Can't post to Twitter (no write credentials), sending opportunity to Telegram")
            opp_msg = (
                f"🐦 TWITTER OPPORTUNITY:\n"
                f"Tweet: {best_tweet['text'][:200]}\n"
                f"Link: https://twitter.com/i/status/{best_tweet['id']}\n"
                f"Suggested reply: {clean_reply}"
            )
            send_telegram(opp_msg)
            replied["twitter"].append(best_tweet["id"])
            save_replied_posts(replied)
            return {
                "platform": "Twitter (manual)",
                "tweet": best_tweet['text'][:100],
                "link": f"https://twitter.com/i/status/{best_tweet['id']}",
                "reply": clean_reply
            }

    except Exception as e:
        print(f"  ❌ Twitter error: {e}")
        return None


# ============================================================
# 4. MASTODON AUTO-ENGAGEMENT
# ============================================================
def mastodon_find_and_reply(trend_data):
    """Search Mastodon for relevant posts and engage."""
    if not MASTODON_ACCESS_TOKEN:
        print("⚠️ Mastodon not configured, skipping")
        return None

    print("🦣 Searching Mastodon for conversations...")

    replied = load_replied_posts()
    headers = {"Authorization": f"Bearer {MASTODON_ACCESS_TOKEN}"}

    search_queries = [
        "world cup sweepstake",
        "football office pool",
        "world cup 2026 bracket",
        "football sweepstake kit",
    ]
    query = random.choice(search_queries)

    try:
        # Search for posts
        search_url = f"https://{MASTODON_INSTANCE}/api/v2/search"
        params = {
            "q": query,
            "type": "statuses",
            "limit": 10,
        }
        response = requests.get(search_url, headers=headers, params=params, timeout=30)

        if response.status_code != 200:
            print(f"  ⚠️ Mastodon search failed: {response.status_code}")
            return None

        statuses = response.json().get("statuses", [])
        if not statuses:
            print("  ℹ️ No Mastodon posts found")
            return None

        # Find the best post to reply to
        best_status = None
        best_score = 0

        for status in statuses:
            if status["id"] in replied["mastodon"]:
                continue

            score = 0
            text_lower = status["content"].lower()

            # Strip HTML for scoring
            clean_text = re.sub(r'<[^>]+>', '', text_lower)

            if any(q in clean_text for q in ["how", "what", "anyone", "help", "looking"]):
                score += 3
            if any(kw in clean_text for kw in ["sweepstake", "pool", "bracket", "predictor"]):
                score += 2
            if status.get("replies_count", 0) < 5:
                score += 1

            if score > best_score:
                best_score = score
                best_status = status

        if not best_status:
            print("  ℹ️ No good Mastodon posts found this run")
            return None

        # Generate reply
        clean_status = re.sub(r'<[^>]+>', '', best_status["content"])

        prompt = f"""You are a real football fan on Mastodon. You saw this post:

POST: {clean_status[:500]}

Write a helpful reply. RULES:
- Be AUTHENTIC and friendly (Mastodon has a warm, community tone)
- Give genuinely useful advice first
- Casually mention at the end: "Found this sweepstake kit that made my office pool way easier — has 48 team cards and scoring systems built in" — adapt wording naturally
- You CAN include the link {PAYHIP_LINK} since Mastodon is more relaxed
- DO NOT use marketing language
- No markdown, no asterisks
- Keep under 300 words"""

        reply_text = ai_generate(prompt, temperature=0.9)
        clean_reply = sanitize_text(reply_text)

        # Post the reply
        reply_url = f"https://{MASTODON_INSTANCE}/api/v1/statuses"
        reply_data = {
            "status": clean_reply,
            "in_reply_to_id": best_status["id"],
        }
        post_resp = requests.post(reply_url, headers=headers, json=reply_data, timeout=30)

        if post_resp.status_code == 200:
            reply_url_result = post_resp.json().get("url", "")
            print(f"  ✅ Replied on Mastodon: {clean_status[:60]}")
            replied["mastodon"].append(best_status["id"])
            save_replied_posts(replied)
            return {
                "platform": "Mastodon",
                "post": clean_status[:100],
                "link": best_status.get("url", ""),
                "reply": clean_reply[:200]
            }
        else:
            print(f"  ❌ Mastodon reply failed: {post_resp.status_code}")
            replied["mastodon"].append(best_status["id"])
            save_replied_posts(replied)
            return None

    except Exception as e:
        print(f"  ❌ Mastodon error: {e}")
        return None


# ============================================================
# 5. WEB DISCOVERY — Find MORE places to engage
# ============================================================
def discover_engagement_opportunities(trend_data):
    """Use AI + trends to find WHERE people are talking about World Cup pools."""
    print("🌍 Discovering engagement opportunities...")

    ideas_str = ", ".join(i["keyword"] for i in trend_data["trending_ideas"][:3]) if trend_data["trending_ideas"] else "sweepstakes, pools"
    countries = ", ".join(trend_data["top_countries"][:3])

    prompt = f"""I sell a World Cup Sweepstake Kit PDF ({PRODUCT_PRICE}) — {PRODUCT_DESC}

Based on these trending topics: {ideas_str}
And these hot countries: {countries}

List 5 SPECIFIC places online where real people are CURRENTLY discussing World Cup sweepstakes, office pools, or football brackets. For each:
1. PLATFORM (Reddit subreddit, Facebook group name, Quora topic, forum URL, Discord server, etc.)
2. WHAT THEY'RE DISKUSSING (the specific conversation happening)
3. HOW TO ENGAGE (what to say that's genuinely helpful and naturally mentions my kit)
4. THE LINK or search term to find it

Focus on places where I can jump into EXISTING conversations — not create new posts.
Be very specific (exact subreddit names, exact search queries, exact Quora questions).

No markdown. No asterisks. Plain text only."""

    return ai_generate(prompt, temperature=0.8)


# ============================================================
# 6. DAILY BRIEF GENERATOR
# ============================================================
def generate_daily_brief(trend_data, product_research, engagement_results, discovery):
    """Generate the comprehensive daily brief sent via Telegram."""
    countries = ", ".join(trend_data["top_countries"][:5])
    ideas = ", ".join(
        f"{i['keyword']} ({i['score']})" for i in trend_data["trending_ideas"][:5]
    ) if trend_data["trending_ideas"] else "None today"

    # Build engagement summary
    engage_summary = ""
    for result in engagement_results:
        if result:
            engage_summary += f"\n  {result['platform']}: Replied to '{result.get('title', result.get('tweet', result.get('post', '')))[:60]}'"

    if not engage_summary:
        engage_summary = "\n  No auto-replies this run (no good conversations found or platforms not configured)"

    brief = f"""SULWEPRINTS DAILY AGENT BRIEF
{datetime.now().strftime('%A, %B %d, %Y %H:%M')}

HOT MARKETS: {countries}

TRENDING IDEAS: {ideas}

AUTO-ENGAGEMENT RESULTS: {engage_summary}

PRODUCT OPPORTUNITIES:
{product_research[:1500]}

WHERE TO ENGAGE NEXT (manual):
{discovery[:1500]}

Your kit: {PAYHIP_LINK}"""

    return brief


# ============================================================
# 7. MAIN AGENT RUNNER
# ============================================================
def main():
    print("=" * 55)
    print(f"🚀 SulwePrints Agent v3.0 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   Auto-Engagement Mode: Find people. Reply helpfully. Sell naturally.")
    print("=" * 55)

    # Step 1: Research trends
    trend_data = check_trends()
    print(f"  Hot markets: {trend_data['top_countries'][:3]}")
    print(f"  Trending ideas: {[i['keyword'] for i in trend_data['trending_ideas'][:3]]}")

    # Step 2: Research digital product opportunities
    product_research = research_digital_products(trend_data)

    # Step 3: AUTO-ENGAGE on all configured platforms
    print("\n🤖 Auto-engaging on platforms...")
    engagement_results = []

    # Reddit (finds questions, replies helpfully)
    reddit_result = reddit_find_and_reply(trend_data)
    engagement_results.append(reddit_result)

    # Twitter/X (finds tweets, replies)
    twitter_result = twitter_find_and_reply(trend_data)
    engagement_results.append(twitter_result)

    # Mastodon (finds posts, replies)
    mastodon_result = mastodon_find_and_reply(trend_data)
    engagement_results.append(mastodon_result)

    # Step 4: Discover more engagement opportunities
    discovery = discover_engagement_opportunities(trend_data)

    # Step 5: Send daily brief via Telegram
    print("\n📱 Compiling daily brief...")
    brief = generate_daily_brief(trend_data, product_research, engagement_results, discovery)
    send_telegram(brief)

    # Step 6: Summary
    print("\n" + "=" * 55)
    print("📊 ENGAGEMENT RESULTS:")
    active_platforms = 0
    for result in engagement_results:
        if result:
            active_platforms += 1
            print(f"  ✅ {result['platform']}: {result.get('title', result.get('tweet', result.get('post', '')))[:60]}")
        else:
            pass  # Skip unconfigured platforms

    if active_platforms == 0:
        print("  ⬜ No platforms configured yet — add Reddit/Twitter/Mastodon to start!")

    print(f"\n  Active platforms: {active_platforms}/3")
    print(f"  Platforms: Reddit={'✅' if HAS_PRAW and REDDIT_CLIENT_ID else '⬜'}, "
          f"Twitter={'✅' if TWITTER_BEARER_TOKEN else '⬜'}, "
          f"Mastodon={'✅' if MASTODON_ACCESS_TOKEN else '⬜'}")
    print("=" * 55)
    print("🏁 Agent finished.")


if __name__ == "__main__":
    main()
