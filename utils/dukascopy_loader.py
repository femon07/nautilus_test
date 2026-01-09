"""
Dukascopyデータローダー（独自実装版）
requestsライブラリを使用して直接データをダウンロード
"""
import os
import io
import lzma
import struct
import pandas as pd
import requests
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
import time

# Dukascopyのティックデータフォーマット
# 各ティックは20バイト: timestamp(4), ask(4), bid(4), ask_vol(4), bid_vol(4)
TICK_STRUCT = struct.Struct('>IIIff')

def _decompress_lzma(data: bytes) -> bytes:
    """LZMA圧縮されたbi5ファイルを解凍"""
    try:
        return lzma.decompress(data)
    except lzma.LZMAError:
        return b''

def _parse_ticks(data: bytes, base_timestamp: datetime) -> list:
    """バイナリティックデータをパース"""
    ticks = []
    offset = 0
    while offset + 20 <= len(data):
        ms_offset, ask, bid, ask_vol, bid_vol = TICK_STRUCT.unpack_from(data, offset)
        offset += 20
        
        tick_time = base_timestamp + timedelta(milliseconds=ms_offset)
        # askとbidは価格の10万倍で格納されている
        ticks.append({
            'timestamp': tick_time,
            'ask': ask / 100000.0,
            'bid': bid / 100000.0,
            'ask_volume': ask_vol,
            'bid_volume': bid_vol
        })
    return ticks

def _download_hour(symbol: str, dt: datetime, session: requests.Session) -> list:
    """1時間分のティックデータをダウンロード"""
    # Dukascopyは月を0-indexedで使用（1月=00）
    month = dt.month - 1
    url = f"https://datafeed.dukascopy.com/datafeed/{symbol}/{dt.year}/{month:02d}/{dt.day:02d}/{dt.hour:02d}h_ticks.bi5"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for attempt in range(3):
        try:
            resp = session.get(url, headers=headers, timeout=30)
            if resp.status_code == 200 and len(resp.content) > 0:
                decompressed = _decompress_lzma(resp.content)
                if decompressed:
                    base_ts = datetime(dt.year, dt.month, dt.day, dt.hour, tzinfo=timezone.utc)
                    return _parse_ticks(decompressed, base_ts)
            elif resp.status_code == 404:
                # データが存在しない時間帯（週末など）
                return []
            time.sleep(0.5)
        except Exception as e:
            time.sleep(1)
    return []

def _resample_to_m1(ticks_df: pd.DataFrame) -> pd.DataFrame:
    """ティックデータを1分足にリサンプル"""
    if ticks_df.empty:
        return pd.DataFrame()
    
    ticks_df = ticks_df.set_index('timestamp')
    # mid価格を計算
    ticks_df['mid'] = (ticks_df['ask'] + ticks_df['bid']) / 2
    
    ohlc = ticks_df['mid'].resample('1min').ohlc()
    ohlc = ohlc.dropna()
    
    # volumeはティック数で代用
    volume = ticks_df['mid'].resample('1min').count()
    ohlc['volume'] = volume
    
    ohlc = ohlc.reset_index()
    ohlc.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    
    return ohlc

def load_dukascopy_data(symbol: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    Dukascopyから直接データをダウンロードし、CSVとして保存・読み込みを行う
    キャッシュファイル名は期間を含む形式で自動生成されます。
    
    Parameters
    ----------
    symbol : str
        通貨ペア (例: "EURUSD")
    start_date : datetime
        開始日時 (TZ-naive or UTC)
    end_date : datetime
        終了日時 (排他的: この日時を含まない)
        
    Returns
    -------
    pd.DataFrame
        timestamp (UTC), open, high, low, close, volume を含むDataFrame
    """
    # まず入力日付をUTCに正規化する
    if start_date.tzinfo is None:
        # naiveならUTCとみなす
        start_date = start_date.replace(tzinfo=timezone.utc)
    else:
        start_date = start_date.astimezone(timezone.utc)
        
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)
    else:
        end_date = end_date.astimezone(timezone.utc)

    # 日付文字列フォーマット(時刻まで含める)
    fmt = "%Y%m%d-%H%M"
    filename = f"{symbol}_{start_date.strftime(fmt)}_{end_date.strftime(fmt)}.csv"
    path = Path(f"./data/{filename}")
    
    # 既にファイルが存在するかチェック
    if path.exists():
        print(f"✓ キャッシュされたデータを使用します: {path}")
        df = pd.read_csv(path)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        return df

    print(f"Dukascopyからデータをダウンロード中: {symbol} ({start_date} - {end_date})...")
    
    # ディレクトリ作成
    path.parent.mkdir(parents=True, exist_ok=True)
    
    all_ticks = []
    session = requests.Session()
    
    # Dukascopy API用にnaiveなUTC時間を作成
    current = start_date.replace(tzinfo=None)
    end_dt_naive = end_date.replace(tzinfo=None)
    
    total_hours = int((end_dt_naive - current).total_seconds() / 3600)
    processed = 0
    
    while current < end_dt_naive:
        ticks = _download_hour(symbol, current, session)
        all_ticks.extend(ticks)
        
        processed += 1
        if processed % 24 == 0:  # 1日ごとに進捗表示
            pct = (processed / total_hours) * 100 if total_hours > 0 else 100
            print(f"  進捗: {pct:.1f}% ({current.date()})")
        
        current += timedelta(hours=1)
        time.sleep(0.1)  # レート制限対策
    
    if not all_ticks:
        raise ValueError("取得されたデータが空です。期間やシンボルを確認してください。")
    
    # ティックをDataFrameに変換
    ticks_df = pd.DataFrame(all_ticks)
    
    # 1分足にリサンプル
    print("ティックデータを1分足に変換中...")
    df = _resample_to_m1(ticks_df)
    
    # CSV保存
    df.to_csv(path, index=False)
    print(f"✓ データを保存しました: {path} ({len(df):,}行)")
    
    return df
