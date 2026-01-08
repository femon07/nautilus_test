"""
ボリンジャーバンド + RSI による平均回帰戦略（改善版: トレンドフィルタ + ATR SL/TP）
"""
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.model.events import OrderFilled
from decimal import Decimal
import numpy as np


class MeanReversionConfig(StrategyConfig, frozen=True):
    """平均回帰戦略の設定"""
    instrument_id: str = "EUR/USD.SIM"
    bar_type: str = "EUR/USD.SIM-1-MINUTE-MID-EXTERNAL"
    
    # BB / RSI Settings
    bb_period: int = 20
    bb_std_dev: float = 2.0
    rsi_period: int = 14
    rsi_oversold: float = 25.0
    rsi_overbought: float = 75.0
    
    # Trend Filter
    ema_period: int = 200  # 長期トレンド判定用
    
    # Risk Management
    position_size: float = 1000.0
    atr_period: int = 14
    sl_atr_mult: float = 2.0  # SL = Entry - ATR * 2.0
    tp_atr_mult: float = 3.0  # TP = Entry + ATR * 3.0


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


class EMA:
    """指数平滑移動平均 (Exponential Moving Average)"""
    def __init__(self, period: int):
        self.period = period
        self.value = None
        self.multiplier = 2.0 / (period + 1.0)
        
    def update(self, price: float):
        if self.value is None:
            self.value = price
        else:
            self.value = (price - self.value) * self.multiplier + self.value


class ATR:
    """Average True Range (Wilder's Smoothing)"""
    def __init__(self, period: int = 14):
        self.period = period
        self.value = None
        self.prev_close = None
        
    def update(self, high: float, low: float, close: float):
        if self.prev_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - self.prev_close), abs(low - self.prev_close))
        
        self.prev_close = close
        
        if self.value is None:
            self.value = tr
        else:
            # Wilder's Smoothing
            self.value = (self.value * (self.period - 1) + tr) / self.period


class MeanReversionStrategy(Strategy):
    """ボリンジャーバンド + RSI 平均回帰戦略（改善版）"""
    
    def __init__(self, config: MeanReversionConfig):
        super().__init__(config)
        
        self.instrument_id = InstrumentId.from_str(config.instrument_id)
        self.bar_type = BarType.from_str(config.bar_type)
        
        self.bb_period = config.bb_period
        self.bb_std_dev = config.bb_std_dev
        self.rsi_period = config.rsi_period
        self.rsi_oversold = config.rsi_oversold
        self.rsi_overbought = config.rsi_overbought
        self.position_size = Decimal(str(config.position_size))
        
        # Trend Filter
        self.ema_period = config.ema_period
        
        # SL/TP Multipliers
        self.sl_atr_mult = config.sl_atr_mult
        self.tp_atr_mult = config.tp_atr_mult
        
        # Indicators
        self.bb = None
        self.rsi = None
        self.ema = None
        self.atr = None
        self.instrument = None
        
        # Position Management
        self.entry_price = None
        self.position_side = None
        self.current_sl_price = None
        self.current_tp_price = None
        self.pending_atr_snap = None # エントリー判断時のATRを保持
    
    def on_start(self):
        """戦略開始時の初期化"""
        self.instrument = self.cache.instrument(self.instrument_id)
        if self.instrument is None:
            self.log.error(f"楽器が見つかりません: {self.instrument_id}")
            return
        
        self.bb = BollingerBand(period=self.bb_period, std_dev=self.bb_std_dev)
        self.rsi = SimpleRSI(period=self.rsi_period)
        self.ema = EMA(period=self.ema_period)
        self.atr = ATR(period=self.config.atr_period)
        
        self.subscribe_bars(self.bar_type)
        self.log.info(f"平均回帰戦略(改善版)を開始: {self.instrument_id}")
        self.log.info(f"EMA: {self.ema_period}, ATR SL x{self.sl_atr_mult}, TP x{self.tp_atr_mult}")
    
    def on_bar(self, bar: Bar):
        """新しいバーを受信した際の処理"""
        current_price = float(bar.close)
        high = float(bar.high)
        low = float(bar.low)
        
        self.bb.update(current_price)
        self.rsi.update(current_price)
        self.ema.update(current_price)
        self.atr.update(high, low, current_price)
        
        if self.bb.upper is None or self.ema.value is None or self.atr.value is None:
            return
        
        positions = self.cache.positions_open(instrument_id=self.instrument_id)
        has_position = len(positions) > 0
        
        if not has_position:
            self._check_entry_signals(bar, current_price)
        else:
            self._check_exit_signals(bar) # Barを渡してHigh/Low判定
    
    def _check_entry_signals(self, bar: Bar, current_price: float):
        """エントリーシグナルの確認"""
        rsi_value = self.rsi.value
        ema_value = self.ema.value
        
        # Trend Filter:
        # 上昇トレンド(価格 > EMA)のときは「押し目買い」狙い (RSI売られすぎ)
        # 下降トレンド(価格 < EMA)のときは「戻り売り」狙い (RSI買われすぎ)
        
        # 買いシグナル: 価格 < LowerBand AND RSI < Oversold AND Trend is UP (Price > EMA)
        if current_price < self.bb.lower and rsi_value < self.rsi_oversold:
            if current_price > ema_value:  # Trend Filter
                 self._place_order(OrderSide.BUY)
                 self.log.info(f"買いシグナル (Trend UP) - Price:{current_price:.5f}, EMA:{ema_value:.5f}, RSI:{rsi_value:.2f}")
            else:
                 # トレンド逆行のためスルー
                 pass
        
        # 売りシグナル: 価格 > UpperBand AND RSI > Overbought AND Trend is DOWN (Price < EMA)
        elif current_price > self.bb.upper and rsi_value > self.rsi_overbought:
            if current_price < ema_value:  # Trend Filter
                self._place_order(OrderSide.SELL)
                self.log.info(f"売りシグナル (Trend DOWN) - Price:{current_price:.5f}, EMA:{ema_value:.5f}, RSI:{rsi_value:.2f}")
            else:
                 pass
    
    def _check_exit_signals(self, bar: Bar):
        """Dynamic SL/TPによるエグジット判定"""
        if self.current_sl_price is None or self.current_tp_price is None:
            return

        # BarのHigh/Lowを使って判定（より厳密）
        high = float(bar.high)
        low = float(bar.low)
        
        if self.position_side == OrderSide.BUY:
            # 買いポジション
            # HighがTPを超えたら利確
            if high >= self.current_tp_price:
                self.close_all_positions(self.instrument_id)
                self.log.info(f"TP達成(BUY) - High:{high:.5f} >= TP:{self.current_tp_price:.5f}")
                self._reset_position()
            # LowがSLを割ったら損切り
            elif low <= self.current_sl_price:
                self.close_all_positions(self.instrument_id)
                self.log.info(f"SL発動(BUY) - Low:{low:.5f} <= SL:{self.current_sl_price:.5f}")
                self._reset_position()
                
        elif self.position_side == OrderSide.SELL:
            # 売りポジション
            # LowがTPを下回ったら利確
            if low <= self.current_tp_price:
                 self.close_all_positions(self.instrument_id)
                 self.log.info(f"TP達成(SELL) - Low:{low:.5f} <= TP:{self.current_tp_price:.5f}")
                 self._reset_position()
            # HighがSLを超えたら損切り
            elif high >= self.current_sl_price:
                 self.close_all_positions(self.instrument_id)
                 self.log.info(f"SL発動(SELL) - High:{high:.5f} >= SL:{self.current_sl_price:.5f}")
                 self._reset_position()
    
    def _place_order(self, side: OrderSide):
        """成行注文を発注"""
        if self.instrument is None:
            return
            
        # ATRをスナップショット（約定時の計算用）
        self.pending_atr_snap = self.atr.value
        
        order = self.order_factory.market(
            instrument_id=self.instrument_id,
            order_side=side,
            quantity=self.instrument.make_qty(self.position_size),
        )
        
        self.submit_order(order)
    
    def _reset_position(self):
        """ポジション情報をリセット"""
        self.entry_price = None
        self.position_side = None
        self.current_sl_price = None
        self.current_tp_price = None
    
    def on_order_filled(self, event: OrderFilled):
        """注文約定時の処理"""
        # エントリー注文の約定のみ反応する（クローズ注文は無視）
        if self.entry_price is None: 
            self.entry_price = float(event.last_px)
            self.position_side = event.order_side
            
            # SL/TP計算
            atr_val = self.pending_atr_snap if self.pending_atr_snap else 0.0010 # Default fallback
            
            if event.order_side == OrderSide.BUY:
                self.current_sl_price = self.entry_price - (atr_val * self.sl_atr_mult)
                self.current_tp_price = self.entry_price + (atr_val * self.tp_atr_mult)
            else:
                self.current_sl_price = self.entry_price + (atr_val * self.sl_atr_mult)
                self.current_tp_price = self.entry_price - (atr_val * self.tp_atr_mult)
                
            self.log.info(f"Entry Filled: {event.order_side} @ {self.entry_price:.5f}")
            self.log.info(f"Set SL: {self.current_sl_price:.5f}, TP: {self.current_tp_price:.5f} (ATR: {atr_val:.5f})")
    
    def on_stop(self):
        """戦略停止時の処理"""
        self.log.info("平均回帰戦略を停止")
        self.close_all_positions(self.instrument_id)
        # self.unsubscribe_bars(self.bar_type) # Error handling if already unsubscribed? Safe to call usually.
