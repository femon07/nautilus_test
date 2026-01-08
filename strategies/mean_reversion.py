"""
ボリンジャーバンド + RSI による平均回帰戦略
"""
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import TimeInForce
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.model.events import OrderFilled
from decimal import Decimal
import numpy as np


class MeanReversionConfig(StrategyConfig, frozen=True):
    """平均回帰戦略の設定"""
    instrument_id: str = "EUR/USD.SIM"
    bar_type: str = "EUR/USD.SIM-1-MINUTE-MID-EXTERNAL"
    bb_period: int = 20
    bb_std_dev: float = 2.0
    rsi_period: int = 14
    rsi_oversold: float = 35.0   # 緩和: 30 -> 35
    rsi_overbought: float = 65.0  # 緩和: 70 -> 65
    position_size: float = 1000.0  # FX最小取引サイズ


class BollingerBand:
    """シンプルなボリンジャーバンド計算"""
    
    def __init__(self, period: int = 20, std_dev: float = 2.0):
        self.period = period
        self.std_dev = std_dev
        self.prices = []
        self.upper = None
        self.middle = None
        self.lower = None
    
    def update(self, price: float):
        """価格を追加してバンドを更新"""
        self.prices.append(price)
        if len(self.prices) > self.period:
            self.prices.pop(0)
        
        if len(self.prices) >= self.period:
            self.middle = np.mean(self.prices)
            std = np.std(self.prices)
            self.upper = self.middle + (self.std_dev * std)
            self.lower = self.middle - (self.std_dev * std)


class SimpleRSI:
    """シンプルなRSI計算"""
    
    def __init__(self, period: int = 14):
        self.period = period
        self.prices = []
        self.value = 50.0
    
    def update(self, price: float):
        """価格を追加してRSIを更新"""
        self.prices.append(price)
        if len(self.prices) > self.period + 1:
            self.prices.pop(0)
        
        if len(self.prices) >= self.period + 1:
            changes = np.diff(self.prices)
            gains = np.where(changes > 0, changes, 0)
            losses = np.where(changes < 0, -changes, 0)
            
            avg_gain = np.mean(gains[-self.period:])
            avg_loss = np.mean(losses[-self.period:])
            
            if avg_loss == 0:
                self.value = 100.0
            else:
                rs = avg_gain / avg_loss
                self.value = 100 - (100 / (1 + rs))


class MeanReversionStrategy(Strategy):
    """ボリンジャーバンド + RSI 平均回帰戦略"""
    
    def __init__(self, config: MeanReversionConfig):
        super().__init__(config)
        
        # 設定からパラメータ取得
        self.instrument_id = InstrumentId.from_str(config.instrument_id)
        self.bar_type = BarType.from_str(config.bar_type)
        
        self.bb_period = config.bb_period
        self.bb_std_dev = config.bb_std_dev
        self.rsi_period = config.rsi_period
        self.rsi_oversold = config.rsi_oversold
        self.rsi_overbought = config.rsi_overbought
        self.position_size = Decimal(str(config.position_size))
        
        # インディケータ
        self.bb = None
        self.rsi = None
        self.instrument = None
        self.entry_price = None
    
    def on_start(self):
        """戦略開始時の初期化"""
        self.instrument = self.cache.instrument(self.instrument_id)
        if self.instrument is None:
            self.log.error(f"楽器が見つかりません: {self.instrument_id}")
            return
        
        self.bb = BollingerBand(period=self.bb_period, std_dev=self.bb_std_dev)
        self.rsi = SimpleRSI(period=self.rsi_period)
        
        self.subscribe_bars(self.bar_type)
        self.log.info(f"平均回帰戦略を開始: {self.instrument_id}")
    
    def on_bar(self, bar: Bar):
        """新しいバーを受信した際の処理"""
        current_price = float(bar.close)
        
        self.bb.update(current_price)
        self.rsi.update(current_price)
        
        if self.bb.upper is None:
            return
        
        # オープンポジションを取得
        positions = self.cache.positions_open(instrument_id=self.instrument_id)
        has_position = len(positions) > 0
        
        if not has_position:
            self._check_entry_signals(bar, current_price)
        else:
            position = positions[0] if positions else None
            if position:
                self._check_exit_signals(bar, current_price, position)
    
    def _check_entry_signals(self, bar: Bar, current_price: float):
        """エントリーシグナルの確認"""
        rsi_value = self.rsi.value
        
        if current_price < self.bb.lower and rsi_value < self.rsi_oversold:
            self._place_limit_order(OrderSide.BUY, bar)
            self.log.info(f"買いシグナル - 価格:{current_price:.5f}, RSI:{rsi_value:.2f}")
        
        elif current_price > self.bb.upper and rsi_value > self.rsi_overbought:
            self._place_limit_order(OrderSide.SELL, bar)
            self.log.info(f"売りシグナル - 価格:{current_price:.5f}, RSI:{rsi_value:.2f}")
    
    def _check_exit_signals(self, bar: Bar, current_price: float, position):
        """エグジットシグナルの確認"""
        if position.is_long and current_price >= self.bb.middle:
            self.close_all_positions(self.instrument_id)
            self.log.info(f"買いポジション利益確定 - 価格:{current_price:.5f}")
        
        elif position.is_short and current_price <= self.bb.middle:
            self.close_all_positions(self.instrument_id)
            self.log.info(f"売りポジション利益確定 - 価格:{current_price:.5f}")
    
    def _place_limit_order(self, side: OrderSide, bar: Bar):
        """成行注文を発注"""
        if self.instrument is None:
            return
        
        # 成行注文を使用（確実に約定させるため）
        order = self.order_factory.market(
            instrument_id=self.instrument_id,
            order_side=side,
            quantity=self.instrument.make_qty(self.position_size),
        )
        
        self.submit_order(order)
    
    def on_order_filled(self, event: OrderFilled):
        """注文約定時の処理"""
        self.entry_price = float(event.last_px)
        self.log.info(f"注文約定: {event.order_side} @ {self.entry_price:.5f}")
    
    def on_stop(self):
        """戦略停止時の処理"""
        self.log.info("平均回帰戦略を停止")
        self.close_all_positions(self.instrument_id)
        self.unsubscribe_bars(self.bar_type)
