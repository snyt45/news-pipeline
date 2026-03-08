.PHONY: setup test run dry-run

setup: ## venv作成と依存インストール
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

test: ## テスト実行
	.venv/bin/python -m pytest tests/ -v

run: ## パイプライン実行
	.venv/bin/python main.py

dry-run: ## ターミナル出力のみ（Google出力スキップ）
	.venv/bin/python main.py --dry-run

help: ## コマンド一覧を表示
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'
