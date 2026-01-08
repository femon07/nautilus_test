"""
合成データでの純粋なバックテスト実行（比較用）
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.engine import BacktestEngineConfig
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.enums import OmsType
from nautilus_trader.model.identifiers import TraderId
from nautilus_trader.model.objects import Money
from nautilus_trader.persistence.wranglers import BarDataWrangler
from nautilus_trader.test_kit.providers import TestInstrumentProvider
from nautilus_trader.backtest.models import FillModel
from nautilus_trader.model.data import BarType as BarTypeClass
from nautilus_trader.persistence.wranglers import QuoteTickDataWrangler

from config import BacktestConfig, StrategyConfig
from strategies.mean_reversion import MeanReversionStrategy, MeanReversionConfig
from utils.data_loader import generate_synthetic_ohlcv

def main():
    bt_config = BacktestConfig()
    strat_config = StrategyConfig()
    
    # 1. 合成データ生成 (2023年1月)
    # 実データの開始価格にあわせる (約 1.07)
    df = generate_synthetic_ohlcv(
        start_date="2023-01-01",
        end_date="2023-01-31",
        initial_price=1.0700,
        volatility=0.0008, 
        trend=0.0
    )
    
    engine_config = BacktestEngineConfig(trader_id=TraderId("SYNTHETIC-TESTER"))
    engine = BacktestEngine(config=engine_config)
    
    fill_model = FillModel(prob_fill_on_limit=1.0, prob_fill_on_stop=1.0, prob_slippage=0.0)
    engine.add_venue(
        venue=Venue("SIM"),
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        base_currency=USD,
        starting_balances=[Money(bt_config.initial_balance, USD)],
        fill_model=fill_model,
    )
    
    eur_usd = TestInstrumentProvider.default_fx_ccy("EUR/USD", venue=Venue("SIM"))
    engine.add_instrument(eur_usd)
    
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.set_index('timestamp')
    
    bar_type_str = f"{eur_usd.id}-1-MINUTE-MID-EXTERNAL"
    bar_type_obj = BarTypeClass.from_str(bar_type_str)
    
    wrangler = BarDataWrangler(bar_type=bar_type_obj, instrument=eur_usd)
    bars = wrangler.process(data=df, ts_init_delta=1_000_000)
    engine.add_data(bars)
    
    quote_df = df.copy()
    quote_df['bid'] = df['close'] - 0.00005
    quote_df['ask'] = df['close'] + 0.00005
    quote_df['bid_size'] = 1_000_000
    quote_df['ask_size'] = 1_000_000
    
    quote_wrangler = QuoteTickDataWrangler(instrument=eur_usd)
    ticks = quote_wrangler.process(quote_df)
    engine.add_data(ticks)
    
    strategy_config = MeanReversionConfig(
        instrument_id=str(eur_usd.id),
        bar_type=bar_type_str,
        bb_period=strat_config.bb_period,
        bb_std_dev=strat_config.bb_std_dev,
        rsi_period=strat_config.rsi_period,
        rsi_oversold=strat_config.rsi_oversold,
        rsi_overbought=strat_config.rsi_overbought,
        position_size=float(strat_config.position_size),
        stop_loss_pips=strat_config.stop_loss_pips,
        take_profit_pips=strat_config.take_profit_pips,
    )
    
    strategy = MeanReversionStrategy(config=strategy_config)
    engine.add_strategy(strategy)
    
    print("Running Synthetic Backtest...")
    engine.run()
    
    report = engine.trader.generate_account_report(Venue("SIM"))
    orders = engine.trader.generate_order_fills_report()
    positions = engine.trader.generate_positions_report()
    
    print("\n--- Synthetic Test Results ---")
    print(f"PnL (total): {engine.trader.account(Venue('SIM')).balance(USD).amount - 100000.0}")
    print(f"Total Trades (Positions): {len(positions) if not positions.empty else 0}")
    if not orders.empty:
        # 簡易的な勝率計算
        wins = 0
        losses = 0
        # ポジションレポートからPnLを確認するのが確実
        # ここでは簡易表示に留める
        pass

if __name__ == "__main__":
    main()
