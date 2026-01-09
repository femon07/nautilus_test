"""
バックテスト設定と戦略パラメータ
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class StrategyConfig:
    """平均回帰戦略のパラメータ"""
    
    # ボリンジャーバンド設定
    bb_period: int = 20
    bb_std_dev: float = 2.0
    
    # RSI設定（厳格化: 35/65 → 25/75）
    rsi_period: int = 14
    rsi_oversold: float = 25.0
    rsi_overbought: float = 75.0
    
    # トレンドフィルター (EMA)
    ema_period: int = 200
    
    # リスク管理 (ATR Based)
    position_size: float = 1000.0
    atr_period: int = 14
    sl_atr_mult: float = 2.0
    tp_atr_mult: float = 3.0
    
    # 注文設定
    limit_order_offset_pips: float = 5.0


@dataclass
class BacktestConfig:
    """バックテスト実行設定"""
    
    # データ設定
    symbol: str = "EURUSD"
    instrument_id: str = "EUR/USD"
    venue: str = "SIM"
    start_date: str = "2023-01-01"
    end_date: str = "2023-02-01"  # 1ヶ月分 (排他的: 2/1は含まない)
    bar_type: str = "1-MINUTE-MID-EXTERNAL"
    
    # シミュレーション設定
    initial_balance: float = 100000.0
    currency: str = "USD"
    
    # ログ設定
    log_level: str = "INFO"
    output_directory: str = "./logs"
