FROM node:18-alpine

WORKDIR /app

# 依存関係をコピーしてインストール
COPY package*.json ./
RUN npm ci

# アプリケーションコードをコピー
COPY . .

# ポート9000を公開
EXPOSE 9000

# デフォルトコマンド（docker-compose.ymlでオーバーライド）
CMD ["npm", "run", "dev"]

