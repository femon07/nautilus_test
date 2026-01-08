# NautilusTrader FX Backtest Sandbox

![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Docker](https://img.shields.io/badge/docker-supported-2496ED)
![License](https://img.shields.io/badge/license-MIT-green)

[NautilusTrader](https://github.com/nautechsystems/nautilus_trader) を使用した、FXアルゴリズム取引のためのバックテスト環境サンドボックスです。
実データ（Dukascopy）を用いたより実践的なバックテストが可能です。

## 特徴

*   **NautilusTraderベース**: 高速でイベント駆動型のバックテストエンジンを採用。
*   **実データ対応**: DukascopyからTickデータを直接ダウンロードし、1分足に変換して使用するローダーを実装済み。
*   **平均回帰戦略**: ボリンジャーバンド、RSI、トレンドフィルター(EMA)、ATRベースの動的SL/TPを組み合わせた戦略を実装。
*   **Docker対応**: 環境構築の手間を最小限に抑え、すぐにバックテストを実行可能。

## プロジェクト構造

```
.
├── backtest.py           # バックテスト実行のエントリーポイント
├── config.py             # 設定ファイル（期間、資金、戦略パラメータ等）
├── strategies/
│   └── mean_reversion.py # 平均回帰戦略の実装
├── utils/
│   └── dukascopy_loader.py # データダウンローダー
├── data/                 # 取得したデータ（.gitignore対象）
├── logs/                 # バックテスト結果・ログ（.gitignore対象）
└── docker-compose.yml    # Docker環境定義
```

## クイックスタート (Docker推奨)

### 1. 準備

Docker Desktop または Docker Engine がインストールされている必要があります。

### 2. コンテナのビルド

```bash
docker compose build
```

### 3. バックテストの実行

以下のコマンドを実行すると、データのダウンロード（初回のみ）からバックテストの実行、結果の表示まで自動で行われます。

```bash
docker compose run --rm backtest python backtest.py
```

実行が完了すると、コンソールに統計情報が表示され、`logs/` ディレクトリに注文履歴とポジション履歴のCSVが出力されます。

## 戦略について

### 平均回帰戦略 (Mean Reversion)

現在実装されている戦略は、典型的な逆張り戦略をベースにフィルタリングを加えたものです。

*   **エントリー条件**:
    *   **買い**: 価格がボリンジャーバンド(-2σ)を下抜け + RSIが売られすぎ(25) + 上昇トレンド(価格 > EMA200)
    *   **売り**: 価格がボリンジャーバンド(+2σ)を上抜け + RSIが買われすぎ(75) + 下降トレンド(価格 < EMA200)
*   **エグジット管理**:
    *   **SL/TP**: ATR(Average True Range)に基づき、ボラティリティに合わせて動的に設定。

## 設定の変更

パラメータの変更は `config.py` を編集することで行えます。

```python
@dataclass
class StrategyConfig:
    # トレンドフィルター期間
    ema_period: int = 200
    
    # リスク管理 (ATR倍率)
    sl_atr_mult: float = 2.0
    tp_atr_mult: float = 3.0
    # ...
```

## ローカル環境での実行 (開発者向け)

Python 3.12以上が必要です。

```bash
# 仮想環境の作成と有効化
python3 -m venv venv
source venv/bin/activate

# 依存関係のインストール
pip install -r requirements.txt

# 実行
python backtest.py
```
