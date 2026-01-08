"""
合成OHLCVデータ生成ユーティリティ
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path


def generate_synthetic_ohlcv(
    start_date: str = "2023-01-01",
    end_date: str = "2023-12-31",
    initial_price: float = 1.1000,
    volatility: float = 0.0015,
    trend: float = 0.0,
    freq: str = "1T"  # 1分足
) -> pd.DataFrame:
    """
    幾何ブラウン運動(GBM)ベースの合成OHLCVデータを生成
    
    Parameters
    ----------
    start_date : str
        開始日
    end_date : str
        終了日
    initial_price : float
        初期価格
    volatility : float
        ボラティリティ（標準偏差）
    trend : float
        ドリフト（トレンド）
    freq : str
        時間足（'1T'=1分、'5T'=5分など）
    
    Returns
    -------
    pd.DataFrame
        timestamp, open, high, low, close, volume を含むDataFrame
    """
    # 時間インデックス生成
    date_range = pd.date_range(start=start_date, end=end_date, freq=freq)
    n_periods = len(date_range)
    
    # ランダムウォーク生成
    np.random.seed(42)  # 再現性のため
    returns = np.random.normal(trend, volatility, n_periods)
    
    # 累積リターンから価格生成
    price_series = initial_price * np.exp(np.cumsum(returns))
    
    # OHLC生成（closeベースでランダムな変動を追加）
    ohlc_data = []
    for i, close in enumerate(price_series):
        # 各バーでの変動幅
        bar_volatility = volatility * close * np.random.uniform(0.5, 1.5)
        
        open_price = close + np.random.normal(0, bar_volatility / 4)
        high_price = max(open_price, close) + abs(np.random.normal(0, bar_volatility / 2))
        low_price = min(open_price, close) - abs(np.random.normal(0, bar_volatility / 2))
        
        # ボリュームはランダム（FXでは意味が薄いが、互換性のため）
        volume = np.random.randint(100, 10000)
        
        ohlc_data.append({
            'timestamp': date_range[i],
            'open': round(open_price, 5),
            'high': round(high_price, 5),
            'low': round(low_price, 5),
            'close': round(close, 5),
            'volume': volume
        })
    
    return pd.DataFrame(ohlc_data)


def save_synthetic_data(
    output_path: str = "./data/EUR_USD_synthetic.csv",
    **kwargs
) -> Path:
    """
    合成データを生成してCSVに保存
    
    Parameters
    ----------
    output_path : str
        出力先CSVパス
    **kwargs
        generate_synthetic_ohlcv()に渡すパラメータ
    
    Returns
    -------
    Path
        保存したファイルのパス
    """
    df = generate_synthetic_ohlcv(**kwargs)
    
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_csv(output_file, index=False)
    print(f"✓ 合成データを生成しました: {output_file} ({len(df):,} rows)")
    
    return output_file


if __name__ == "__main__":
    # テスト実行
    save_synthetic_data(
        start_date="2023-01-01",
        end_date="2023-12-31",
        initial_price=1.1000,
        volatility=0.0015,
        trend=0.00001  # わずかな上昇トレンド
    )
