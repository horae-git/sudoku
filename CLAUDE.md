# Python 環境

- 使用 uv 管理 Python 環境
- 所有原始碼、註解與使用者可見文字使用繁體中文（由 tests/test_no_simplified_chinese.py 自動檢查；CI 見 .github/workflows/ci.yml）
- 測試：`uv run pytest -q`（全量）、`uv run pytest -m "not slow" -q`（快速集，壓力測試標 slow）
