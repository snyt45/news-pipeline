# Google Docs書き出し + Spreadsheetトークン警告 実装プラン

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Spreadsheetから今日の日付の行を読み取り、Google Docsにカテゴリ別に構造化して上書きする。Spreadsheetのトークン使用量が閾値を超えたら警告を出す。

**Architecture:** main.pyに3つの関数を追加する。`read_today_from_spreadsheet()`でSpreadsheetから今日分を取得し、`write_to_google_docs()`でDocsに上書き、`check_spreadsheet_token_usage()`でトークン使用量を概算して警告する。Google Docs APIのスコープを追加し、`build_docs_service()`で認証する。

**Tech Stack:** 既存のPython 3.13, google-auth, google-api-python-client, pytest

---

### Task 1: Google Docs APIスコープ追加 + build_docs_service

**Files:**
- Modify: `main.py:130` (SCOPES定数の後)

**Step 1: テストを書く**

```python
# tests/test_main.py に追加

def test_build_docs_service_creates_service():
    """Google Docs APIサービスが構築される"""
    mock_creds = MagicMock()

    with patch("main.ServiceAccountCredentials.from_service_account_file", return_value=mock_creds) as mock_from_file, \
         patch("main.build") as mock_build, \
         patch.dict("os.environ", {"GOOGLE_CREDENTIALS_PATH": "./credentials.json"}):
        from main import build_docs_service
        build_docs_service()

    mock_build.assert_called_once()
    call_args = mock_build.call_args
    assert call_args[0][0] == "docs"
    assert call_args[0][1] == "v1"
```

**Step 2: テストが失敗することを確認**

Run: `.venv/bin/python -m pytest tests/test_main.py::test_build_docs_service_creates_service -v`

Expected: FAIL（build_docs_serviceがない）

**Step 3: 実装**

main.pyのSCOPES定数を修正し、`build_docs_service()`を追加:

```python
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
```

**Step 4: テストがパスすることを確認**

Run: `.venv/bin/python -m pytest tests/test_main.py -v`

Expected: ALL passed

**Step 5: コミット**

```bash
git add main.py tests/test_main.py
git commit -m "Google Docs APIスコープとbuild_docs_serviceを追加"
```

---

### Task 2: read_today_from_spreadsheet

**Files:**
- Modify: `main.py` (append_to_spreadsheetの後)
- Modify: `tests/test_main.py`

**Step 1: テストを書く**

```python
# tests/test_main.py に追加

def test_read_today_from_spreadsheet_returns_today_rows():
    """Spreadsheetから今日の日付の行だけを返す"""
    from datetime import date
    today = date.today().isoformat()

    mock_service = MagicMock()
    mock_sheet = mock_service.spreadsheets.return_value.values.return_value
    mock_sheet.get.return_value.execute.return_value = {
        "values": [
            ["日付", "カテゴリ", "タイトル", "URL", "要約", "ソース"],
            [today, "AI/LLM", "今日の記事", "https://example.com/1", "要約1", "Zenn"],
            ["2026-03-01", "DevTools", "古い記事", "https://example.com/2", "要約2", "HN"],
            [today, "DevTools", "今日の記事2", "https://example.com/3", "要約3", "HN"],
        ]
    }

    with patch.dict("os.environ", {"SPREADSHEET_ID": "test-sheet-id"}):
        from main import read_today_from_spreadsheet
        rows = read_today_from_spreadsheet(mock_service)

    assert len(rows) == 2
    assert rows[0][2] == "今日の記事"
    assert rows[1][2] == "今日の記事2"
```

**Step 2: テストが失敗することを確認**

Run: `.venv/bin/python -m pytest tests/test_main.py::test_read_today_from_spreadsheet_returns_today_rows -v`

Expected: FAIL

**Step 3: 実装**

```python
def read_today_from_spreadsheet(service):
    spreadsheet_id = os.environ["SPREADSHEET_ID"]
    sheet_name = os.environ.get("SPREADSHEET_SHEET_NAME", SPREADSHEET_SHEET_NAME_DEFAULT)
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=sheet_name,
    ).execute()
    all_rows = result.get("values", [])
    today = date.today().isoformat()
    return [row for row in all_rows if row and row[0] == today]
```

**Step 4: テストがパスすることを確認**

Run: `.venv/bin/python -m pytest tests/test_main.py -v`

Expected: ALL passed

**Step 5: コミット**

```bash
git add main.py tests/test_main.py
git commit -m "Spreadsheetから今日分の行を読み取るread_today_from_spreadsheetを追加"
```

---

### Task 3: write_to_google_docs

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`

**Step 1: テストを書く**

```python
# tests/test_main.py に追加

def test_write_to_google_docs_formats_by_category():
    """カテゴリ別に構造化してDocsに書き出す"""
    from datetime import date
    today = date.today().isoformat()

    rows = [
        [today, "AI/LLM", "AI記事1", "https://example.com/1", "AI要約1", "Zenn"],
        [today, "AI/LLM", "AI記事2", "https://example.com/2", "AI要約2", "HN"],
        [today, "DevTools", "ツール記事", "https://example.com/3", "ツール要約", "Zenn"],
    ]

    mock_docs_service = MagicMock()
    mock_docs_service.documents.return_value.get.return_value.execute.return_value = {
        "body": {"content": [{"endIndex": 1}]}
    }

    with patch.dict("os.environ", {"GOOGLE_DOC_ID": "test-doc-id"}):
        from main import write_to_google_docs
        write_to_google_docs(mock_docs_service, rows)

    # batchUpdateが呼ばれたことを確認
    mock_docs_service.documents.return_value.batchUpdate.assert_called()
    call_args = mock_docs_service.documents.return_value.batchUpdate.call_args
    body = call_args[1]["body"] if "body" in call_args[1] else call_args.kwargs["body"]
    requests = body["requests"]

    # insertTextリクエストの中にカテゴリとタイトルが含まれる
    insert_texts = [r["insertText"]["text"] for r in requests if "insertText" in r]
    full_text = "".join(insert_texts)
    assert "AI/LLM" in full_text
    assert "DevTools" in full_text
    assert "AI記事1" in full_text
    assert "ツール記事" in full_text
    assert "https://example.com/1" in full_text


def test_write_to_google_docs_skips_when_no_rows():
    """行がない場合はAPI呼び出しをスキップする"""
    mock_docs_service = MagicMock()

    with patch.dict("os.environ", {"GOOGLE_DOC_ID": "test-doc-id"}):
        from main import write_to_google_docs
        write_to_google_docs(mock_docs_service, [])

    mock_docs_service.documents.return_value.batchUpdate.assert_not_called()
```

**Step 2: テストが失敗することを確認**

Run: `.venv/bin/python -m pytest tests/test_main.py::test_write_to_google_docs_formats_by_category -v`

Expected: FAIL

**Step 3: 実装**

Google Docs APIでは、既存の内容を削除してからテキストを挿入する。

```python
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
    from collections import defaultdict
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

    print(f"Google Docsに{len(rows)}件書き出しました")
```

**Step 4: テストがパスすることを確認**

Run: `.venv/bin/python -m pytest tests/test_main.py -v`

Expected: ALL passed

**Step 5: コミット**

```bash
git add main.py tests/test_main.py
git commit -m "Google Docsへの書き出し機能を実装（write_to_google_docs）"
```

---

### Task 4: check_spreadsheet_token_usage

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`

**Step 1: テストを書く**

```python
# tests/test_main.py に追加

def test_check_spreadsheet_token_usage_warns_over_threshold(capsys):
    """8万トークン超えで警告を出す"""
    mock_service = MagicMock()
    mock_sheet = mock_service.spreadsheets.return_value.values.return_value
    # 1セル100文字 x 1000行 x 6列 = 600,000文字 ≈ 150,000トークン（日本語1文字≈1トークン）
    row = ["a" * 100] * 6
    mock_sheet.get.return_value.execute.return_value = {
        "values": [row] * 1000
    }

    with patch.dict("os.environ", {"SPREADSHEET_ID": "test-sheet-id"}):
        from main import check_spreadsheet_token_usage
        result = check_spreadsheet_token_usage(mock_service)

    assert result is True
    captured = capsys.readouterr()
    assert "警告" in captured.out or "WARNING" in captured.out


def test_check_spreadsheet_token_usage_no_warning_under_threshold(capsys):
    """閾値以下では警告を出さない"""
    mock_service = MagicMock()
    mock_sheet = mock_service.spreadsheets.return_value.values.return_value
    # 少量データ
    mock_sheet.get.return_value.execute.return_value = {
        "values": [["test", "AI", "title", "url", "summary", "source"]] * 10
    }

    with patch.dict("os.environ", {"SPREADSHEET_ID": "test-sheet-id"}):
        from main import check_spreadsheet_token_usage
        result = check_spreadsheet_token_usage(mock_service)

    assert result is False
    captured = capsys.readouterr()
    assert "警告" not in captured.out
```

**Step 2: テストが失敗することを確認**

Run: `.venv/bin/python -m pytest tests/test_main.py::test_check_spreadsheet_token_usage_warns_over_threshold -v`

Expected: FAIL

**Step 3: 実装**

```python
TOKEN_WARNING_THRESHOLD = 80000


def check_spreadsheet_token_usage(service):
    spreadsheet_id = os.environ["SPREADSHEET_ID"]
    sheet_name = os.environ.get("SPREADSHEET_SHEET_NAME", SPREADSHEET_SHEET_NAME_DEFAULT)
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
```

**Step 4: テストがパスすることを確認**

Run: `.venv/bin/python -m pytest tests/test_main.py -v`

Expected: ALL passed

**Step 5: コミット**

```bash
git add main.py tests/test_main.py
git commit -m "Spreadsheetトークン使用量の警告機能を追加（check_spreadsheet_token_usage）"
```

---

### Task 5: main()にGoogle Docs書き出しとトークン警告を組み込む

**Files:**
- Modify: `main.py:179-217` (main関数)

**Step 1: main関数を更新**

```python
def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="News Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="ターミナル出力のみ（Google出力をスキップ）")
    args = parser.parse_args()

    if not args.dry_run:
        sheets_service = build_sheets_service()
        if already_curated_today(sheets_service):
            print(f"{date.today().isoformat()}のデータはすでに存在するためスキップします")
            # 既存データでもDocs書き出しは実行（手動追記分を反映するため）
            rows = read_today_from_spreadsheet(sheets_service)
            if rows and os.environ.get("GOOGLE_DOC_ID"):
                docs_service = build_docs_service()
                print("Google Docsに書き出し中...")
                write_to_google_docs(docs_service, rows)
            return

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

    check_spreadsheet_token_usage(sheets_service)

    print("Spreadsheetに追記中...")
    append_to_spreadsheet(sheets_service, curated)

    if os.environ.get("GOOGLE_DOC_ID"):
        docs_service = build_docs_service()
        rows = read_today_from_spreadsheet(sheets_service)
        print("Google Docsに書き出し中...")
        write_to_google_docs(docs_service, rows)


if __name__ == "__main__":
    main()
```

注意点:
- `GOOGLE_DOC_ID`が未設定ならDocs書き出しをスキップ（後方互換性）
- 当日分が既存でもDocs書き出しは実行する（手動追記分の反映）
- トークン警告はSpreadsheet追記の前に表示

**Step 2: テスト実行**

Run: `.venv/bin/python -m pytest tests/test_main.py -v`

Expected: ALL passed

**Step 3: コミット**

```bash
git add main.py
git commit -m "main()にGoogle Docs書き出しとトークン警告を組み込む"
```

---

### Task 6: READMEにGoogle Docs設定手順を追加

**Files:**
- Modify: `README.md`

**Step 1: クイックスタートにステップ6を追加**

ステップ5（Spreadsheet準備）の後に追加:

```markdown
### 6. Google Docs準備（任意）

NotebookLMのソースとして使うGoogle Docsを準備する。

1. Google Docsを新規作成
2. サービスアカウントのメールアドレスをDocsの共有に追加（編集者権限）
3. DocsのURLから`GOOGLE_DOC_ID`を取得（`/d/`と`/edit`の間の文字列）

`.env`に追記:

```
GOOGLE_DOC_ID=取得したDocsのID
```

設定しない場合、Spreadsheetへの追記のみ実行される。
```

**Step 2: mermaid図の「未実装」を削除**

```
C --> D[Google Docsに書き出し]
```

**Step 3: 仕組みセクションの説明を更新**

```markdown
4. **Google Docs書き出し** — Spreadsheetから今日分を読み取り、カテゴリ別に構造化してGoogle Docsに上書き
```

**Step 4: Spreadsheetローテーション手順を追加**

コマンドセクションの後に追加:

```markdown
## Spreadsheetのローテーション

NotebookLMのSpreadsheetソース制限は10万トークン。パイプライン実行時にトークン使用量が80%を超えると警告が表示される。

警告が出たら:

1. 新しいGoogle Spreadsheetを作成
2. 1行目にヘッダーを入力: `日付 | カテゴリ | タイトル | URL | 要約 | ソース`
3. サービスアカウントを共有に追加（編集者権限）
4. `.env`の`SPREADSHEET_ID`を新しいIDに差し替え

旧Spreadsheetはそのまま残るので、過去記事の検索に使える。
```

**Step 5: コミット**

```bash
git add README.md
git commit -m "READMEにGoogle Docs設定手順とSpreadsheetローテーション手順を追加"
```

---

### Task 7: 動作確認 + push

**Step 1: Google Docsを手動で作成し、サービスアカウントを共有に追加**

手動作業。

**Step 2: .envにGOOGLE_DOC_IDを設定**

手動作業。

**Step 3: パイプライン実行**

Run: `mise run pipeline`

Expected: RSS取得 → キュレーション → Spreadsheet追記 → Google Docs書き出し

**Step 4: 再実行して冪等性を確認**

Run: `mise run pipeline`

Expected: 「すでに存在するためスキップします」→ Google Docs書き出しは実行される

**Step 5: push**

```bash
git push origin main
```
