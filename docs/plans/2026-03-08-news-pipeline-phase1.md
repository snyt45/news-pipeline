# News Pipeline Phase 1 実装プラン

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** RSSフィードから記事を取得し、Gemini 2.5 Flash Liteで10-15件にキュレーション、日本語要約付きでターミナルに出力する。

**Architecture:** main.py 1ファイルに全処理を書く。config/feeds.yamlからフィードURL、config/profile.yamlから興味・嗜好を読み込み、feedparserでRSS取得後、Gemini APIでキュレーション+日本語要約を実行。`--dry-run`フラグで出力先を切り替え。

**Tech Stack:** Python 3.13, feedparser, PyYAML, python-dotenv, google-genai, pytest

---

### Task 1: プロジェクト基盤ファイル

**Files:**
- Create: `~/work/news-pipeline/.gitignore`
- Create: `~/work/news-pipeline/.env.example`
- Create: `~/work/news-pipeline/requirements.txt`
- Create: `~/work/news-pipeline/.python-version`

**Step 1: .gitignore 作成**

```
.env
credentials.json
logs/
__pycache__/
.venv/
```

**Step 2: .env.example 作成**

```
GEMINI_API_KEY=your_gemini_api_key_here
SPREADSHEET_ID=
GOOGLE_DOC_ID=
GOOGLE_CREDENTIALS_PATH=./credentials.json
```

**Step 3: requirements.txt 作成**

```
feedparser
pyyaml
python-dotenv
google-genai
pytest
```

**Step 4: .python-version 作成**

```
3.13
```

**Step 5: venv作成と依存インストール**

Run: `cd ~/work/news-pipeline && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`

**Step 6: コミット**

```bash
cd ~/work/news-pipeline
git add .gitignore .env.example requirements.txt .python-version
git commit -m "プロジェクト基盤ファイルを追加"
```

---

### Task 2: config ファイル作成

**Files:**
- Create: `~/work/news-pipeline/config/feeds.yaml`
- Create: `~/work/news-pipeline/config/profile.yaml`

**Step 1: feeds.yaml 作成**

```yaml
feeds:
  - name: "Zenn - トレンド"
    url: "https://zenn.dev/feed"
    lang: "ja"
  - name: "Hacker News (100pt+)"
    url: "https://hnrss.org/newest?points=100"
    lang: "en"
  - name: "はてなブックマーク - テクノロジー"
    url: "https://b.hatena.ne.jp/hotentry/it.rss"
    lang: "ja"
```

**Step 2: profile.yaml 作成**

```yaml
role: "フルスタックエンジニア（Ruby, TypeScript, React）"
model: "gemini-2.5-flash-lite"
language: "ja"
articles_per_day: 15

interests:
  - "AI/LLMの実用的な活用事例や新動向"
  - "開発ツール・ワークフロー改善"
  - "個人開発・副業に活かせる知見"
  - "ソフトウェアアーキテクチャ・設計パターン"
  - "Obsidian・PKM・セカンドブレイン"

exclude:
  - "初心者向けチュートリアル"
  - "プレスリリースや広告色が強い記事"
  - "内容の薄い焼き直し・まとめ記事"
  - "AIスロップ"
```

**Step 3: コミット**

```bash
git add config/
git commit -m "config ファイルを追加（feeds.yaml, profile.yaml）"
```

---

### Task 3: RSS取得機能 — テスト

**Files:**
- Create: `~/work/news-pipeline/main.py`
- Create: `~/work/news-pipeline/tests/test_main.py`

**Step 1: fetch_feedsのテストを書く**

```python
# tests/test_main.py
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta


def test_fetch_feeds_returns_articles_from_yaml(tmp_path):
    """feeds.yamlを読み込んでフィードから記事を取得する"""
    feeds_yaml = tmp_path / "feeds.yaml"
    feeds_yaml.write_text(
        "feeds:\n"
        '  - name: "Test Feed"\n'
        '    url: "https://example.com/feed"\n'
        '    lang: "ja"\n'
    )

    now = datetime.now(timezone.utc)
    mock_entry = MagicMock()
    mock_entry.title = "テスト記事"
    mock_entry.link = "https://example.com/article"
    mock_entry.get.return_value = "テスト要約"
    mock_entry.published_parsed = (now - timedelta(hours=1)).timetuple()

    mock_feed = MagicMock()
    mock_feed.entries = [mock_entry]
    mock_feed.bozo = False

    with patch("main.feedparser.parse", return_value=mock_feed):
        from main import fetch_feeds
        articles = fetch_feeds(str(feeds_yaml))

    assert len(articles) == 1
    assert articles[0]["title"] == "テスト記事"
    assert articles[0]["url"] == "https://example.com/article"
    assert articles[0]["source"] == "Test Feed"
    assert articles[0]["lang"] == "ja"


def test_fetch_feeds_skips_old_articles(tmp_path):
    """24時間以上前の記事はスキップする"""
    feeds_yaml = tmp_path / "feeds.yaml"
    feeds_yaml.write_text(
        "feeds:\n"
        '  - name: "Test Feed"\n'
        '    url: "https://example.com/feed"\n'
        '    lang: "ja"\n'
    )

    old_time = datetime.now(timezone.utc) - timedelta(hours=25)
    mock_entry = MagicMock()
    mock_entry.title = "古い記事"
    mock_entry.link = "https://example.com/old"
    mock_entry.get.return_value = ""
    mock_entry.published_parsed = old_time.timetuple()

    mock_feed = MagicMock()
    mock_feed.entries = [mock_entry]
    mock_feed.bozo = False

    with patch("main.feedparser.parse", return_value=mock_feed):
        from main import fetch_feeds
        articles = fetch_feeds(str(feeds_yaml))

    assert len(articles) == 0


def test_fetch_feeds_skips_failed_feed(tmp_path):
    """フィード取得失敗時はスキップして続行する"""
    feeds_yaml = tmp_path / "feeds.yaml"
    feeds_yaml.write_text(
        "feeds:\n"
        '  - name: "Bad Feed"\n'
        '    url: "https://example.com/bad"\n'
        '    lang: "en"\n'
    )

    mock_feed = MagicMock()
    mock_feed.entries = []
    mock_feed.bozo = True

    with patch("main.feedparser.parse", return_value=mock_feed):
        from main import fetch_feeds
        articles = fetch_feeds(str(feeds_yaml))

    assert len(articles) == 0
```

**Step 2: テストが失敗することを確認**

Run: `cd ~/work/news-pipeline && source .venv/bin/activate && python -m pytest tests/test_main.py -v`

Expected: FAIL（main.pyにfetch_feedsがない）

---

### Task 4: RSS取得機能 — 実装

**Files:**
- Modify: `~/work/news-pipeline/main.py`

**Step 1: fetch_feedsを実装**

```python
# main.py
import feedparser
import yaml
from datetime import datetime, timezone, timedelta
from calendar import timegm


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
            published = entry.get("published_parsed")
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
```

**Step 2: テストがパスすることを確認**

Run: `cd ~/work/news-pipeline && source .venv/bin/activate && python -m pytest tests/test_main.py -v`

Expected: 3 passed

**Step 3: コミット**

```bash
git add main.py tests/
git commit -m "RSS取得機能を実装（fetch_feeds）"
```

---

### Task 5: プロンプト生成 — テスト

**Files:**
- Modify: `~/work/news-pipeline/tests/test_main.py`

**Step 1: build_promptのテストを追加**

```python
# tests/test_main.py に追加

def test_build_prompt_includes_interests_and_excludes(tmp_path):
    """profile.yamlの内容がプロンプトに反映される"""
    profile_yaml = tmp_path / "profile.yaml"
    profile_yaml.write_text(
        'role: "テストエンジニア"\n'
        'model: "gemini-2.5-flash-lite"\n'
        'language: "ja"\n'
        "articles_per_day: 10\n"
        "interests:\n"
        '  - "AI活用"\n'
        '  - "開発ツール"\n'
        "exclude:\n"
        '  - "初心者向け"\n'
        '  - "広告記事"\n'
    )

    from main import build_prompt
    prompt = build_prompt(str(profile_yaml), [])

    assert "テストエンジニア" in prompt
    assert "AI活用" in prompt
    assert "開発ツール" in prompt
    assert "初心者向け" in prompt
    assert "広告記事" in prompt
    assert "10" in prompt
    assert "ja" in prompt or "日本語" in prompt
```

**Step 2: テストが失敗することを確認**

Run: `cd ~/work/news-pipeline && source .venv/bin/activate && python -m pytest tests/test_main.py::test_build_prompt_includes_interests_and_excludes -v`

Expected: FAIL

---

### Task 6: プロンプト生成 — 実装

**Files:**
- Modify: `~/work/news-pipeline/main.py`

**Step 1: build_promptを実装**

```python
# main.py に追加

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
```

**Step 2: テストがパスすることを確認**

Run: `cd ~/work/news-pipeline && source .venv/bin/activate && python -m pytest tests/test_main.py -v`

Expected: ALL passed

**Step 3: コミット**

```bash
git add main.py tests/
git commit -m "プロンプト生成機能を実装（build_prompt）"
```

---

### Task 7: キュレーション機能 — テスト

**Files:**
- Modify: `~/work/news-pipeline/tests/test_main.py`

**Step 1: curateのテストを追加（APIレスポンスをモック）**

```python
# tests/test_main.py に追加
import json


def test_curate_returns_parsed_articles(tmp_path):
    """Gemini APIのレスポンスをパースして記事リストを返す"""
    profile_yaml = tmp_path / "profile.yaml"
    profile_yaml.write_text(
        'role: "テストエンジニア"\n'
        'model: "gemini-2.5-flash-lite"\n'
        'language: "ja"\n'
        "articles_per_day: 2\n"
        "interests:\n"
        '  - "AI活用"\n'
        "exclude:\n"
        '  - "広告"\n'
    )

    articles = [
        {"title": "Article 1", "url": "https://example.com/1", "summary": "Summary 1", "source": "Test", "lang": "en"},
        {"title": "Article 2", "url": "https://example.com/2", "summary": "Summary 2", "source": "Test", "lang": "ja"},
    ]

    curated = [
        {"title": "Article 1", "url": "https://example.com/1", "summary_ja": "要約1", "source": "Test", "category": "AI/LLM"},
    ]
    api_response_text = f"```json\n{json.dumps(curated, ensure_ascii=False)}\n```"

    mock_response = MagicMock()
    mock_response.text = api_response_text

    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response

    with patch("main.genai") as mock_genai:
        mock_genai.Client.return_value.models.generate_content.return_value = mock_response
        from main import curate
        result = curate(articles, str(profile_yaml))

    assert len(result) == 1
    assert result[0]["title"] == "Article 1"
    assert result[0]["summary_ja"] == "要約1"
    assert result[0]["category"] == "AI/LLM"
```

**Step 2: テストが失敗することを確認**

Run: `cd ~/work/news-pipeline && source .venv/bin/activate && python -m pytest tests/test_main.py::test_curate_returns_parsed_articles -v`

Expected: FAIL

---

### Task 8: キュレーション機能 — 実装

**Files:**
- Modify: `~/work/news-pipeline/main.py`

**Step 1: curateを実装**

```python
# main.py に追加（ファイル先頭のimportにも追加）
import json
import os
import re
from google import genai
from dotenv import load_dotenv

load_dotenv()


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
```

**Step 2: テストがパスすることを確認**

Run: `cd ~/work/news-pipeline && source .venv/bin/activate && python -m pytest tests/test_main.py -v`

Expected: ALL passed

**Step 3: コミット**

```bash
git add main.py tests/
git commit -m "キュレーション機能を実装（curate, parse_curate_response）"
```

---

### Task 9: CLIエントリポイント + --dry-run

**Files:**
- Modify: `~/work/news-pipeline/main.py`

**Step 1: main関数とCLIを実装**

```python
# main.py の末尾に追加
import argparse


def main():
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

    # Phase 2: Google出力（後で実装）
    print("[TODO] Spreadsheet追記 + Google Docs上書き")


if __name__ == "__main__":
    main()
```

**Step 2: --dry-run で動作確認（実際のAPI呼び出し）**

Run: `cd ~/work/news-pipeline && source .venv/bin/activate && python main.py --dry-run`

Expected: RSS取得 → Geminiキュレーション → ターミナルに10-15件表示

※ .envにGEMINI_API_KEYが設定されている必要がある。未設定なら先にGoogle AI StudioでAPIキーを取得する。

**Step 3: コミット**

```bash
git add main.py
git commit -m "CLIエントリポイントと--dry-runモードを実装"
```

---

### Task 10: GitHubリポジトリ作成 + push

**Step 1: README.md 作成**

```markdown
# news-pipeline

RSS + LLMキュレーション + Google Spreadsheet + NotebookLMラジオのパイプライン。

散歩中にNotebookLMラジオで自分向けの技術ニュースを聴くための仕組み。

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env にAPIキーを設定
```

## 使い方

```bash
# キュレーション結果をターミナルに出力（Google出力なし）
python main.py --dry-run

# 全パイプライン実行（Spreadsheet + Google Docs出力）
python main.py
```

## カスタマイズ

1. `config/feeds.yaml` — RSSフィードURLを追加・変更
2. `config/profile.yaml` — 興味・嗜好・除外基準を変更
3. `.env` — APIキー・Google リソースIDを設定
```

**Step 2: GitHubにパブリックリポジトリ作成 + push**

```bash
cd ~/work/news-pipeline
git add README.md
git commit -m "README追加"
gh repo create news-pipeline --public --source=. --push
```
