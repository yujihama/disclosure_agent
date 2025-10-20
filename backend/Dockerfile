FROM python:3.11-slim

WORKDIR /app

# 依存関係のインストールに必要なツールをインストール
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 依存関係をコピーしてインストール
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# アプリケーションコードをコピー
COPY . .

# ストレージディレクトリを作成
RUN mkdir -p storage/uploads storage/metadata

# ポート8000を公開
EXPOSE 8000

# デフォルトコマンド（docker-compose.ymlでオーバーライド）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

