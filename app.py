import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from datetime import datetime, timedelta, time

# --- ページ設定 ---
st.set_page_config(page_title="BACK TESTER", page_icon="image_10.png", layout="wide")

# 横長のロゴ画像を指定
# 開いている時：横長ロゴ、閉じている時：小さいアイコン
st.logo("image_11.png", icon_image="image_10.png")

# font-weight: 200 (数字を小さくすると細くなります)
# font-size: 45px (数字を変えると大きさを自由に変えられます)
# タイトルを2行に分ける（メイン＋小見出し）
st.markdown("""
    <div style='margin-bottom: 20px;'>
        <h1 style='font-weight: 450; font-size: 45px; margin: 0; padding: 0;'>BACK TESTER</h1>
        <h3 style='font-weight: 250; font-size: 20px; margin: 0; padding: 0; color: #aaaaaa;'>DAY TRADING MANAGER｜ver 1.2</h3>
    </div>
    """, unsafe_allow_html=True)

# キャッシュ機能付きデータ取得
@st.cache_data(ttl=600)
def fetch_stock_data(ticker, start, end):
    try:
        df = yf.download(ticker, start=start, end=end, interval="5m", progress=False, multi_level_index=False, auto_adjust=False)
        return df
    except Exception:
        return pd.DataFrame()

# --- サイドバー ---
st.sidebar.header("⚙️ パラメーター設定")

ticker_input = st.sidebar.text_input("銘柄コード (カンマ区切り)", "8267.T")
tickers = [t.strip() for t in ticker_input.split(",") if t.strip()]

days_back = st.sidebar.slider("過去何日分を取得", 10, 59, 59)

st.sidebar.subheader("⏰ 時間設定")
# 自由入力形式に変更（デフォルトは9:00〜9:15）
# step=300 (秒) で5分刻みに設定
start_entry_time = st.sidebar.time_input("開始時間", time(9, 0), step=300)
end_entry_time = st.sidebar.time_input("終了時間", time(9, 15), step=300)

# ★追加: スマホ誤操作防止の隙間
st.sidebar.write("")

st.sidebar.subheader("📉 エントリー条件")
use_vwap_filter = st.sidebar.checkbox("VWAPより上でエントリー", value=True)

# ★追加: スマホ誤操作防止の隙間
st.sidebar.write("")

gap_min = st.sidebar.slider("寄付ギャップダウン下限 (%)", -10.0, 0.0, -3.0, 0.1) / 100
gap_max = st.sidebar.slider("寄付ギャップアップ上限 (%)", -5.0, 5.0, 1.0, 0.1) / 100

st.sidebar.subheader("💰 決済ルール")
trailing_start = st.sidebar.number_input("トレイリング開始 (%)", 0.1, 5.0, 0.5, 0.1) / 100
trailing_pct = st.sidebar.number_input("下がったら成行注文 (%)", 0.1, 5.0, 0.2, 0.1) / 100
stop_loss = st.sidebar.number_input("損切り (%)", -5.0, -0.1, -0.7, 0.1) / 100

SLIPPAGE_PCT = 0.0003
FORCE_CLOSE_TIME = time(14, 55)

# ★追加: スマホ誤操作防止の隙間
st.sidebar.write("")

# --- 実行ボタン ---
if st.sidebar.button("バックテスト実行", type="primary"):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    all_trades = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker in enumerate(tickers):
        status_text.text(f"Testing {ticker}...")
        progress_bar.progress((i + 1) / len(tickers))
        
        df = fetch_stock_data(ticker, start_date, end_date)
        
        if df.empty: continue
        
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        
        if df.index.tzinfo is None:
            df.index = df.index.tz_localize('UTC').tz_convert('Asia/Tokyo')
        else:
            df.index = df.index.tz_convert('Asia/Tokyo')

        df['EMA5'] = EMAIndicator(close=df['Close'], window=5).ema_indicator()
        macd = MACD(close=df['Close'])
        df['MACD_H'] = macd.macd_diff()
        df['MACD_H_Prev'] = df['MACD_H'].shift(1)
        rsi = RSIIndicator(close=df['Close'], window=14)
        df['RSI14'] = rsi.rsi()
        df['RSI14_Prev'] = df['RSI14'].shift(1)
        
        def compute_vwap(d):
            tp = (d['High'] + d['Low'] + d['Close']) / 3
            return ((tp * d['Volume']).cumsum() / d['Volume'].cumsum().replace(0, np.nan)).ffill()

        unique_dates = np.unique(df.index.date)
        
        for date in unique_dates:
            day = df[df.index.date == date].copy().between_time('09:00', '15:00')
            if day.empty: continue
            day['VWAP'] = compute_vwap(day)
            
            past = df[df.index.date < date]
            if past.empty: continue
            prev_close = past['Close'].iloc[-1]
            gap_pct = (day.iloc[0]['Open'] - prev_close) / prev_close
            
            in_pos = False
            entry_p = 0
            entry_t = None
            entry_vwap = 0
            stop_p = 0
            trail_active = False
            trail_high = 0
            
            for ts, row in day.iterrows():
                cur_time = ts.time()
                if np.isnan(row['EMA5']) or np.isnan(row['RSI14']): continue
                
                if not in_pos:
                    if start_entry_time <= cur_time <= end_entry_time:
                        if gap_min <= gap_pct <= gap_max:
                            # VWAP条件
                            vwap_condition = (row['Close'] > row['VWAP']) if use_vwap_filter else True
                            
                            if vwap_condition and (row['Close'] > row['EMA5']) and \
                               (row['RSI14'] > 45) and (row['RSI14'] > row['RSI14_Prev']) and \
                               (row['MACD_H'] > row['MACD_H_Prev']):
                                
                                entry_p = row['Close'] * (1 + SLIPPAGE_PCT)
                                entry_t = ts
                                entry_vwap = row['VWAP']
                                in_pos = True
                                stop_p = entry_p * (1 + stop_loss)
                                trail_active = False
                                trail_high = row['High']
                else:
                    if row['High'] > trail_high: trail_high = row['High']
                    if not trail_active and (trail_high >= entry_p * (1 + trailing_start)):
                        trail_active = True
                    
                    exit_p = None
                    reason = ""
                    
                    if trail_active and (row['Low'] <= trail_high * (1 - trailing_pct)):
                        exit_p = trail_high * (1 - trailing_pct) * (1 - SLIPPAGE_PCT)
                        reason = "Trailing"
                    elif row['Low'] <= stop_p:
                        exit_p = stop_p * (1 - SLIPPAGE_PCT)
                        reason = "Stop Loss"
                    elif cur_time >= FORCE_CLOSE_TIME:
                        exit_p = row['Close'] * (1 - SLIPPAGE_PCT)
                        reason = "Time Up"
                        
                    if exit_p:
                        pnl = (exit_p - entry_p) / entry_p
                        all_trades.append({
                            'Ticker': ticker, 
                            'Entry': entry_t, 
                            'Exit': ts,
                            'In': int(entry_p), 
                            'Out': int(exit_p),
                            'PnL': pnl, 
                            'Reason': reason,
                            'EntryVWAP': entry_vwap,
                            'Gap(%)': gap_pct * 100
                        })
                        in_pos = False
                        break
                        
    progress_bar.empty()
    status_text.empty()

    # --- 結果表示 ---
    res_df = pd.DataFrame(all_trades)
    
    if res_df.empty:
        st.warning("条件に合うトレードはありませんでした。")
    else:
        # タブ設定
        tab1, tab2, tab3, tab4 = st.tabs(["📊 サマリー", "📉 ギャップ分析", "🧐 VWAP分析", "📝 詳細ログ"])
        
        with tab1:
            wins = res_df[res_df['PnL'] > 0]
            losses = res_df[res_df['PnL'] <= 0]
            win_rate = len(wins) / len(res_df)
            pf = wins['PnL'].sum() / -losses['PnL'].sum() if not losses.empty else float('inf')
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("総トレード数", f"{len(res_df)}回")
            c2.metric("勝率", f"{win_rate:.1%}")
            c3.metric("PF", f"{pf:.2f}")
            c4.metric("期待値", f"{res_df['PnL'].mean():.2%}")
            
            st.divider()
            st.subheader("📈 資産推移チャート")
            res_df['Cumulative PnL'] = res_df['PnL'].cumsum()
            chart_data = res_df.set_index('Exit')['Cumulative PnL']
            st.line_chart(chart_data)

        with tab2:
            st.subheader("📉 始値ギャップ方向と成績")
            res_df['GapDir'] = res_df['Gap(%)'].apply(lambda x: 'Gap Up 📈' if x > 0 else ('Gap Down 📉' if x < 0 else 'Flat ➖'))
            
            gap_dir_stats = res_df.groupby('GapDir').agg(
                Count=('PnL', 'count'),
                WinRate=('PnL', lambda x: (x > 0).mean()),
                AvgPnL=('PnL', 'mean')
            ).reset_index()
            
            gap_dir_stats['WinRate'] = gap_dir_stats['WinRate'].apply(lambda x: f"{x:.1%}")
            gap_dir_stats['AvgPnL'] = gap_dir_stats['AvgPnL'].apply(lambda x: f"{x:.2%}")
            gap_dir_stats.columns = ['方向', 'トレード数', '勝率', '平均損益']
            st.table(gap_dir_stats)
            
            st.divider()
            st.subheader("📊 詳細なギャップ幅ごとの勝率")
            
            min_g = np.floor(res_df['Gap(%)'].min())
            max_g = np.ceil(res_df['Gap(%)'].max())
            if np.isnan(min_g): min_g = -3.0
            if np.isnan(max_g): max_g = 1.0
            
            bins_g = np.arange(min_g, max_g + 0.5, 0.5)
            res_df['GapRange'] = pd.cut(res_df['Gap(%)'], bins=bins_g)
            
            gap_range_stats = res_df.groupby('GapRange', observed=True).agg(
                Count=('PnL', 'count'),
                WinRate=('PnL', lambda x: (x > 0).mean()),
                AvgPnL=('PnL', 'mean')
            ).reset_index()
            
            gap_range_stats['RangeLabel'] = gap_range_stats['GapRange'].astype(str)
            st.bar_chart(data=gap_range_stats.set_index('RangeLabel')['WinRate'])
            
            disp_gap = gap_range_stats[['RangeLabel', 'Count', 'WinRate', 'AvgPnL']].copy()
            disp_gap['WinRate'] = disp_gap['WinRate'].apply(lambda x: f"{x:.1%}")
            disp_gap['AvgPnL'] = disp_gap['AvgPnL'].apply(lambda x: f"{x:.2%}")
            disp_gap.columns = ['ギャップ幅(%)', 'トレード数', '勝率', '平均損益']
            st.dataframe(disp_gap, use_container_width=True, hide_index=True)

        with tab3:
            st.subheader("🧐 エントリー時のVWAP位置と勝率")
            res_df['VWAP乖離(%)'] = ((res_df['In'] - res_df['EntryVWAP']) / res_df['EntryVWAP']) * 100
            
            min_dev = np.floor(res_df['VWAP乖離(%)'].min() * 2) / 2
            max_dev = np.ceil(res_df['VWAP乖離(%)'].max() * 2) / 2
            if np.isnan(min_dev): min_dev = -1.0
            if np.isnan(max_dev): max_dev = 1.0
            
            bins = np.arange(min_dev, max_dev + 0.2, 0.2)
            res_df['Range'] = pd.cut(res_df['VWAP乖離(%)'], bins=bins)
            
            vwap_stats = res_df.groupby('Range', observed=True).agg(
                Count=('PnL', 'count'),
                WinRate=('PnL', lambda x: (x > 0).mean()),
                AvgPnL=('PnL', 'mean')
            ).reset_index()
            
            vwap_stats['RangeLabel'] = vwap_stats['Range'].astype(str)
            st.bar_chart(data=vwap_stats.set_index('RangeLabel')['WinRate'])
            
            display_stats = vwap_stats[['RangeLabel', 'Count', 'WinRate', 'AvgPnL']].copy()
            display_stats['WinRate'] = display_stats['WinRate'].apply(lambda x: f"{x:.1%}")
            display_stats['AvgPnL'] = display_stats['AvgPnL'].apply(lambda x: f"{x:.2%}")
            display_stats.columns = ['乖離率レンジ', 'トレード数', '勝率', '平均損益']
            st.dataframe(display_stats, use_container_width=True, hide_index=True)

        with tab4:
            st.subheader("📝 トレード履歴")
            disp_df = res_df.copy().sort_values('Entry', ascending=False).reset_index(drop=True)
            disp_df['PnL'] = disp_df['PnL'].apply(lambda x: f"{x:.2%}")
            disp_df['Gap(%)'] = disp_df['Gap(%)'].apply(lambda x: f"{x:.2f}%")
            disp_df['VWAP乖離(%)'] = disp_df['VWAP乖離(%)'].apply(lambda x: f"{x:.2f}%")
            disp_df['Entry'] = disp_df['Entry'].dt.strftime('%Y-%m-%d %H:%M')
            disp_df['Exit'] = disp_df['Exit'].dt.strftime('%Y-%m-%d %H:%M')
            cols = ['Ticker', 'Entry', 'Gap(%)', 'In', 'EntryVWAP', 'VWAP乖離(%)', 'Out', 'PnL', 'Reason']
            st.dataframe(disp_df[cols], use_container_width=True, hide_index=True)
