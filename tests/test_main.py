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
