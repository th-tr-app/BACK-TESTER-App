
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from datetime import datetime, timedelta, time

# --- ページ設定 ---
st.set_page_config(page_title="朝スキャル バックテスト", layout="wide")
st.title("📊 BACK TESTER | Morning Ver (VWAP Analysis)")

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
start_h, start_m = st.sidebar.slider("開始時間", 9, 15, (9, 0))
end_h, end_m = st.sidebar.slider("終了時間", 9, 15, (9, 15))
start_entry_time = time(start_h, start_m)
end_entry_time = time(end_h, end_m)

st.sidebar.subheader("📉 エントリー条件")
# ★追加: VWAP条件のON/OFFスイッチ
use_vwap_filter = st.sidebar.checkbox("Close > VWAP を条件に含める", value=True)

gap_min = st.sidebar.slider("ギャップ下限 (%)", -10.0, 0.0, -3.0, 0.1) / 100
gap_max = st.sidebar.slider("ギャップ上限 (%)", -5.0, 5.0, 1.0, 0.1) / 100

st.sidebar.subheader("💰 決済ルール")
trailing_start = st.sidebar.number_input("トレール開始利益 (%)", 0.1, 5.0, 0.5, 0.1) / 100
trailing_pct = st.sidebar.number_input("トレール幅 (%)", 0.1, 5.0, 0.2, 0.1) / 100
stop_loss = st.sidebar.number_input("損切り (%)", -5.0, -0.1, -0.7, 0.1) / 100

SLIPPAGE_PCT = 0.0003
FORCE_CLOSE_TIME = time(14, 55)

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
            entry_vwap = 0 # ★エントリー時のVWAP記録用
            stop_p = 0
            trail_active = False
            trail_high = 0
            
            for ts, row in day.iterrows():
                cur_time = ts.time()
                if np.isnan(row['EMA5']) or np.isnan(row['RSI14']): continue
                
                if not in_pos:
                    if start_entry_time <= cur_time <= end_entry_time:
                        if gap_min <= gap_pct <= gap_max:
                            # VWAP条件の判定ロジック
                            vwap_condition = (row['Close'] > row['VWAP']) if use_vwap_filter else True
                            
                            if vwap_condition and (row['Close'] > row['EMA5']) and \
                               (row['RSI14'] > 45) and (row['RSI14'] > row['RSI14_Prev']) and \
                               (row['MACD_H'] > row['MACD_H_Prev']):
                                
                                entry_p = row['Close'] * (1 + SLIPPAGE_PCT)
                                entry_t = ts
                                entry_vwap = row['VWAP'] # ★VWAPを記録
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
                            'EntryVWAP': entry_vwap # ★結果に追加
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
        # タブで画面を切り替え
        tab1, tab2, tab3 = st.tabs(["📊 サマリー", "📊 VWAP分析", "📝 詳細ログ"])
        
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
            st.subheader("🧐 エントリー時のVWAP位置と勝率")
            
            # VWAP乖離率（%）を計算
            res_df['VWAP乖離(%)'] = ((res_df['In'] - res_df['EntryVWAP']) / res_df['EntryVWAP']) * 100
            
            # 乖離率を0.2%刻みなどでグループ化（ビン分割）
            # ビンの範囲を動的に設定（データの最小・最大に合わせて）
            min_dev = np.floor(res_df['VWAP乖離(%)'].min() * 2) / 2
            max_dev = np.ceil(res_df['VWAP乖離(%)'].max() * 2) / 2
            # 0.2%刻みのビンを作成
            bins = np.arange(min_dev, max_dev + 0.2, 0.2)
            
            # ビンごとの集計
            res_df['Range'] = pd.cut(res_df['VWAP乖離(%)'], bins=bins)
            
            # グループごとの勝率計算
            vwap_stats = res_df.groupby('Range', observed=True).agg(
                Count=('PnL', 'count'),
                WinRate=('PnL', lambda x: (x > 0).mean()),
                AvgPnL=('PnL', 'mean')
            ).reset_index()
            
            # 見やすいようにフォーマット
            vwap_stats['RangeLabel'] = vwap_stats['Range'].astype(str)
            
            # チャート表示（勝率）
            st.bar_chart(data=vwap_stats.set_index('RangeLabel')['WinRate'])
            
            st.write("詳細データ:")
            # データフレーム表示（数値整形）
            display_stats = vwap_stats.copy()
            display_stats['WinRate'] = display_stats['WinRate'].apply(lambda x: f"{x:.1%}")
            display_stats['AvgPnL'] = display_stats['AvgPnL'].apply(lambda x: f"{x:.2%}")
            st.dataframe(display_stats, use_container_width=True)
            
            st.info("💡 **見方**: 横軸は「エントリー価格がVWAPより何%上にいたか」を示します。プラスならVWAPより上、マイナスなら下です。どの位置でエントリーした時の勝率が高いかを確認できます。")

        with tab3:
            st.subheader("📝 トレード履歴")
            disp_df = res_df.copy().sort_values('Entry', ascending=False).reset_index(drop=True)
            disp_df['PnL'] = disp_df['PnL'].apply(lambda x: f"{x:.2%}")
            disp_df['VWAP乖離(%)'] = disp_df['VWAP乖離(%)'].apply(lambda x: f"{x:.2f}%")
            disp_df['Entry'] = disp_df['Entry'].dt.strftime('%Y-%m-%d %H:%M')
            disp_df['Exit'] = disp_df['Exit'].dt.strftime('%Y-%m-%d %H:%M')
            cols = ['Ticker', 'Entry', 'Exit', 'In', 'EntryVWAP', 'VWAP乖離(%)', 'Out', 'PnL', 'Reason']
            st.dataframe(disp_df[cols], use_container_width=True, hide_index=True)
