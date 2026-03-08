import argparse
import feedparser
import json
import os
import re
import yaml
from datetime import datetime, timezone, timedelta, date
from calendar import timegm
from google import genai
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build

FEEDS_PATH = "config/feeds.yaml"
PROFILE_PATH = "config/profile.yaml"
ARTICLE_MAX_AGE_HOURS = 24
SUMMARY_MAX_LENGTH = 200
SPREADSHEET_SHEET_NAME = os.environ.get("SPREADSHEET_SHEET_NAME", "シート1")


def fetch_feeds(feeds_path=FEEDS_PATH):
    with open(feeds_path) as f:
        config = yaml.safe_load(f)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=ARTICLE_MAX_AGE_HOURS)
    articles = []

    for feed_conf in config["feeds"]:
        feed = feedparser.parse(feed_conf["url"])
        if feed.bozo and not feed.entries:
            print(f"[WARN] フィード取得失敗: {feed_conf['name']}")
            continue

        for entry in feed.entries:
            published_parsed = getattr(entry, "published_parsed", None)
            published_dt = None
            if published_parsed:
                published_dt = datetime.fromtimestamp(
                    timegm(published_parsed), tz=timezone.utc
                )
                if published_dt < cutoff:
                    continue

            articles.append({
                "title": entry.title,
                "url": entry.link,
                "summary": entry.get("summary", ""),
                "source": feed_conf["name"],
                "lang": feed_conf.get("lang", "en"),
                "published": str(published_dt) if published_dt else "",
            })

    return articles


def build_prompt(profile_path=PROFILE_PATH, articles=None, profile=None):
    if profile is None:
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
                lines.append(f"   要約: {a['summary'][:SUMMARY_MAX_LENGTH]}")
            lines.append("")

    return "\n".join(lines)


def curate(articles, profile_path=PROFILE_PATH):
    if not articles:
        return []

    with open(profile_path) as f:
        profile = yaml.safe_load(f)

    prompt = build_prompt(profile_path, articles, profile=profile)

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


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def append_to_spreadsheet(curated):
    if not curated:
        return

    spreadsheet_id = os.environ["SPREADSHEET_ID"]
    credentials_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "./credentials.json")

    creds = ServiceAccountCredentials.from_service_account_file(
        credentials_path, scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=creds)

    today = date.today().isoformat()
    rows = []
    for a in curated:
        rows.append([
            today,
            a.get("category", ""),
            a["title"],
            a["url"],
            a.get("summary_ja", ""),
            a.get("source", ""),
        ])

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=SPREADSHEET_SHEET_NAME,
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()

    print(f"Spreadsheetに{len(rows)}件追記しました")


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="News Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="ターミナル出力のみ（Google出力をスキップ）")
    args = parser.parse_args()

    print("RSS取得中...")
    articles = fetch_feeds()
    print(f"{len(articles)}件の記事を取得")

    if not articles:
        print("記事が見つかりませんでした")
        return

    print("キュレーション中...")
    curated = curate(articles)
    print(f"{len(curated)}件に厳選")

    if args.dry_run:
        for i, a in enumerate(curated, 1):
            print(f"\n{'='*60}")
            print(f"{i}. [{a.get('category', '')}] {a['title']}")
            print(f"   {a['url']}")
            print(f"   {a.get('summary_ja', '')}")
        return

    print("Spreadsheetに追記中...")
    append_to_spreadsheet(curated)


if __name__ == "__main__":
    main()
