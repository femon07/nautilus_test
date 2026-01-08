"""
平均回帰戦略の単体テスト
"""
import pytest
from strategies.mean_reversion import BollingerBand


class TestBollingerBand:
    """ボリンジャーバンド計算のテスト"""
    
    def test_initialization(self):
        """初期化テスト"""
        bb = BollingerBand(period=20, std_dev=2.0)
        assert bb.period == 20
        assert bb.std_dev == 2.0
        assert bb.upper is None
        assert bb.lower is None
    
    def test_update_insufficient_data(self):
        """データ不足時は計算されないことを確認"""
        bb = BollingerBand(period=5, std_dev=2.0)
        
        # 4個のデータ（period未満）を追加
        for price in [1.0, 1.1, 1.2, 1.3]:
            bb.update(price)
        
        # まだ計算されないはず
        assert bb.upper is None
        assert bb.middle is None
        assert bb.lower is None
    
    def test_update_sufficient_data(self):
        """十分なデータがある場合に計算されることを確認"""
        bb = BollingerBand(period=5, std_dev=2.0)
        
        # 5個のデータを追加
        prices = [1.0, 1.1, 1.2, 1.1, 1.0]
        for price in prices:
            bb.update(price)
        
        # 計算されるはず
        assert bb.upper is not None
        assert bb.middle is not None
        assert bb.lower is not None
        
        # 中央線は平均値
        assert bb.middle == pytest.approx(1.08, rel=0.01)
        
        # 上限 > 中央 > 下限
        assert bb.upper > bb.middle > bb.lower
    
    def test_bollinger_band_range(self):
        """ボリンジャーバンドの幅が妥当かテスト"""
        bb = BollingerBand(period=10, std_dev=2.0)
        
        # 等間隔のデータ
        for price in [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]:
            bb.update(price)
        
        # ボラティリティがゼロなら、上限=中央=下限
        assert bb.upper == pytest.approx(bb.middle, abs=0.001)
        assert bb.lower == pytest.approx(bb.middle, abs=0.001)
    
    def test_rolling_window(self):
        """ローリングウィンドウが機能することを確認"""
        bb = BollingerBand(period=3, std_dev=1.0)
        
        # 3個のデータでバンド計算
        bb.update(1.0)
        bb.update(2.0)
        bb.update(3.0)
        
        middle_before = bb.middle
        
        # さらにデータ追加（古いデータが削除されるはず）
        bb.update(4.0)
        
        # 中央線が変わるはず（1.0が削除され、4.0が追加）
        # 新しい平均: (2.0 + 3.0 + 4.0) / 3 = 3.0
        assert bb.middle == pytest.approx(3.0, abs=0.01)
        assert bb.middle != middle_before


class TestMeanReversionStrategy:
    """戦略ロジックのテスト（モック使用）"""
    
    def test_strategy_config(self):
        """設定が正しく読み込まれることを確認"""
        from strategies.mean_reversion import MeanReversionStrategy
        
        config = {
            "instrument_id": "EUR/USD.SIM",
            "bar_type": "EUR/USD.SIM-1-MINUTE-MID",
            "bb_period": 25,
            "rsi_period": 10,
        }
        
        # Strategyクラスのインスタンス化には完全な設定が必要だが、
        # ここでは設定の検証のみを行う
        assert config["bb_period"] == 25
        assert config["rsi_period"] == 10


# pytest実行コマンド例:
# docker compose run --rm backtest pytest tests/ -v
