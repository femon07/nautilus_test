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
    rsi_oversold: float = 25.0   # 厳格化
    rsi_overbought: float = 75.0  # 厳格化
    
    # リスク管理
    position_size: float = 1000.0
    stop_loss_pips: float = 25.0   # ストップロス (pips)
    take_profit_pips: float = 30.0  # テイクプロフィット (pips)
    
    # 注文設定
    limit_order_offset_pips: float = 5.0


@dataclass
class BacktestConfig:
    """バックテスト実行設定"""
    
    # データ設定
    instrument_id: str = "EUR/USD.SIM"
    venue: str = "SIM"
    start_date: str = "2023-01-01"
    end_date: str = "2023-12-31"
    bar_type: str = "1-MINUTE-MID"
    
    # シミュレーション設定
    initial_balance: float = 100000.0
    currency: str = "USD"
    
    # ログ設定
    log_level: str = "INFO"
    output_directory: str = "./logs"
