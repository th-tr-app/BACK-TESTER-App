import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from datetime import datetime, timedelta, time

# --- ページ設定 ---
st.set_page_config(page_title="BACK TESTER", page_icon="📈", layout="wide")

# --- 銘柄名マッピング ---
TICKER_NAME_MAP = {
    "4506.T": "住友ファーマ", "3436.T": "SUMCO", "6723.T": "ルネサス", 
    "6315.T": "TOWA", "8725.T": "MS&AD", "8002.T": "丸紅", "7453.T": "良品計画",
}

# CSS
st.markdown("""
    <style>
    @media (max-width: 640px) {
        [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: 10px !important; }
        [data-testid="column"] { flex: 0 0 45% !important; max-width: 45% !important; min-width: 45% !important; }
        [data-testid="stMetricLabel"] { font-size: 12px !important; }
        [data-testid="stMetricValue"] { font-size: 18px !important; }
    }
    th, td { text-align: left !important; }
    </style>
    """, unsafe_allow_html=True)

st.markdown("""
    <div style='margin-bottom: 20px;'>
        <h1 style='font-weight: 400; font-size: 46px; margin: 0; padding: 0;'>BACK TESTER</h1>
        <h3 style='font-weight: 300; font-size: 20px; margin: 0; padding: 0; color: #aaaaaa;'>DAY TRADING MANAGER｜ver 5.8 ATR</h3>
    </div>
    """, unsafe_allow_html=True)

def get_trade_pattern(row, gap_pct):
    check_vwap = row['VWAP'] if pd.notna(row['VWAP']) else row['Close']
    if (gap_pct <= -0.004) and (row['Close'] > check_vwap): return "A：反転狙い"
    elif (-0.003 <= gap_pct < 0.003) and (row['Close'] > row['EMA5']): return "D：上昇継続"
    elif (gap_pct >= 0.005) and (row['RSI14'] >= 65): return "C：ブレイク"
    elif (gap_pct >= 0.003) and (row['Close'] > row['EMA5']): return "B：押目上昇"
    return "E：他タイプ"

@st.cache_data(ttl=600)
def fetch_intraday(ticker, start, end):
    try:
        df = yf.download(ticker, start=start, end=datetime.now(), interval="5m", progress=False, multi_level_index=False, auto_adjust=False)
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_daily_stats_maps(ticker, start):
    p_map, o_map, a_map = {}, {}, {}
    try:
        d_start = start - timedelta(days=60)
        df = yf.download(ticker, start=d_start, end=datetime.now(), interval="1d", progress=False, multi_level_index=False, auto_adjust=False)
        if df.empty: return p_map, o_map, a_map
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        if df.index.tzinfo is None: df.index = df.index.tz_localize('UTC').tz_convert('Asia/Tokyo')
        else: df.index = df.index.tz_convert('Asia/Tokyo')
        
        high_low = df['High'] - df['Low']
        high_close_prev = abs(df['High'] - df['Close'].shift(1))
        low_close_prev = abs(df['Low'] - df['Close'].shift(1))
        tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()
        atr_prev = atr.shift(1)
        
        prev_close = df['Close'].shift(1)
        p_map = {d.strftime('%Y-%m-%d'): c for d, c in zip(df.index, prev_close) if pd.notna(c)}
        o_map = {d.strftime('%Y-%m-%d'): o for d, o in zip(df.index, df['Open']) if pd.notna(o)}
        a_map = {d.strftime('%Y-%m-%d'): a for d, a in zip(df.index, atr_prev) if pd.notna(a)}
        return p_map, o_map, a_map
    except: return p_map, o_map, a_map

@st.cache_data(ttl=86400)
def get_ticker_name(ticker):
    return TICKER_NAME_MAP.get(ticker, ticker)

# --- UI ---
ticker_input = st.text_input("銘柄コード (カンマ区切り)", "4506.T, 3436.T")
tickers = [t.strip() for t in ticker_input.split(",") if t.strip()]
main_btn = st.button("バックテスト実行", type="primary", key="main_btn")
st.divider()

st.sidebar.header("⚙️ パラメーター設定")
days_back = st.sidebar.slider("過去何日分を取得", 10, 59, 30)
st.sidebar.subheader("⏰ 時間設定")
start_entry_time = st.sidebar.time_input("開始時間", time(9, 0), step=300)
end_entry_time = st.sidebar.time_input("終了時間", time(9, 15), step=300)
st.sidebar.subheader("📉 エントリー条件")
use_vwap = st.sidebar.checkbox("**VWAP** より上でエントリー", value=True)
use_ema = st.sidebar.checkbox("**EMA5** より上でエントリー", value=True)
use_rsi = st.sidebar.checkbox("**RSI** が45以上or上向き", value=True)
use_macd = st.sidebar.checkbox("**MACD** が上向き", value=True)
st.sidebar.divider()
gap_min = st.sidebar.slider("寄付ギャップダウン下限 (%)", -10.0, 0.0, -3.0, 0.05) / 100
gap_max = st.sidebar.slider("寄付ギャップアップ上限 (%)", -5.0, 5.0, 1.0, 0.05) / 100

st.sidebar.subheader("💰 決済ルール")
trailing_start = st.sidebar.number_input("トレイリング開始 (%)", 0.1, 5.0, 0.35, 0.05) / 100
trailing_pct = st.sidebar.number_input("下がったら成行注文 (%)", 0.1, 5.0, 0.15, 0.05) / 100
stop_loss_fixed = st.sidebar.number_input("損切り (%) ※ATR非使用時", -5.0, -0.1, -0.5, 0.05) / 100
st.sidebar.divider()
st.sidebar.write("📉 **動的損切り設定 (ATR)**")
use_atr_stop = st.sidebar.checkbox("ATR損切りを使用", value=True)
atr_multiplier = st.sidebar.number_input("ATR倍率", 0.5, 5.0, 1.5, 0.1)
atr_min_stop = st.sidebar.number_input("最低損切り (%)", 0.1, 5.0, 0.5, 0.1) / 100

SLIPPAGE_PCT = 0.0003
FORCE_CLOSE_TIME = time(14, 55)
sidebar_btn = st.sidebar.button("バックテスト実行", type="primary", key="sidebar_btn")

if main_btn or sidebar_btn:
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    all_trades = []
    progress_bar = st.progress(0); status_text = st.empty()
    ticker_names = {}

    for i, ticker in enumerate(tickers):
        status_text.text(f"Testing {ticker}...")
        progress_bar.progress((i + 1) / len(tickers))
        ticker_names[ticker] = get_ticker_name(ticker)
        df = fetch_intraday(ticker, start_date, end_date)
        prev_close_map, curr_open_map, atr_map = fetch_daily_stats_maps(ticker, start_date)
        
        if df.empty: continue
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        if df.index.tzinfo is None: df.index = df.index.tz_localize('UTC').tz_convert('Asia/Tokyo')
        else: df.index = df.index.tz_convert('Asia/Tokyo')

        df['EMA5'] = EMAIndicator(close=df['Close'], window=5).ema_indicator()
        macd = MACD(close=df['Close']); df['MACD_H'] = macd.macd_diff(); df['MACD_H_Prev'] = df['MACD_H'].shift(1)
        rsi = RSIIndicator(close=df['Close'], window=14); df['RSI14'] = rsi.rsi(); df['RSI14_Prev'] = df['RSI14'].shift(1)
        
        def compute_vwap(d):
            tp = (d['High'] + d['Low'] + d['Close']) / 3
            cum_vp = (tp * d['Volume']).cumsum()
            cum_vol = d['Volume'].cumsum().replace(0, np.nan)
            return (cum_vp / cum_vol).ffill()

        unique_dates = np.unique(df.index.date)
        for date in unique_dates:
            day = df[df.index.date == date].copy().between_time('09:00', '15:00')
            if day.empty: continue
            day['VWAP'] = compute_vwap(day)
            date_str = date.strftime('%Y-%m-%d')
            prev_close = prev_close_map.get(date_str); daily_open = curr_open_map.get(date_str)
            if prev_close is None or daily_open is None: continue

            gap_pct = (daily_open - prev_close) / prev_close
            in_pos = False; entry_p = 0; entry_t = None; entry_vwap = 0; stop_p = 0; trail_active = False; trail_high = 0
            sl_pct_to_record = 0 # 初期化
            
            for ts, row in day.iterrows():
                cur_time = ts.time()
                if np.isnan(row['EMA5']) or np.isnan(row['RSI14']): continue
                if not in_pos:
                    if start_entry_time <= cur_time <= end_entry_time:
                        if gap_min <= gap_pct <= gap_max:
                            cond_vwap = (row['Close'] > row['VWAP']) if use_vwap else True
                            cond_ema  = (row['Close'] > row['EMA5']) if use_ema else True
                            cond_rsi = ((row['RSI14'] > 45) and (row['RSI14'] > row['RSI14_Prev'])) if use_rsi else True
                            cond_macd = (row['MACD_H'] > row['MACD_H_Prev']) if use_macd else True
                            if pd.isna(row['VWAP']) and use_vwap: cond_vwap = False
                            
                            if cond_vwap and cond_ema and cond_rsi and cond_macd:
                                entry_p = row['Close'] * (1 + SLIPPAGE_PCT); entry_t = ts; entry_vwap = row['VWAP']; in_pos = True
                                
                                # ★修正：損切り価格の計算と記録
                                if use_atr_stop:
                                    atr_val = atr_map.get(date_str)
                                    if atr_val:
                                        sl_pct_to_record = max(atr_min_stop, (atr_val / entry_p) * atr_multiplier)
                                        stop_p = entry_p * (1 - sl_pct_to_record)
                                    else:
                                        sl_pct_to_record = abs(stop_loss_fixed)
                                        stop_p = entry_p * (1 + stop_loss_fixed)
                                else:
                                    sl_pct_to_record = abs(stop_loss_fixed)
                                    stop_p = entry_p * (1 + stop_loss_fixed)
                                
                                trail_active = False; trail_high = row['High']
                                pattern_type = get_trade_pattern(row, gap_pct)
                else:
                    if row['High'] > trail_high: trail_high = row['High']
                    if not trail_active and (trail_high >= entry_p * (1 + trailing_start)): trail_active = True
                    exit_p = None; reason = ""
                    if trail_active and (row['Low'] <= trail_high * (1 - trailing_pct)):
                        exit_p = trail_high * (1 - trailing_pct) * (1 - SLIPPAGE_PCT); reason = "トレイリング"
                    elif row['Low'] <= stop_p:
                        exit_p = stop_p * (1 - SLIPPAGE_PCT); reason = "損切り"
                    elif cur_time >= FORCE_CLOSE_TIME:
                        exit_p = row['Close'] * (1 - SLIPPAGE_PCT); reason = "時間切れ"
                    
                    if exit_p:
                        all_trades.append({
                            'Ticker': ticker, 'Entry': entry_t, 'Exit': ts, 'In': int(entry_p), 'Out': int(exit_p),
                            'PnL': (exit_p - entry_p) / entry_p, 'Reason': reason, 'EntryVWAP': entry_vwap, 'Gap(%)': gap_pct * 100,
                            'Pattern': pattern_type, 'PrevClose': int(prev_close), 'DayOpen': int(daily_open),
                            'SL設定(%)': sl_pct_to_record * 100  # ★追加
                        })
                        in_pos = False; break
                        
    progress_bar.empty(); status_text.empty()
    res_df = pd.DataFrame(all_trades)
    
    if res_df.empty:
        st.warning("条件に合うトレードはありませんでした。")
    else:
        tab1, tab2, tab6 = st.tabs(["📊 サマリー", "🤖 勝ちパターン", "📝 詳細ログ"])
        with tab1:
            count_all = len(res_df); wins_all = res_df[res_df['PnL'] > 0]
            win_rate_all = len(wins_all) / count_all if count_all > 0 else 0
            gross_win = res_df[res_df['PnL']>0]['PnL'].sum()
            gross_loss = abs(res_df[res_df['PnL']<=0]['PnL'].sum())
            pf_all = gross_win/gross_loss if gross_loss > 0 else float('inf')
            expectancy_all = res_df['PnL'].mean()
            st.markdown(f"""
            <div style='display: flex; justify-content: space-around; background-color: #262730; padding: 20px; border-radius: 10px;'>
                <div style='text-align: center;'><div style='color: #aaa;'>総トレード数</div><div style='font-size: 24px;'>{count_all}回</div></div>
                <div style='text-align: center;'><div style='color: #aaa;'>勝率</div><div style='font-size: 24px;'>{win_rate_all:.1%}</div></div>
                <div style='text-align: center;'><div style='color: #aaa;'>PF</div><div style='font-size: 24px;'>{pf_all:.2f}</div></div>
                <div style='text-align: center;'><div style='color: #aaa;'>期待値</div><div style='font-size: 24px;'>{expectancy_all:.2%}</div></div>
            </div>
            """, unsafe_allow_html=True)
            st.divider()
            report = [f"Period: {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}\n"]
            for t in tickers:
                tdf = res_df[res_df['Ticker'] == t]
                if tdf.empty: continue
                wins = tdf[tdf['PnL'] > 0]; cnt = len(tdf); wr = len(wins)/cnt if cnt>0 else 0
                report.append(f">>> TICKER: {t} | {ticker_names.get(t, t)}\n勝率: {wr:.1%} | 期待値: {tdf['PnL'].mean():+.2%}\n")
            st.code("\n".join(report))

        with tab6:
            # 詳細ログに新しいカラムが含まれた状態で表示されます
            st.dataframe(res_df.sort_values('Entry', ascending=False), use_container_width=True)
