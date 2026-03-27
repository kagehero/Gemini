# Ubuntu VPS へのデプロイ（Geminni）

想定: **Ubuntu 22.04 / 24.04 LTS**、ドメイン例 `example.com`（実際の値に置き換えてください）。

## 1. サーバーに入れるもの

```bash
sudo apt update
sudo apt install -y nginx python3 python3-venv python3-pip git curl
```

**Node.js 20+**（公式バイナリまたは [NodeSource](https://github.com/nodesource/distributions)）。例:

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

## 2. アプリの配置

例: `/var/www/geminni`（所有者はデプロイ用ユーザー）。

```bash
sudo mkdir -p /var/www/geminni
sudo chown $USER:$USER /var/www/geminni
cd /var/www/geminni
git clone <YOUR_REPO_URL> .
# または scp / rsync で同期
```

### Python

```bash
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
```

### 環境変数

```bash
cp .env.example .env
nano .env   # TENANT_ID, CLIENT_SECRET, GEMINI_API_KEY, GRAPH_SEARCH_REGION, API_CORS_ORIGINS など
```

本番では **API の CORS** に **ブラウザが開く HTTPS のオリジン**を入れます（後述の Nginx の `server_name` と一致）。

例:

```env
API_CORS_ORIGINS=https://example.com
API_HOST=127.0.0.1
API_PORT=8000
```

### フロントのビルド

```bash
cd web
cp .env.local.example .env.local
nano .env.local
```

同一オリジンで Nginx が `/api` をバックエンドへ流す場合:

```env
NEXT_PUBLIC_API_URL=https://example.com
```

（ブラウザは `https://example.com/api/query` を叩く想定。下記 Nginx 参照。）

```bash
npm ci
npm run build
cd ..
```

### データの永続化

`data/`（SQLite・Chroma・トークンキャッシュ）を **リポジトリと同じディスク**に置き、デプロイで上書きしないよう注意してください。初回は `main.py index` などで生成されます。

## 3. 本番プロセス（systemd）

**開発用の `main.py api` は `reload=True` なので本番では使わない**でください。`uvicorn` を直接起動します。

### `/etc/systemd/system/geminni-api.service`

```ini
[Unit]
Description=Geminni FastAPI
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/geminni
EnvironmentFile=/var/www/geminni/.env
ExecStart=/var/www/geminni/.venv/bin/uvicorn api.app:app --host 127.0.0.1 --port 8000 --workers 2
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`User` / パスは環境に合わせて変更。`.env` の読み込みはアプリが `python-dotenv` で行うため、`EnvironmentFile` は必須ではありませんが、追加の OS レベル変数がある場合に便利です。

### `/etc/systemd/system/geminni-web.service`

```ini
[Unit]
Description=Geminni Next.js
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/geminni/web
Environment=NODE_ENV=production
EnvironmentFile=/var/www/geminni/web/.env.local
ExecStart=/usr/bin/npm run start
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`ExecStart` の `npm` パスは `which npm` で確認してください。

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now geminni-api geminni-web
sudo systemctl status geminni-api geminni-web
```

## 4. Nginx（HTTPS + リバースプロキシ）

### サイト設定例 `/etc/nginx/sites-available/geminni`

```nginx
server {
    listen 80;
    server_name example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    # Next.js
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # FastAPI（アプリは /api/...）
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
}
```

SSL 証明書（Let’s Encrypt）:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d example.com
```

```bash
sudo ln -s /etc/nginx/sites-available/geminni /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## 5. ファイアウォール

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

**8000 / 3000 は外向きに開けない**（Nginx 経由のみ）。

## 6. 動作確認

- `curl -s https://example.com/api/health`
- ブラウザで `https://example.com` を開き、質問を送信

## 7. デプロイ更新の流れ（例）

```bash
cd /var/www/geminni
git pull
.venv/bin/pip install -r requirements.txt
cd web && npm ci && npm run build && cd ..
sudo systemctl restart geminni-api geminni-web
```

## 8. 注意

- **シークレット**は Git に含めず、サーバの `.env` のみで管理。
- **長時間処理**（Graph / Gemini）はタイムアウトを Nginx / クライアント側で必要に応じて延長。
- トラフィックが増えたら **workers 数**・**サーバスペック**・**レート制限**を検討。
