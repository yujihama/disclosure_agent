FROM node:18-alpine

WORKDIR /app

# 依存関係をコピーしてインストール
COPY package*.json ./
RUN npm ci

# アプリケーションコードをコピー
COPY . .

# ポート3000を公開
EXPOSE 3000

# デフォルトコマンド（docker-compose.ymlでオーバーライド）
CMD ["npm", "run", "dev"]

