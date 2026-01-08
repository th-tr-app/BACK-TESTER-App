import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from datetime import datetime, timedelta, time

# --- ページ設定 ---
st.set_page_config(page_title="BACK TESTER ATR", page_icon="📈", layout="wide")

# --- 銘柄名マッピング (省略せず保持) ---
TICKER_NAME_MAP = {
    "4506.T": "住友ファーマ", "3436.T": "SUMCO", "6723.T": "ルネサス", 
    "6315.T": "TOWA", "8725.T": "MS&AD", "8002.T": "丸紅", # 必要に応じて追加
}

def get_ticker_name(ticker):
    return TICKER_NAME_MAP.get(ticker, ticker)

@st.cache_data(ttl=3600)
def fetch_intraday(ticker, start, end):
    try:
        df = yf.download(ticker, start=start, end=end, interval="5m", progress=False, multi_level_index=False, auto_adjust=False)
        return df
    except: return pd.DataFrame()

# ★ 修正ポイント1: ATR算出ロジックを含むデータ取得関数
def fetch_daily_stats_maps(ticker, start):
    try:
        # ATR計算用に60日前から取得
        d_start = start - timedelta(days=60)
        df = yf.download(ticker, start=d_start, end=datetime.now(), interval="1d", progress=False, multi_level_index=False, auto_adjust=False)
        
        if df.empty: return {}, {}, {}
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        # タイムゾーン処理
        if df.index.tzinfo is None:
            df.index = df.index.tz_localize('UTC').tz_convert('Asia/Tokyo')
        else:
            df.index = df.index.tz_convert('Asia/Tokyo')
            
        # ATR計算 (14日間)
        high_low = df['High'] - df['Low']
        high_close_prev = abs(df['High'] - df['Close'].shift(1))
        low_close_prev = abs(df['Low'] - df['Close'].shift(1))
        tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()
        
        # 判定に使うのは「前日時点」のATR
        atr_prev = atr.shift(1)
        
        prev_close = df['Close'].shift(1)
        prev_close_map = {d.strftime('%Y-%m-%d'): c for d, c in zip(df.index, prev_close) if pd.notna(c)}
        curr_open_map = {d.strftime('%Y-%m-%d'): o for d, o in zip(df.index, df['Open']) if pd.notna(o)}
        atr_map = {d.strftime('%Y-%m-%d'): a for d, a in zip(df.index, atr_prev) if pd.notna(a)}
        
        return prev_close_map, curr_open_map, atr_map
    except: return {}, {}, {}

# --- サイドバーUI ---
st.sidebar.header("⚙️ バックテスト設定")
ticker_input = st.sidebar.text_input("銘柄コード (例: 4506.T, 3436.T)", "4506.T")
start_date = st.sidebar.date_input("開始日", datetime.now() - timedelta(days=30))

st.sidebar.divider()
st.sidebar.subheader("💰 決済ルール")
trailing_start = st.sidebar.number_input("トレイリング開始 (%)", 0.1, 5.0, 0.35, 0.05) / 100
trailing_pct = st.sidebar.number_input("下がったら成行注文 (%)", 0.1, 5.0, 0.15, 0.05) / 100
stop_loss_fixed = st.sidebar.number_input("固定損切り (%) ※ATR非使用時", -5.0, -0.1, -0.5, 0.05) / 100

# ★ 修正ポイント2: ATR動的損切りUI
st.sidebar.write("")
st.sidebar.divider()
st.sidebar.write("📉 **動的損切り設定 (ATR)**")
use_atr_stop = st.sidebar.checkbox("ATR損切りを使用", value=True)
atr_multiplier = st.sidebar.number_input("ATR倍率 (推奨1.5〜2.0)", 0.5, 5.0, 1.5, 0.1)
atr_min_stop = st.sidebar.number_input("最低損切り幅 (%)", 0.1, 5.0, 0.5, 0.1) / 100

SLIPPAGE_PCT = 0.0003
FORCE_CLOSE_TIME = time(14, 55)

if st.sidebar.button("バックテスト実行", type="primary"):
    tickers = [t.strip() for t in ticker_input.split(",")]
    all_trades = []
    
    for ticker in tickers:
        df = fetch_intraday(ticker, start_date, datetime.now())
        prev_close_map, curr_open_map, atr_map = fetch_daily_stats_maps(ticker, start_date)
        
        if df.empty: continue
        
        # インジケータ計算 (EMA, MACD, RSI)
        df['EMA5'] = EMAIndicator(close=df['Close'], window=5).ema_indicator()
        macd = MACD(close=df['Close'])
        df['MACD_H'] = macd.macd_diff()
        df['MACD_H_Prev'] = df['MACD_H'].shift(1)
        
        unique_dates = np.unique(df.index.date)
        for date in unique_dates:
            day = df[df.index.date == date].copy().between_time('09:00', '15:00')
            if day.empty: continue
            
            date_str = date.strftime('%Y-%m-%d')
            daily_open = curr_open_map.get(date_str)
            prev_close = prev_close_map.get(date_str)
            if not daily_open or not prev_close: continue
            
            gap_pct = (daily_open - prev_close) / prev_close
            
            in_pos = False
            entry_p = 0
            stop_p = 0
            trail_high = 0
            trail_active = False
            
            for ts, row in day.iterrows():
                cur_time = ts.time()
                
                if not in_pos:
                    # エントリー条件 (簡易化して記載していますが5.8のロジックを継承)
                    if time(9,0) <= cur_time <= time(9,15):
                        if row['Close'] > row['EMA5'] and row['MACD_H'] > row['MACD_H_Prev']:
                            entry_p = row['Close'] * (1 + SLIPPAGE_PCT)
                            in_pos = True
                            
                            # ★ 修正ポイント3: 動的損切り価格の計算
                            if use_atr_stop:
                                atr_val = atr_map.get(date_str)
                                if atr_val:
                                    # ATRベースの損切り幅計算
                                    dynamic_sl_pct = max(atr_min_stop, (atr_val / entry_p) * atr_multiplier)
                                    stop_p = entry_p * (1 - dynamic_sl_pct)
                                else:
                                    stop_p = entry_p * (1 + stop_loss_fixed)
                            else:
                                stop_p = entry_p * (1 + stop_loss_fixed)
                            
                            trail_high = row['High']
                else:
                    # トレイリング・損切りロジック
                    if row['High'] > trail_high: trail_high = row['High']
                    if not trail_active and (trail_high >= entry_p * (1 + trailing_start)):
                        trail_active = True
                    
                    exit_p = None
                    if trail_active and (row['Low'] <= trail_high * (1 - trailing_pct)):
                        exit_p = trail_high * (1 - trailing_pct)
                        reason = "トレーリング"
                    elif row['Low'] <= stop_p:
                        exit_p = stop_p
                        reason = "損切り"
                    elif cur_time >= FORCE_CLOSE_TIME:
                        exit_p = row['Close']
                        reason = "大引け"
                    
                    if exit_p:
                        all_trades.append({
                            'Ticker': ticker, 'Date': date_str, 'PnL': (exit_p - entry_p) / entry_p, 'Reason': reason
                        })
                        break

    if all_trades:
        res_df = pd.DataFrame(all_trades)
        st.write("### 📊 バックテスト結果")
        st.dataframe(res_df)
        st.write(f"平均損益: {res_df['PnL'].mean():.2%}")
        st.write(f"勝率: {(res_df['PnL'] > 0).mean():.1%}")
