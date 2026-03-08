import argparse
import feedparser
import json
import os
import re
import yaml
from collections import defaultdict
from datetime import datetime, timezone, timedelta, date
from calendar import timegm
from google import genai
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build

FEEDS_PATH = "config/feeds.yaml"
PROFILE_PATH = "config/profile.yaml"
MAX_AGE_HOURS = 24
SUMMARY_MAX_LENGTH = 200
DEFAULT_SHEET_NAME = "シート1"
TOKEN_WARNING_THRESHOLD = 80000


def fetch_feeds(feeds_path=FEEDS_PATH):
    with open(feeds_path) as f:
        config = yaml.safe_load(f)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
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


def build_prompt(profile, articles=None):

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

    prompt = build_prompt(profile, articles)

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


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
]


def build_sheets_service():
    credentials_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "./credentials.json")
    creds = ServiceAccountCredentials.from_service_account_file(
        credentials_path, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds)


def build_docs_service():
    credentials_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "./credentials.json")
    creds = ServiceAccountCredentials.from_service_account_file(
        credentials_path, scopes=SCOPES
    )
    return build("docs", "v1", credentials=creds)


def check_spreadsheet_token_usage(service):
    spreadsheet_id = os.environ["SPREADSHEET_ID"]
    sheet_name = os.environ.get("SHEET_NAME", DEFAULT_SHEET_NAME)
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=sheet_name,
    ).execute()
    all_rows = result.get("values", [])

    total_chars = sum(len(cell) for row in all_rows for cell in row)
    estimated_tokens = total_chars  # 日本語1文字≈1トークンで概算

    if estimated_tokens > TOKEN_WARNING_THRESHOLD:
        print(f"[WARNING] Spreadsheetのトークン使用量が閾値を超えています（推定{estimated_tokens:,}トークン / 上限100,000トークン）")
        print("[WARNING] NotebookLMのソース制限に達する可能性があります。新しいSpreadsheetを作成し、.envのSPREADSHEET_IDを差し替えてください")
        return True
    return False


def already_curated_today(service):
    spreadsheet_id = os.environ["SPREADSHEET_ID"]
    sheet_name = os.environ.get("SHEET_NAME", DEFAULT_SHEET_NAME)
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A:A",
    ).execute()
    existing_dates = [row[0] for row in result.get("values", []) if row]
    return date.today().isoformat() in existing_dates


def append_to_spreadsheet(service, curated):
    if not curated:
        return

    spreadsheet_id = os.environ["SPREADSHEET_ID"]
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
        range=os.environ.get("SHEET_NAME", DEFAULT_SHEET_NAME),
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()

    print(f"[Spreadsheet] {len(rows)}件追記しました")


def read_today_from_spreadsheet(service):
    spreadsheet_id = os.environ["SPREADSHEET_ID"]
    sheet_name = os.environ.get("SHEET_NAME", DEFAULT_SHEET_NAME)
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=sheet_name,
    ).execute()
    all_rows = result.get("values", [])
    today = date.today().isoformat()
    return [row for row in all_rows if row and row[0] == today]


def write_to_google_docs(docs_service, rows):
    if not rows:
        return

    doc_id = os.environ["GOOGLE_DOC_ID"]

    # 既存の内容を取得して削除
    doc = docs_service.documents().get(documentId=doc_id).execute()
    end_index = doc["body"]["content"][-1]["endIndex"]
    requests = []
    if end_index > 2:
        requests.append({"deleteContentRange": {
            "range": {"startIndex": 1, "endIndex": end_index - 1}
        }})

    # カテゴリ別にグループ化
    categories = defaultdict(list)
    for row in rows:
        category = row[1] if len(row) > 1 else "その他"
        categories[category].append(row)

    # テキスト生成
    today = rows[0][0] if rows else date.today().isoformat()
    lines = [f"{today} 技術ニュース\n\n"]
    for category, articles in categories.items():
        lines.append(f"## {category}\n\n")
        for a in articles:
            title = a[2] if len(a) > 2 else ""
            url = a[3] if len(a) > 3 else ""
            summary = a[4] if len(a) > 4 else ""
            lines.append(f"- {title}\n")
            if url:
                lines.append(f"  URL: {url}\n")
            if summary:
                lines.append(f"  {summary}\n")
            lines.append("\n")

    text = "".join(lines)
    requests.append({"insertText": {"location": {"index": 1}, "text": text}})

    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": requests},
    ).execute()


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="News Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="ターミナル出力のみ（Google出力をスキップ）")
    args = parser.parse_args()

    has_doc_id = bool(os.environ.get("GOOGLE_DOC_ID"))

    if not args.dry_run:
        if not os.environ.get("GEMINI_API_KEY"):
            print("[ERROR] GEMINI_API_KEYが設定されていません。.envを確認してください")
            return
        if not os.environ.get("SPREADSHEET_ID"):
            print("[ERROR] SPREADSHEET_IDが設定されていません。.envを確認してください")
            return
        if not has_doc_id:
            print("[INFO] GOOGLE_DOC_IDが未設定のため、Google Docs書き出しはスキップされます")

        sheets_service = build_sheets_service()
        if already_curated_today(sheets_service):
            print(f"[Spreadsheet] {date.today().isoformat()}のデータはすでに存在するためスキップします")
            # 既存データでもDocs書き出しは実行（手動追記分を反映するため）
            if has_doc_id:
                rows = read_today_from_spreadsheet(sheets_service)
                if rows:
                    docs_service = build_docs_service()
                    print("[Google Docs] 書き出し中...")
                    write_to_google_docs(docs_service, rows)
                    print(f"[Google Docs] {len(rows)}件書き出しました")
            return

    print("[RSS] 取得中...")
    articles = fetch_feeds()
    print(f"[RSS] {len(articles)}件の記事を取得")

    if not articles:
        print("[RSS] 記事が見つかりませんでした")
        return

    print("[Gemini] キュレーション中...")
    curated = curate(articles)
    print(f"[Gemini] {len(curated)}件に厳選")

    if args.dry_run:
        for i, a in enumerate(curated, 1):
            print(f"\n{'='*60}")
            print(f"{i}. [{a.get('category', '')}] {a['title']}")
            print(f"   {a['url']}")
            print(f"   {a.get('summary_ja', '')}")
        return

    check_spreadsheet_token_usage(sheets_service)

    print("[Spreadsheet] 追記中...")
    append_to_spreadsheet(sheets_service, curated)

    if has_doc_id:
        docs_service = build_docs_service()
        rows = read_today_from_spreadsheet(sheets_service)
        print("[Google Docs] 書き出し中...")
        write_to_google_docs(docs_service, rows)
        print(f"[Google Docs] {len(rows)}件書き出しました")


if __name__ == "__main__":
    main()
