import feedparser
import json
import os
import re
import yaml
from datetime import datetime, timezone, timedelta
from calendar import timegm
from google import genai
from dotenv import load_dotenv

load_dotenv()


def fetch_feeds(feeds_path="config/feeds.yaml"):
    with open(feeds_path) as f:
        config = yaml.safe_load(f)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    articles = []

    for feed_conf in config["feeds"]:
        feed = feedparser.parse(feed_conf["url"])
        if feed.bozo and not feed.entries:
            print(f"[WARN] フィード取得失敗: {feed_conf['name']}")
            continue

        for entry in feed.entries:
            published = getattr(entry, "published_parsed", None)
            if published:
                published_dt = datetime.fromtimestamp(
                    timegm(published), tz=timezone.utc
                )
                if published_dt < cutoff:
                    continue

            articles.append({
                "title": entry.title,
                "url": entry.link,
                "summary": entry.get("summary", ""),
                "source": feed_conf["name"],
                "lang": feed_conf.get("lang", "en"),
                "published": str(published_dt) if published else "",
            })

    return articles


def build_prompt(profile_path="config/profile.yaml", articles=None):
    with open(profile_path) as f:
        profile = yaml.safe_load(f)

    lines = [
        f"あなたは{profile['role']}向けの技術キュレーターです。",
        f"以下の記事リストから、最も価値のある{profile['articles_per_day']}件を厳選してください。",
        "",
        "## 選定基準（上にあるほど優先）",
    ]
    for interest in profile["interests"]:
        lines.append(f"- {interest}")

    lines.append("")
    lines.append("## 除外基準")
    for item in profile["exclude"]:
        lines.append(f"- {item}")

    lang = profile.get("language", "ja")
    lines.extend([
        "",
        "## 出力形式",
        f"各記事について{lang}で2-3行の要約をつけてください。",
        f"英語記事の要約も{lang}で書いてください。",
        "カテゴリ（AI/LLM, DevTools, Architecture, IndieHacker等）も付与してください。",
        "提供された情報のみに基づいて判断してください。",
        "",
        "以下のJSON形式で出力してください:",
        "```json",
        '[{"title": "...", "url": "...", "summary_ja": "...", "source": "...", "category": "..."}]',
        "```",
        "",
        "## 記事リスト",
    ])

    if articles:
        for i, a in enumerate(articles, 1):
            lines.append(f"{i}. [{a['source']}] {a['title']}")
            lines.append(f"   URL: {a['url']}")
            if a.get("summary"):
                lines.append(f"   要約: {a['summary'][:200]}")
            lines.append("")

    return "\n".join(lines)


def curate(articles, profile_path="config/profile.yaml"):
    if not articles:
        return []

    with open(profile_path) as f:
        profile = yaml.safe_load(f)

    prompt = build_prompt(profile_path, articles)

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model=profile["model"],
        contents=prompt,
    )

    return parse_curate_response(response.text)


def parse_curate_response(text):
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print("[WARN] キュレーション結果のパースに失敗")
        return []
