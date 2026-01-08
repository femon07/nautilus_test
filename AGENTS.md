# Project Overview: NautilusTrader Sandbox

このプロジェクトは、[NautilusTrader](https://github.com/nautechsystems/nautilus_trader) を使用したアルゴリズム取引のバックテスト環境のサンドボックスです。

自然言語で生成するアウトプット(チャット,plan,walkthrough等)は**必ず**日本語で出力すること

## 📁 構造と機能

- **strategies/**: 取引戦略のコード。現在は平均回帰戦略 (`mean_reversion.py`) が実装されています。
- **backtest.py**: バックテストを実行するためのメインスクリプト。
- **utils/**: データ読み込みなどのユーティリティ。
- **data/**: ヒストリカルデータ（CSV）の保存先。Dockerfileの設定によりホストとボリューム共有されています。
- **Docker**: 環境構築にDockerを使用しています。`docker-compose.yml` でボリュームマウントや環境変数を管理しています。

## 🛠 技術スタック

- **Language**: Python 3.11
- **Platform**: NautilusTrader
- **Environment**: Docker / Docker Compose

## 🚀 現在の状況 (2026-01-08)

### 実データ導入完了 ✅
Dukascopyの実データを使用したバックテスト環境が構築されました。

#### 実装詳細
- **データソース**: Dukascopy（独自requestsベースのダウンローダー）
- **ファイル**: `utils/dukascopy_loader.py`
- **データ形式**: ティックデータ → 1分足にリサンプル
- **キャッシュ**: `data/EURUSD_M1.csv` に保存され、2回目以降は再利用

#### Docker利用時の注意点
プロジェクトはDockerコンテナ内で実行されることが前提です。
- 新しい依存関係（`requirements.txt`）を追加した際は、必ず `docker compose build` を実行してください。
- データは `./data` に永続化されます。

#### バックテスト実行
```bash
docker compose run --rm backtest python backtest.py
```
