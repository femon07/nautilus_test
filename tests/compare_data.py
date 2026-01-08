"""
合成データ vs 実データ 比較用バックテスト
"""
import pandas as pd
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


def run_backtest(df, data_type: str):
    """バックテスト実行"""
    print(f"\n{'='*60}")
    print(f"バックテスト: {data_type}")
    print(f"{'='*60}")
    
    bt_config = BacktestConfig()
    strat_config = StrategyConfig()
    
    engine_config = BacktestEngineConfig(
        trader_id=TraderId("BACKTESTER-001"),
    )
    engine = BacktestEngine(config=engine_config)
    
    fill_model = FillModel(
        prob_fill_on_limit=1.0,
        prob_fill_on_stop=1.0,
        prob_slippage=0.0,
    )
    
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
    
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.set_index('timestamp')
    
    bar_type_str = f"{eur_usd.id}-1-MINUTE-MID-EXTERNAL"
    bar_type_obj = BarTypeClass.from_str(bar_type_str)
    
    wrangler = BarDataWrangler(
        bar_type=bar_type_obj,
        instrument=eur_usd,
    )
    
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
    
    engine.run()
    
    # 結果抽出
    orders = engine.trader.generate_order_fills_report()
    positions = engine.trader.generate_positions_report()
    
    return {
        'data_type': data_type,
        'bars': len(bars),
        'orders': len(orders),
        'positions': len(positions) if not positions.empty else 0,
    }


def main():
    bt_config = BacktestConfig()
    
    print("=" * 60)
    print("合成データ vs 実データ 比較")
    print("=" * 60)
    print(f"期間: {bt_config.start_date} - {bt_config.end_date}")
    
    # 1. 合成データ生成（同じ期間）
    print("\n[1/2] 合成データ生成...")
    synthetic_df = generate_synthetic_ohlcv(
        start_date=bt_config.start_date,
        end_date=bt_config.end_date,
        initial_price=1.0700,  # 2023年1月のEUR/USD実データに近い値
        volatility=0.0008,
        trend=0.0
    )
    
    # 2. 実データ読み込み
    print("[2/2] 実データ読み込み...")
    real_df = pd.read_csv("./data/EURUSD_M1.csv")
    
    print(f"\n合成データ: {len(synthetic_df):,}行")
    print(f"実データ: {len(real_df):,}行")
    
    # バックテスト実行
    synthetic_result = run_backtest(synthetic_df, "合成データ")
    real_result = run_backtest(real_df, "実データ (Dukascopy)")
    
    # 比較表示
    print("\n" + "=" * 60)
    print("比較結果")
    print("=" * 60)
    print(f"{'指標':<20} {'合成データ':>15} {'実データ':>15}")
    print("-" * 50)
    print(f"{'バー数':<20} {synthetic_result['bars']:>15,} {real_result['bars']:>15,}")
    print(f"{'注文数':<20} {synthetic_result['orders']:>15} {real_result['orders']:>15}")
    print(f"{'ポジション数':<20} {synthetic_result['positions']:>15} {real_result['positions']:>15}")


if __name__ == "__main__":
    main()
