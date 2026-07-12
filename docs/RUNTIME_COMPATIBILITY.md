# Runtime Compatibility

## 実行環境構成（パターンA）

Auto-blogはVPS上で稼働し、WordPressにはREST API経由で接続します。

```
┌─────────────────────┐     REST API      ┌─────────────────────┐
│   SwingBot VPS      │ ───────────────── │   XServer           │
│   (Ubuntu 22.04)    │                   │   (WordPress)       │
│                     │                   │                     │
│   Python 3.11+      │                   │   PHP/MySQL         │
│   /opt/blog-pipeline│                   │   Python 3.6 (未使用)│
└─────────────────────┘                   └─────────────────────┘
```

## Python要件

| 環境 | バージョン | 用途 |
|------|-----------|------|
| VPS (実行環境) | Python 3.11+ | Auto-blog実行 |
| XServer | Python 3.6.8 | **使用しない** |

### 方針
- Python 3.11+を維持
- Python 3.6対応コードは作成しない
- XServerのPythonはAuto-blogの実行要件ではない

## 依存関係

```
# requirements.txt
requests>=2.28.0
python-frontmatter>=1.0.0
pyyaml>=6.0
```

## 確認済み互換性

- subprocess.run(capture_output=True): Python 3.7+
- f-strings: Python 3.6+
- typing hints: Python 3.9+ (full support)
- match-case: Python 3.10+ (使用しない)

## 備考

tokoroten-siteの`build_autoblog_package.py`は標準ライブラリのみで実装。
XServer (Python 3.6) での実行時は`capture_output`の互換性問題あり。
→ ZIP生成はVPS上で実行することを推奨。
