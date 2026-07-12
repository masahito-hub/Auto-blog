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

## Fail-Closed設計

全てのAPI呼び出しはfail-closed:
- **Slug重複チェック**: 200以外/timeout/複数返却→エラー
- **カテゴリ解決**: 完全一致1件のみ許可、0件/複数→エラー
- **画像アップロード**: path safety違反/symlink/..→エラー
- **投稿作成**: 認証失敗/権限不足/rate limit→エラー

## Queue Idempotency

- `wp_post_id`/`wp_url`をDB永続化
- POST成功直後に保存
- `wp_post_id`ありジョブは再POSTしない

## 依存関係

```
requests>=2.28.0
python-frontmatter>=1.0.0
pyyaml>=6.0
```
