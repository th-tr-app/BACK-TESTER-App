import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from datetime import datetime, timedelta, time

# --- ページ設定 ---
st.set_page_config(page_title="BACK TESTER", page_icon="image_10.png", layout="wide")

# ヘッダーロゴ
st.logo("image_11.png", icon_image="image_10.png")

# タイトル
st.markdown("""
    <div style='margin-bottom: 20px;'>
        <h1 style='font-weight: 400; font-size: 46px; margin: 0; padding: 0;'>BACK TESTER</h1>
        <h3 style='font-weight: 300; font-size: 20px; margin: 0; padding: 0; color: #aaaaaa;'>DAY TRADING MANAGER｜ver 2.0</h3>
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

# ==========================================
# メイン画面：入力エリア
# ==========================================
ticker_input = st.text_input("銘柄コード (カンマ区切り)", "8267.T")
tickers = [t.strip() for t in ticker_input.split(",") if t.strip()]

main_btn = st.button("バックテスト実行", type="primary", key="main_btn")

st.divider()

# ==========================================
# サイドバー：パラメーター設定
# ==========================================
st.sidebar.header("⚙️ パラメーター設定")

days_back = st.sidebar.slider("過去何日分を取得", 10, 59, 59)

st.sidebar.subheader("⏰ 時間設定")
start_entry_time = st.sidebar.time_input("開始時間", time(9, 0), step=300)
end_entry_time = st.sidebar.time_input("終了時間", time(9, 15), step=300)

st.sidebar.write("")

# --- テクニカル指標 ---
st.sidebar.subheader("📉 エントリー条件")

use_vwap = st.sidebar.checkbox("**VWAP** より上でエントリー", value=True)
st.sidebar.write("")

use_ema = st.sidebar.checkbox("**EMA5** より上でエントリー", value=True)
st.sidebar.write("")

use_rsi = st.sidebar.checkbox("**RSI** が45以上or上向き", value=True)
st.sidebar.write("")

use_macd = st.sidebar.checkbox("**MACD** が上向き", value=True)
st.sidebar.write("")

st.sidebar.divider()

# ギャップ設定
gap_min = st.sidebar.slider("寄付ギャップダウン下限 (%)", -10.0, 0.0, -3.0, 0.1) / 100
gap_max = st.sidebar.slider("寄付ギャップアップ上限 (%)", -5.0, 5.0, 1.0, 0.1) / 100

st.sidebar.subheader("💰 決済ルール")
trailing_start = st.sidebar.number_input("トレイリング開始 (%)", 0.1, 5.0, 0.5, 0.1) / 100
trailing_pct = st.sidebar.number_input("下がったら成行注文 (%)", 0.1, 5.0, 0.2, 0.1) / 100
stop_loss = st.sidebar.number_input("損切り (%)", -5.0, -0.1, -0.7, 0.1) / 100

SLIPPAGE_PCT = 0.0003
FORCE_CLOSE_TIME = time(14, 55)

st.sidebar.write("")
st.sidebar.write("")

sidebar_btn = st.sidebar.button("バックテスト実行", type="primary", key="sidebar_btn")

# ==========================================
# バックテスト実行ロジック
# ==========================================
if main_btn or sidebar_btn:
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
                            cond_vwap = (row['Close'] > row['VWAP']) if use_vwap else True
                            cond_ema  = (row['Close'] > row['EMA5']) if use_ema else True
                            cond_rsi = ((row['RSI14'] > 45) and (row['RSI14'] > row['RSI14_Prev'])) if use_rsi else True
                            cond_macd = (row['MACD_H'] > row['MACD_H_Prev']) if use_macd else True
                            
                            if cond_vwap and cond_ema and cond_rsi and cond_macd:
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
        tab1, tab2, tab3, tab4 = st.tabs(["📊 サマリー", "📉 ギャップ分析", "🧐 VWAP分析", "📝 詳細ログ"])
        
        with tab1:
            # 1. 全体統計（HTML/CSSグリッドで表示）
            count_all = len(res_df)
            wins_all = res_df[res_df['PnL'] > 0]
            losses_all = res_df[res_df['PnL'] <= 0]
            win_rate_all = len(wins_all) / count_all if count_all > 0 else 0
            
            gross_win_all = wins_all['PnL'].sum()
            gross_loss_all = abs(losses_all['PnL'].sum())
            pf_all = gross_win_all / gross_loss_all if gross_loss_all > 0 else float('inf')
            expectancy_all = res_df['PnL'].mean()

            # ★修正: カスタムHTMLで表示（これによりスマホでの2列配置を強制）
            st.markdown(f"""
            <style>
            .metric-container {{
                display: grid;
                grid-template-columns: 1fr 1fr 1fr 1fr;
                gap: 10px;
                margin-bottom: 10px;
            }}
            /* スマホ（幅640px以下）では2列にする */
            @media (max-width: 640px) {{
                .metric-container {{
                    grid-template-columns: 1fr 1fr;
                }}
            }}
            .metric-box {{
                background-color: #262730;
                padding: 15px;
                border-radius: 8px;
                text-align: center;
                box-shadow: 0 1px 3px rgba(0,0,0,0.3);
            }}
            .metric-label {{
                font-size: 12px;
                color: #aaaaaa;
                margin-bottom: 5px;
            }}
            .metric-value {{
                font-size: 24px;
                font-weight: bold;
                color: #ffffff;
            }}
            </style>

            <div class="metric-container">
                <div class="metric-box">
                    <div class="metric-label">総トレード数</div>
                    <div class="metric-value">{count_all}回</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">勝率</div>
                    <div class="metric-value">{win_rate_all:.1%}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">PF</div>
                    <div class="metric-value">{pf_all:.2f}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">期待値</div>
                    <div class="metric-value">{expectancy_all:.2%}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.divider()

            # 2. テキストレポート作成
            report = []
            report.append("=================")
            report.append(" BACKTEST REPORT ")
            report.append("=================")
            report.append(f"\nPeriod: {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}")
            report.append("")
            
            for t in tickers:
                report.append(f"Testing {t}... ({days_back} days)")
            report.append("")

            for t in tickers:
                tdf = res_df[res_df['Ticker'] == t]
                if tdf.empty:
                    continue
                
                wins = tdf[tdf['PnL'] > 0]
                losses = tdf[tdf['PnL'] <= 0]
                
                count = len(tdf)
                win_rate = len(wins) / count if count > 0 else 0
                avg_win = wins['PnL'].mean() if not wins.empty else 0
                avg_loss = losses['PnL'].mean() if not losses.empty else 0
                
                gross_win = wins['PnL'].sum()
                gross_loss = abs(losses['PnL'].sum())
                pf = gross_win / gross_loss if gross_loss > 0 else float('inf')
                expectancy = tdf['PnL'].mean()

                report.append(f">>> TICKER: {t}")
                report.append(f"トレード数: {count} | 勝率: {win_rate:.1%} | 利益平均: {avg_win:.2%} | 損失平均: {avg_loss:.2%} | PF: {pf:.2f} | 期待値: {expectancy:.2%}")
                report.append("")

            # 3. テキストボックス
            report_text = "\n".join(report)
            st.caption("右上のコピーボタンで全文コピーできます↓")
            st.code(report_text, language="text")

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
