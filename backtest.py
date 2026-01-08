"""
バックテスト実行スクリプト
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

from config import BacktestConfig, StrategyConfig
from strategies.mean_reversion import MeanReversionStrategy
from utils.data_loader import save_synthetic_data


def main():
    """バックテスト実行"""
    print("=" * 60)
    print("NautilusTrader バックテスト実行")
    print("=" * 60)
    
    # 設定読み込み
    bt_config = BacktestConfig()
    strat_config = StrategyConfig()
    
    # 1. 合成データ生成
    print("\n[1/4] 合成データ生成中...")
    data_path = save_synthetic_data(
        output_path="./data/EUR_USD_synthetic.csv",
        start_date=bt_config.start_date,
        end_date=bt_config.end_date,
        initial_price=1.1000,
        volatility=0.0015,
        trend=0.00001
    )
    
    # 2. バックテストエンジン設定
    print("\n[2/4] バックテストエンジン初期化中...")
    
    engine_config = BacktestEngineConfig(
        trader_id=TraderId("BACKTESTER-001"),
    )
    
    engine = BacktestEngine(config=engine_config)
    
    # 3. venueと口座の追加（楽器より先）
    print("\n[3/4] venueと口座設定中...")
    
    from nautilus_trader.backtest.models import FillModel
    
    # FillModelを設定（バーデータでの約定を有効化）
    fill_model = FillModel(
        prob_fill_on_limit=1.0,  # 指値注文の約定確率
        prob_fill_on_stop=1.0,   # ストップ注文の約定確率
        prob_slippage=0.0,       # スリッページ確率
    )
    
    engine.add_venue(
        venue=Venue("SIM"),
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        base_currency=USD,
        starting_balances=[Money(bt_config.initial_balance, USD)],
        fill_model=fill_model,
    )
    
    # 4. 楽器とデータ読み込み
    print("\n[4/4] データ読み込み中...")
    
    # EUR/USD楽器の作成
    EUR_USD = TestInstrumentProvider.default_fx_ccy("EUR/USD", venue=Venue("SIM"))
    engine.add_instrument(EUR_USD)
    
    # CSVデータの読み込み
    df = pd.read_csv(data_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.set_index('timestamp')
    
    # BarDataWranglerでNautilusデータに変換
    from nautilus_trader.model.data import BarType as BarTypeClass
    # NautilusTraderのbar_type形式: INSTRUMENT_ID-INTERVAL-PRICE_TYPE-AGGREGATION_SOURCE
    bar_type_str = f"{EUR_USD.id}-1-MINUTE-MID-EXTERNAL"
    bar_type_obj = BarTypeClass.from_str(bar_type_str)
    
    wrangler = BarDataWrangler(
        bar_type=bar_type_obj,
        instrument=EUR_USD,
    )
    
    bars = wrangler.process(
        data=df,
        ts_init_delta=1_000_000  # 1ms
    )
    
    engine.add_data(bars)
    print(f"✓ {len(bars):,}個のバーデータを読み込みました")
    
    # QuoteTickデータを生成（成行注文の約定に必要）
    from nautilus_trader.persistence.wranglers import QuoteTickDataWrangler
    
    # バーデータからQuoteTick用のDataFrameを作成
    quote_df = df.copy()
    quote_df['bid'] = df['close'] - 0.00005  # 0.5pips spread
    quote_df['ask'] = df['close'] + 0.00005
    quote_df['bid_size'] = 1_000_000
    quote_df['ask_size'] = 1_000_000
    
    quote_wrangler = QuoteTickDataWrangler(instrument=EUR_USD)
    ticks = quote_wrangler.process(quote_df)
    
    engine.add_data(ticks)
    print(f"✓ {len(ticks):,}個のQuoteTickを読み込みました")
    
    
    # 5. 戦略設定
    print("\n[5/6] 戦略設定中...")
    
    from strategies.mean_reversion import MeanReversionConfig
    
    # 戦略設定
    strategy_config = MeanReversionConfig(
        instrument_id=str(EUR_USD.id),
        bar_type=bar_type_str,
        bb_period=strat_config.bb_period,
        bb_std_dev=strat_config.bb_std_dev,
        rsi_period=strat_config.rsi_period,
        rsi_oversold=strat_config.rsi_oversold,
        rsi_overbought=strat_config.rsi_overbought,
        position_size=float(strat_config.position_size),
    )
    
    strategy = MeanReversionStrategy(config=strategy_config)
    engine.add_strategy(strategy)
    
    # 6. バックテスト実行
    print("\n" + "=" * 60)
    print("バックテスト開始...")
    print("=" * 60 + "\n")
    
    engine.run()
    
    # 7. 結果表示
    print("\n" + "=" * 60)
    print("バックテスト結果")
    print("=" * 60)
    
    # ログディレクトリ作成
    log_dir = Path(bt_config.output_directory)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # パフォーマンス統計
    account = engine.trader.generate_account_report(Venue("SIM"))
    print("\n### 口座サマリー ###")
    print(account)
    
    # 注文履歴
    orders = engine.trader.generate_order_fills_report()
    if not orders.empty:
        print(f"\n### 注文履歴 ({len(orders)}件) ###")
        print(orders)
        
        # CSV保存
        orders_path = log_dir / f"orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        orders.to_csv(orders_path, index=False)
        print(f"\n✓ 注文履歴を保存しました: {orders_path}")
    else:
        print("\n注文なし")
    
    # ポジション履歴
    positions = engine.trader.generate_positions_report()
    if not positions.empty:
        print(f"\n### ポジション履歴 ({len(positions)}件) ###")
        print(positions)
        
        positions_path = log_dir / f"positions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        positions.to_csv(positions_path, index=False)
        print(f"\n✓ ポジション履歴を保存しました: {positions_path}")
    else:
        print("\nポジションなし")
    
    print("\n" + "=" * 60)
    print("バックテスト完了")
    print("=" * 60)


if __name__ == "__main__":
    main()
