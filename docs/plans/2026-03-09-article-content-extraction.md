# 記事本文抽出 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Google Docsに記事本文を載せてNotebookLMのラジオを充実させる

**Architecture:** キュレーション後の厳選記事URLからtrafilaturaで本文を取得し、Google Docs書き出し時に本文を含める。Spreadsheetは変更なし。本文が取れなかった記事はDocsに載せない。

**Tech Stack:** Python, trafilatura, Google Docs API

---

### Task 1: trafilaturaの追加

**Files:**
- Modify: `requirements.txt`

**Step 1: requirements.txtにtrafilaturaを追加**

```
trafilatura
```

requirements.txtの末尾に追加する。

**Step 2: インストール**

Run: `.venv/bin/pip install -r requirements.txt`
Expected: trafilaturaが正常にインストールされる

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "trafilaturaを依存に追加"
```

---

### Task 2: fetch_article_contents関数のテストを書く

**Files:**
- Modify: `tests/test_main.py`

**Step 1: 正常系テストを書く**

```python
def test_fetch_article_contents_returns_content():
    """URLから記事本文を取得して辞書で返す"""
    from main import fetch_article_contents

    with patch("main.trafilatura.fetch_url", return_value="<html><body><p>記事の本文です</p></body></html>") as mock_fetch, \
         patch("main.trafilatura.extract", return_value="記事の本文です") as mock_extract:
        result = fetch_article_contents(["https://example.com/article1"])

    assert result == {"https://example.com/article1": "記事の本文です"}
    mock_fetch.assert_called_once_with("https://example.com/article1")
```

**Step 2: 取得失敗時のテストを書く**

```python
def test_fetch_article_contents_skips_failed_urls():
    """本文取得に失敗したURLはスキップする"""
    from main import fetch_article_contents

    with patch("main.trafilatura.fetch_url", return_value=None):
        result = fetch_article_contents(["https://example.com/fail"])

    assert result == {}


def test_fetch_article_contents_skips_empty_extract():
    """extractがNoneを返した場合はスキップする"""
    from main import fetch_article_contents

    with patch("main.trafilatura.fetch_url", return_value="<html></html>"), \
         patch("main.trafilatura.extract", return_value=None):
        result = fetch_article_contents(["https://example.com/empty"])

    assert result == {}
```

**Step 3: 複数URL混在テストを書く**

```python
def test_fetch_article_contents_mixed_results():
    """成功と失敗が混在する場合、成功分だけ返す"""
    from main import fetch_article_contents

    def mock_fetch(url):
        if "good" in url:
            return "<html><body><p>本文</p></body></html>"
        return None

    with patch("main.trafilatura.fetch_url", side_effect=mock_fetch), \
         patch("main.trafilatura.extract", return_value="本文"):
        result = fetch_article_contents([
            "https://example.com/good",
            "https://example.com/bad",
        ])

    assert len(result) == 1
    assert "https://example.com/good" in result
```

**Step 4: テストが失敗することを確認**

Run: `.venv/bin/python -m pytest tests/test_main.py -v -k "fetch_article_contents"`
Expected: FAIL（fetch_article_contentsが未定義）

**Step 5: Commit**

```bash
git add tests/test_main.py
git commit -m "fetch_article_contentsのテストを追加"
```

---

### Task 3: fetch_article_contents関数を実装する

**Files:**
- Modify: `main.py`

**Step 1: importにtrafilaturaを追加**

main.pyの先頭のimportブロックに追加:

```python
import trafilatura
```

**Step 2: fetch_article_contents関数を実装**

`write_to_google_docs`関数の前あたりに配置する:

```python
def fetch_article_contents(urls):
    contents = {}
    for url in urls:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            print(f"[Content] 取得失敗: {url}")
            continue
        text = trafilatura.extract(downloaded)
        if not text:
            print(f"[Content] 本文抽出失敗: {url}")
            continue
        contents[url] = text
    return contents
```

**Step 3: テストが通ることを確認**

Run: `.venv/bin/python -m pytest tests/test_main.py -v -k "fetch_article_contents"`
Expected: 4件全てPASS

**Step 4: Commit**

```bash
git add main.py
git commit -m "fetch_article_contents関数を実装"
```

---

### Task 4: write_to_google_docsのテストを更新する

**Files:**
- Modify: `tests/test_main.py`

**Step 1: 既存テストにcontents引数を追加**

`test_write_to_google_docs_formats_by_category`を修正。contents引数を追加し、本文がある記事のみ出力されることを確認する:

```python
def test_write_to_google_docs_formats_by_category():
    """本文がある記事のみカテゴリ別に構造化してDocsに書き出す"""
    today = date.today().isoformat()

    rows = [
        [today, "AI/LLM", "AI記事1", "https://example.com/1", "AI要約1", "Zenn"],
        [today, "AI/LLM", "AI記事2", "https://example.com/2", "AI要約2", "HN"],
        [today, "DevTools", "ツール記事", "https://example.com/3", "ツール要約", "Zenn"],
    ]

    contents = {
        "https://example.com/1": "AI記事1の本文です",
        "https://example.com/3": "ツール記事の本文です",
    }

    mock_docs_service = MagicMock()
    mock_docs_service.documents.return_value.get.return_value.execute.return_value = {
        "body": {"content": [{"endIndex": 1}]}
    }

    with patch.dict("os.environ", {"GOOGLE_DOC_ID": "test-doc-id"}):
        from main import write_to_google_docs
        write_to_google_docs(mock_docs_service, rows, contents)

    mock_docs_service.documents.return_value.batchUpdate.assert_called()
    call_args = mock_docs_service.documents.return_value.batchUpdate.call_args
    body = call_args[1]["body"] if "body" in call_args[1] else call_args.kwargs["body"]
    requests = body["requests"]

    insert_texts = [r["insertText"]["text"] for r in requests if "insertText" in r]
    full_text = "".join(insert_texts)
    # 本文がある記事は載る
    assert "AI記事1" in full_text
    assert "AI記事1の本文です" in full_text
    assert "ツール記事" in full_text
    assert "ツール記事の本文です" in full_text
    # 本文がないAI記事2は載らない
    assert "AI記事2" not in full_text
    # 要約は載らない
    assert "AI要約1" not in full_text
```

**Step 2: 空rows テストも更新**

`test_write_to_google_docs_skips_when_no_rows`を更新:

```python
def test_write_to_google_docs_skips_when_no_rows():
    """行がない場合はAPI呼び出しをスキップする"""
    mock_docs_service = MagicMock()

    with patch.dict("os.environ", {"GOOGLE_DOC_ID": "test-doc-id"}):
        from main import write_to_google_docs
        write_to_google_docs(mock_docs_service, [], {})

    mock_docs_service.documents.return_value.batchUpdate.assert_not_called()
```

**Step 3: 本文が全て取得失敗のテストを追加**

```python
def test_write_to_google_docs_skips_when_no_contents():
    """本文が1件も取れなかった場合はAPI呼び出しをスキップする"""
    today = date.today().isoformat()
    rows = [
        [today, "AI/LLM", "記事1", "https://example.com/1", "要約1", "Zenn"],
    ]

    mock_docs_service = MagicMock()

    with patch.dict("os.environ", {"GOOGLE_DOC_ID": "test-doc-id"}):
        from main import write_to_google_docs
        write_to_google_docs(mock_docs_service, rows, {})

    mock_docs_service.documents.return_value.batchUpdate.assert_not_called()
```

**Step 4: テストが失敗することを確認**

Run: `.venv/bin/python -m pytest tests/test_main.py -v -k "write_to_google_docs"`
Expected: FAIL（write_to_google_docsのシグネチャが変わっていないため）

**Step 5: Commit**

```bash
git add tests/test_main.py
git commit -m "write_to_google_docsのテストを本文対応に更新"
```

---

### Task 5: write_to_google_docs関数を変更する

**Files:**
- Modify: `main.py`

**Step 1: 関数シグネチャを変更しロジックを書き換える**

```python
def write_to_google_docs(docs_service, rows, contents):
    if not rows:
        return

    # 本文がある記事だけフィルタ
    rows_with_content = [row for row in rows if len(row) > 3 and row[3] in contents]
    if not rows_with_content:
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
    for row in rows_with_content:
        category = row[1] if len(row) > 1 else "その他"
        categories[category].append(row)

    # テキスト生成
    today = rows_with_content[0][0] if rows_with_content else date.today().isoformat()
    lines = [f"{today} 技術ニュース\n\n"]
    for category, articles in categories.items():
        lines.append(f"## {category}\n\n")
        for a in articles:
            title = a[2] if len(a) > 2 else ""
            url = a[3] if len(a) > 3 else ""
            content = contents.get(url, "")
            lines.append(f"- {title}\n")
            if url:
                lines.append(f"  URL: {url}\n")
            if content:
                lines.append(f"  {content}\n")
            lines.append("\n")

    text = "".join(lines)
    requests.append({"insertText": {"location": {"index": 1}, "text": text}})

    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": requests},
    ).execute()
```

**Step 2: テストが通ることを確認**

Run: `.venv/bin/python -m pytest tests/test_main.py -v -k "write_to_google_docs"`
Expected: 3件全てPASS

**Step 3: Commit**

```bash
git add main.py
git commit -m "write_to_google_docsを本文表示に対応"
```

---

### Task 6: _write_docs_if_configuredとmainフローを変更する

**Files:**
- Modify: `main.py`

**Step 1: _write_docs_if_configuredを変更**

```python
def _write_docs_if_configured(all_rows):
    if not os.environ.get("GOOGLE_DOC_ID"):
        return
    rows = read_today_rows(all_rows)
    if not rows:
        return

    urls = [row[3] for row in rows if len(row) > 3]
    print("[Content] 記事本文を取得中...")
    contents = fetch_article_contents(urls)
    print(f"[Content] {len(contents)}/{len(urls)}件の本文を取得")

    if not contents:
        print("[Google Docs] 本文が取得できなかったため書き出しスキップ")
        return

    docs_service = build_docs_service()
    print("[Google Docs] 書き出し中...")
    write_to_google_docs(docs_service, rows, contents)
    print(f"[Google Docs] {len(contents)}件書き出しました")
```

mainフローは変更不要（_write_docs_if_configuredを呼ぶだけなので）。

**Step 2: 全テストが通ることを確認**

Run: `.venv/bin/python -m pytest tests/test_main.py -v`
Expected: 全てPASS

**Step 3: Commit**

```bash
git add main.py
git commit -m "パイプラインに記事本文取得ステップを組み込み"
```

---

### Task 7: 結合テスト（dry-runで動作確認）

**Step 1: dry-runで既存機能が壊れていないことを確認**

Run: `.venv/bin/python main.py --dry-run`
Expected: 今まで通りキュレーション結果がターミナルに出力される

**Step 2: 全テスト再実行**

Run: `.venv/bin/python -m pytest tests/test_main.py -v`
Expected: 全てPASS
