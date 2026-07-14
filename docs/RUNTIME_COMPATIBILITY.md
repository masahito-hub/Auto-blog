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

### Python 3.11+を必須とする理由
- `enum.StrEnum`: Python 3.11+
- `X | None` 型注釈: Python 3.10+
- Pydantic 2.x: Python 3.8+ (実質3.11推奨)
- pytest 8.x: Python 3.8+

## 依存関係（requirements.txt）

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
watchdog>=4.0.0
pyyaml>=6.0.1
markdown>=3.5.2
requests>=2.31.0
pydantic>=2.6.0
pydantic-settings>=2.1.0
Pillow>=10.2.0
pytest>=8.0.0
```

## Fail-Closed設計

全てのAPI呼び出しはfail-closed:
- **Slug重複チェック**: 200以外/timeout/複数返却→エラー
- **カテゴリ解決**: 完全一致1件のみ許可、0件/複数→エラー
- **画像アップロード**: path safety違反/symlink/..→エラー

## Queue Idempotency

- `wp_post_id`/`wp_url`をDB永続化
- POST成功直後に保存（ZIP移動より前）
- `wp_post_id`ありジョブは再POSTしない
- 同一file_pathのQUEUED/RUNNING/FAILEDは重複enqueue防止
