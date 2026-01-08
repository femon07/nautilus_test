# マルチステージビルド: ビルダーステージ
FROM python:3.11-slim as builder

WORKDIR /build

# システム依存関係のインストール（Rustコンパイル用）
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Rustのインストール（NautilusTraderのビルドに必要）
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Python依存関係のインストール
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ==========================================
# ランタイムステージ
FROM python:3.11-slim

WORKDIR /app

# ビルダーからPythonパッケージをコピー
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 非rootユーザーの作成
RUN useradd -m -u 1000 trader && \
    chown -R trader:trader /app

# アプリケーションコードをコピー
COPY --chown=trader:trader . .

# 非rootユーザーに切り替え
USER trader

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import nautilus_trader; print('OK')" || exit 1

# デフォルトコマンド
CMD ["python", "backtest.py"]
