# Deployment Guide - XServer VPS (Ubuntu 22.04)

**環境:** XServer VPS + Ubuntu 22.04  
**対象:** 初回デプロイ  
**所要時間:** 約30分

---

## 📋 前提条件チェック

- ✅ XServer VPS (Ubuntu 22.04) 契約済み
- ✅ WordPress 稼働中
- ✅ WordPress 管理画面アクセス可能
- ✅ Slack Webhook URL 取得済み
- ✅ SSH接続情報あり

---

## ステップ1: VPSへのSSH接続

```bash
# XServer VPSに接続
ssh root@your-vps-ip

# または鍵認証の場合
ssh -i ~/.ssh/your-key.pem root@your-vps-ip
```

**初回接続時の注意:**
- パスワード変更を求められた場合は、強力なパスワードに変更
- `yes` で接続を続行

---

## ステップ2: システムアップデート

```bash
# パッケージリスト更新
sudo apt update

# インストール済みパッケージをアップグレード
sudo apt upgrade -y

# 再起動が必要か確認
ls /var/run/reboot-required

# 必要な場合は再起動
# sudo reboot
```

---

## ステップ3: Python 3.11 のインストール

Ubuntu 22.04 はデフォルトで Python 3.10 なので、3.11 をインストールします。

```bash
# deadsnakes PPA追加
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update

# Python 3.11 インストール
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# バージョン確認
python3.11 --version
# 出力例: Python 3.11.x
```

---

## ステップ4: 必要なパッケージのインストール

```bash
# 開発ツール
sudo apt install -y git build-essential libssl-dev libffi-dev

# pip をインストール
sudo apt install -y python3-pip

# その他のツール
sudo apt install -y curl jq unzip
```

---

## ステップ5: 専用ユーザーの作成

セキュリティのため、root ではなく専用ユーザーで実行します。

```bash
# blog-pipeline 用のユーザー作成
sudo useradd -r -m -d /opt/blog-pipeline -s /bin/bash blogpipe

# パスワードは設定しない（鍵認証のみ）
sudo passwd -l blogpipe

# sudo 権限は不要（アプリケーション実行のみ）
```

---

## ステップ6: Blog Pipeline のセットアップ

```bash
# blog-pipeline ユーザーに切り替え
sudo su - blogpipe

# ホームディレクトリに移動（既にいるはず）
cd /opt/blog-pipeline

# リポジトリをクローン
git clone https://github.com/masahito-hub/Auto-blog.git .

# 仮想環境を作成
python3.11 -m venv venv

# 仮想環境を有効化
source venv/bin/activate

# 依存パッケージをインストール
pip install --upgrade pip
pip install -r requirements.txt

# インストール確認
pip list
```

**期待される出力:**
```
Package              Version
-------------------- -------
fastapi              0.109.x
uvicorn              0.27.x
watchdog             4.0.x
...(その他のパッケージ)
```

---

## ステップ7: 環境変数の設定

```bash
# まだ blogpipe ユーザーでログイン中

# .env ファイルを作成
cp .env.example .env

# エディタで編集（nano が簡単）
nano .env
```

**編集内容:**

```bash
# WordPress設定
WP_BASE_URL=https://your-wordpress-site.com  # あなたのWordPress URL
WP_USER=your_username                        # WordPress ユーザー名
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx         # Application Password（後で取得）

# Slack通知（オプション）
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ

# その他はデフォルトでOK
IMAGES_PROVIDER=none
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
LOG_LEVEL=INFO
```

**保存方法（nano）:**
- `Ctrl + O` → Enter（保存）
- `Ctrl + X`（終了）

**ファイル権限を設定:**

```bash
chmod 600 .env
ls -la .env
# 出力: -rw------- 1 blogpipe blogpipe ... .env
```

---

## ステップ8: WordPress Application Password の取得

**WordPress側の操作:**

1. WordPress 管理画面にログイン
2. **ユーザー → プロフィール** に移動
3. 下にスクロールして **「アプリケーションパスワード」** セクションを探す
4. 「新しいアプリケーションパスワード名」に `Blog Pipeline` と入力
5. **「新しいアプリケーションパスワードを追加」** をクリック
6. 表示されたパスワードをコピー（例: `AbC1 2dEf 3GhI 4jKl mNoP 5qRs`）

**⚠️ 重要:** このパスワードは一度しか表示されません！

**VPS側で .env に追加:**

```bash
nano .env

# WP_APP_PASSWORD の行を更新
WP_APP_PASSWORD=AbC1 2dEf 3GhI 4jKl mNoP 5qRs

# 保存して終了
```

---

## ステップ9: 設定の検証

```bash
# まだ仮想環境内にいることを確認
# (venv) が表示されているはず

# 設定チェックスクリプトを実行
python scripts/check_config.py
```

**期待される出力:**

```
🔍 Blog Pipeline Configuration Check

==================================================
✅ Configuration loaded successfully
✅ WordPress URL is valid: https://your-site.com
✅ WordPress REST API is accessible
✅ WordPress authentication successful
✅ Can create posts (permissions OK)
✅ Can upload media (permissions OK)
✅ All directories are writable
✅ Slack webhook is configured (optional)

==================================================

🎉 All checks passed! Your environment is ready.
```

**エラーが出た場合:**

| エラー | 原因 | 解決方法 |
|--------|------|----------|
| WordPress REST API is not accessible | URL が間違っている | `.env` の `WP_BASE_URL` を確認 |
| Authentication failed | Application Password が間違い | WordPress で再発行 |
| Permission denied | ユーザー権限不足 | WordPress でユーザーを「編集者」または「管理者」に |

---

## ステップ10: systemd サービスの設定

**blogpipe ユーザーを一旦抜ける:**

```bash
exit  # blogpipe ユーザーから抜ける
# rootユーザーに戻る
```

**サービスファイルを編集:**

```bash
# サービスファイルをコピー
sudo cp /opt/blog-pipeline/systemd/blog-pipeline.service /etc/systemd/system/

# 念のため内容を確認・編集
sudo nano /etc/systemd/system/blog-pipeline.service
```

**確認すべき項目:**

```ini
[Service]
User=blogpipe                              # ユーザー名が正しいか
Group=blogpipe                             # グループ名が正しいか
WorkingDirectory=/opt/blog-pipeline        # パスが正しいか
EnvironmentFile=/opt/blog-pipeline/.env    # .envのパスが正しいか
ExecStart=/opt/blog-pipeline/venv/bin/python -m app.server  # python のパスが正しいか
```

**サービスを有効化・起動:**

```bash
# systemd にサービスを認識させる
sudo systemctl daemon-reload

# 自動起動を有効化
sudo systemctl enable blog-pipeline

# サービスを開始
sudo systemctl start blog-pipeline

# 状態を確認
sudo systemctl status blog-pipeline
```

**期待される出力:**

```
● blog-pipeline.service - Blog Pipeline - Auto WordPress Publishing
     Loaded: loaded (/etc/systemd/system/blog-pipeline.service; enabled)
     Active: active (running) since ...
   Main PID: 12345 (python)
      Tasks: 3 (limit: 1234)
     Memory: 50.0M
        CPU: 2s
     CGroup: /system.slice/blog-pipeline.service
             └─12345 /opt/blog-pipeline/venv/bin/python -m app.server

... [INFO] Starting Blog Pipeline v0.1.0
... [INFO] Configuration validated successfully
... [INFO] Database initialized
... [INFO] Background threads started
... [INFO] Monitoring inbox: /opt/blog-pipeline/var/inbox
... [INFO] API server starting on 0.0.0.0:8000
```

**Active: active (running)** と表示されていればOK！

---

## ステップ11: ファイアウォール設定（重要）

XServer VPS はデフォルトでファイアウォールが有効なことがあります。

```bash
# ファイアウォール状態を確認
sudo ufw status

# 無効なら有効化（SSH を許可してから）
sudo ufw allow 22/tcp
sudo ufw allow 8000/tcp  # Blog Pipeline API用（外部公開する場合のみ）
sudo ufw enable

# 状態確認
sudo ufw status verbose
```

**⚠️ 注意:**
- API ポート (8000) は**社内アクセスのみ**に制限することを推奨
- SSH トンネル経由でアクセスするのが安全

**SSH トンネルでアクセス（推奨）:**

ローカルPCから：

```bash
# ローカルの 8000 番ポートを VPS の 8000 番に転送
ssh -L 8000:localhost:8000 root@your-vps-ip

# 別のターミナルで
curl http://localhost:8000/health
```

---

## ステップ12: 初回テスト

### テスト用ZIPファイルを作成

**ローカルPCで作成:**

```bash
# テストディレクトリ作成
mkdir test-post
cd test-post

# post.md を作成
cat > post.md << 'EOF'
---
title: "テスト投稿 - Blog Pipeline"
slug: "test-post-from-pipeline"
description: "これはBlog Pipelineからの自動投稿テストです"
status: "draft"
---

# はじめに

これは **Blog Pipeline** からの自動投稿テストです。

## 機能確認

- Markdown → HTML 変換
- WordPress 下書き作成
- 自動処理

正常に動作していれば、この記事がWordPressの下書きに表示されます。
EOF

# ZIPファイルを作成
cd ..
zip -r test-post.zip test-post/
```

### VPSにアップロード

```bash
# ローカルPCから VPS へ
scp test-post.zip root@your-vps-ip:/tmp/

# VPSにSSH接続
ssh root@your-vps-ip

# inbox に移動
sudo mv /tmp/test-post.zip /opt/blog-pipeline/var/inbox/
sudo chown blogpipe:blogpipe /opt/blog-pipeline/var/inbox/test-post.zip
```

### ログを監視

```bash
# リアルタイムでログを表示
sudo journalctl -u blog-pipeline -f
```

**期待されるログ:**

```
[INFO] Detected new ZIP file: test-post.zip
[INFO] File stable, validating: test-post.zip
[INFO] Enqueued job 1 for test-post.zip (2.3KB)
[INFO] Processing job 1: test-post.zip
[INFO] Extracted test-post.zip to test-post
[INFO] Job 1: Parsed post 'test-post-from-pipeline'
[INFO] Connected to WordPress as: YourUsername
[INFO] Created post → ID: 123 | https://your-site.com/test-post-from-pipeline/
[INFO] Job 1: Moved to published: test-post.zip
[INFO] Job 1: Completed successfully
```

### WordPress で確認

1. WordPress 管理画面にログイン
2. **投稿 → 下書き** に移動
3. 「テスト投稿 - Blog Pipeline」が表示されていればOK！

### API で確認

```bash
# ヘルスチェック
curl http://localhost:8000/health
# 出力: {"ok":true,"version":"0.1.0"}

# ジョブステータス
curl http://localhost:8000/status | jq
```

---

## ステップ13: Slack通知の確認

テスト投稿が成功した場合、Slackに通知が届いているはずです。

**通知内容:**

```
✅ [test-post-from-pipeline] Draft created: https://your-site.com/...
```

届いていない場合：

```bash
# Webhook URL が正しいか確認
sudo -u blogpipe cat /opt/blog-pipeline/.env | grep SLACK

# 手動でテスト送信
curl -X POST YOUR_SLACK_WEBHOOK_URL \
  -H 'Content-Type: application/json' \
  -d '{"text":"Blog Pipeline テスト通知"}'
```

---

## トラブルシューティング

### サービスが起動しない

```bash
# 詳細ログを確認
sudo journalctl -u blog-pipeline -n 50 --no-pager

# 手動で起動してエラー確認
sudo -u blogpipe /opt/blog-pipeline/venv/bin/python -m app.server
```

**よくあるエラー:**

| エラーメッセージ | 原因 | 解決方法 |
|------------------|------|----------|
| `Permission denied: '/opt/blog-pipeline/.env'` | ファイル権限 | `sudo chown blogpipe:blogpipe .env` |
| `ModuleNotFoundError: No module named 'fastapi'` | venv未使用 | サービスファイルの `ExecStart` を確認 |
| `Configuration validation failed` | .env 設定ミス | `python scripts/check_config.py` で確認 |

### ZIPが処理されない

```bash
# inbox ディレクトリを確認
ls -la /opt/blog-pipeline/var/inbox/

# 権限を確認
stat /opt/blog-pipeline/var/inbox/

# Watcher スレッドのログを確認
sudo journalctl -u blog-pipeline | grep -i watcher
```

### WordPressへのアップロードが失敗する

```bash
# WordPress への接続テスト
curl -I https://your-wordpress-site.com/wp-json/

# 認証テスト
curl -u "username:app_password" \
  https://your-wordpress-site.com/wp-json/wp/v2/posts
```

---

## セキュリティチェックリスト

- [ ] `.env` ファイルのパーミッションが 600
- [ ] blogpipe ユーザーはパスワードログイン無効
- [ ] API ポート (8000) は外部公開しない（SSH トンネル推奨）
- [ ] ファイアウォール (ufw) が有効
- [ ] 定期的な `apt upgrade` を設定（unattended-upgrades）
- [ ] SSH 鍵認証のみ許可（パスワード認証無効化）

**SSH セキュリティ強化（推奨）:**

```bash
sudo nano /etc/ssh/sshd_config

# 以下を設定
PasswordAuthentication no
PermitRootLogin prohibit-password
Port 22  # または別のポート番号に変更

# 保存後、SSHを再起動
sudo systemctl restart sshd
```

---

## 運用開始

### 日常的な操作

```bash
# サービス状態確認
sudo systemctl status blog-pipeline

# ログ確認
sudo journalctl -u blog-pipeline -f

# ジョブ統計
curl http://localhost:8000/status | jq '.stats'

# サービス再起動（設定変更後など）
sudo systemctl restart blog-pipeline
```

### ZIPファイルの投入方法

**方法1: scpコマンド（推奨）**

```bash
# ローカルPCから
scp your-post.zip root@your-vps-ip:/tmp/
ssh root@your-vps-ip "sudo mv /tmp/your-post.zip /opt/blog-pipeline/var/inbox/ && sudo chown blogpipe:blogpipe /opt/blog-pipeline/var/inbox/your-post.zip"
```

**方法2: SFTP クライアント**

FileZilla や WinSCP で `/opt/blog-pipeline/var/inbox/` に直接アップロード

**方法3: 自動化（将来）**

ローカルでスクリプト化：

```bash
#!/bin/bash
for zip in *.zip; do
  scp "$zip" root@your-vps-ip:/tmp/
  ssh root@your-vps-ip "sudo mv /tmp/$zip /opt/blog-pipeline/var/inbox/"
done
```

---

## 定期メンテナンス

### 週次タスク

```bash
# ログ確認
sudo journalctl -u blog-pipeline --since "7 days ago" | grep -i error

# ディスク使用量確認
du -sh /opt/blog-pipeline/var/*

# 古いジョブのクリーンアップ（30日以上前）
sudo -u blogpipe bash -c 'cd /opt/blog-pipeline && source venv/bin/activate && python -c "from app.queue import cleanup_old_jobs; cleanup_old_jobs(30)"'
```

### 月次タスク

```bash
# システムアップデート
sudo apt update && sudo apt upgrade -y

# 依存パッケージの更新
sudo -u blogpipe bash -c 'cd /opt/blog-pipeline && source venv/bin/activate && pip install --upgrade -r requirements.txt'

# サービス再起動
sudo systemctl restart blog-pipeline
```

---

## 次のステップ

✅ デプロイ完了！

次は：

1. **本番記事の投入**
   - ケト: 30記事
   - 眠活: 30記事
   - 浮気調査: 30記事

2. **監視とメトリクス収集**
   - Search Console でインデックス状況
   - GA4 でトラフィック
   - 収益発生の確認

3. **改善検討**
   - カテゴリ/タグの自動作成
   - 画像生成の有効化
   - 自動公開機能

---

## サポート

問題が発生した場合：

1. **ログを確認**: `sudo journalctl -u blog-pipeline -n 100`
2. **ドキュメント参照**: `/opt/blog-pipeline/docs/`
3. **GitHub Issues**: https://github.com/masahito-hub/Auto-blog/issues

---

**🎉 デプロイ完了おめでとうございます！**
