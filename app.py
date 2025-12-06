import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from datetime import datetime, timedelta, time

# --- ページ設定 ---
st.set_page_config(page_title="BACK TESTER", page_icon="image_10.png", layout="wide")
st.logo("image_11.png", icon_image="image_10.png")

# CSS設定
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
        <h3 style='font-weight: 300; font-size: 20px; margin: 0; padding: 0; color: #aaaaaa;'>DAY TRADING MANAGER｜ver 5.1 Final Fix</h3>
    </div>
    """, unsafe_allow_html=True)

# --- 判定ロジック ---
def get_trade_pattern(row, gap_pct):
    check_vwap = row['VWAP'] if pd.notna(row['VWAP']) else row['Close']
    if gap_pct <= -0.005:
        if (row['Close'] > check_vwap) and (row['RSI14'] <= 55): return "A：ＧＤ反転狙い"
    elif gap_pct >= 0.003:
        if (row['Close'] > check_vwap) and (row['RSI14'] >= 60): return "D：ＧＵ上昇継続"
    elif (row['Close'] > check_vwap * 1.001) and (row['RSI14'] >= 65): return "C：初動ブレイク"
    elif (row['Close'] > row['EMA5']) and (50 <= row['RSI14'] < 65): return "B：押し目上昇型"
    return "E：他のパターン"

# データ取得（5分足）
@st.cache_data(ttl=600)
def fetch_intraday(ticker, start, end):
    try:
        # 土日などのズレ防止のため、終了日を明示的に今日にする
        df = yf.download(ticker, start=start, end=datetime.now(), interval="5m", progress=False, multi_level_index=False, auto_adjust=False)
        return df
    except: return pd.DataFrame()

# ★修正: 前日終値マップ作成（最強版：asof検索用）
@st.cache_data(ttl=3600)
def fetch_daily_data_strong(ticker, start):
    try:
        # 十分過去から取得
        d_start = start - timedelta(days=30)
        df = yf.download(ticker, start=d_start, end=datetime.now(), interval="1d", progress=False, multi_level_index=False, auto_adjust=False)
        
        if df.empty: return pd.Series(dtype=float)
        
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        # タイムゾーンを消して純粋な日付型にする（これがズレ防止の鍵）
        df.index = pd.to_datetime(df.index).tz_localize(None)
        
        # 終値だけのSeriesを返す
        return df['Close']
    except: return pd.Series(dtype=float)

# UI
ticker_input = st.text_input("銘柄コード (カンマ区切り)", "8267.T")
tickers = [t.strip() for t in ticker_input.split(",") if t.strip()]
main_btn = st.button("バックテスト実行", type="primary", key="main_btn")
st.divider()

st.sidebar.header("⚙️ パラメーター設定")
days_back = st.sidebar.slider("過去何日分を取得", 10, 59, 59)
st.sidebar.subheader("⏰ 時間設定")
start_entry_time = st.sidebar.time_input("開始時間", time(9, 0), step=300)
end_entry_time = st.sidebar.time_input("終了時間", time(9, 15), step=300)
st.sidebar.write("")
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

if main_btn or sidebar_btn:
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    all_trades = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker in enumerate(tickers):
        status_text.text(f"Testing {ticker}...")
        progress_bar.progress((i + 1) / len(tickers))
        
        df = fetch_intraday(ticker, start_date, end_date)
        # ★日足の全データをSeriesとして取得
        daily_close_series = fetch_daily_data_strong(ticker, start_date)
        
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
            cum_vp = (tp * d['Volume']).cumsum()
            cum_vol = d['Volume'].cumsum().replace(0, np.nan)
            return (cum_vp / cum_vol).ffill()

        unique_dates = np.unique(df.index.date)
        
        for date in unique_dates:
            day = df[df.index.date == date].copy().between_time('09:00', '15:00')
            if day.empty: continue
            day['VWAP'] = compute_vwap(day)
            
            # ★修正: asofを使って「この日より前にある一番新しい日足」を確実に取得
            # これにより、土日だろうが祝日だろうが、絶対に「直近の営業日」が取れる
            try:
                target_date = pd.Timestamp(date)
                # dateより厳密に小さい日付の中で最大のものを探す
                prev_close_idx = daily_close_series.index[daily_close_series.index < target_date].max()
                
                if pd.isna(prev_close_idx):
                    continue # 前日データなし
                
                prev_close = daily_close_series[prev_close_idx]
            except:
                continue

            gap_pct = (day.iloc[0]['Open'] - prev_close) / prev_close
            
            in_pos = False
            entry_p = 0
            entry_t = None
            entry_vwap = 0
            stop_p = 0
            trail_active = False
            trail_high = 0
            pattern_type = "E：他のパターン"
            
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
                                entry_p = row['Close'] * (1 + SLIPPAGE_PCT)
                                entry_t = ts
                                entry_vwap = row['VWAP']
                                in_pos = True
                                stop_p = entry_p * (1 + stop_loss)
                                trail_active = False
                                trail_high = row['High']
                                pattern_type = get_trade_pattern(row, gap_pct)
                else:
                    if row['High'] > trail_high: trail_high = row['High']
                    if not trail_active and (trail_high >= entry_p * (1 + trailing_start)): trail_active = True
                    
                    exit_p = None
                    reason = ""
                    if trail_active and (row['Low'] <= trail_high * (1 - trailing_pct)):
                        exit_p = trail_high * (1 - trailing_pct) * (1 - SLIPPAGE_PCT)
                        reason = "トレーリング"
                    elif row['Low'] <= stop_p:
                        exit_p = stop_p * (1 - SLIPPAGE_PCT)
                        reason = "損切り"
                    elif cur_time >= FORCE_CLOSE_TIME:
                        exit_p = row['Close'] * (1 - SLIPPAGE_PCT)
                        reason = "時間切れ"
                        
                    if exit_p:
                        pnl = (exit_p - entry_p) / entry_p
                        all_trades.append({
                            'Ticker': ticker, 'Entry': entry_t, 'Exit': ts,
                            'In': int(entry_p), 'Out': int(exit_p),
                            'PnL': pnl, 'Reason': reason,
                            'EntryVWAP': entry_vwap, 'Gap(%)': gap_pct * 100,
                            'Pattern': pattern_type
                        })
                        in_pos = False
                        break
                        
    progress_bar.empty()
    status_text.empty()

    res_df = pd.DataFrame(all_trades)
    if res_df.empty:
        st.warning("条件に合うトレードはありませんでした。")
    else:
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 サマリー", "🤖 勝ちパターン", "📉 ギャップ分析", "🧐 VWAP分析", "🕒 時間分析", "📝 詳細ログ"])
        
        with tab1:
            count_all = len(res_df)
            wins_all = res_df[res_df['PnL'] > 0]
            losses_all = res_df[res_df['PnL'] <= 0]
            win_rate_all = len(wins_all) / count_all if count_all > 0 else 0
            gross_win = res_df[res_df['PnL']>0]['PnL'].sum()
            gross_loss = abs(res_df[res_df['PnL']<=0]['PnL'].sum())
            pf_all = gross_win/gross_loss if gross_loss > 0 else float('inf')
            
            st.markdown(f"""
            <style>
            .metric-container {{ display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 10px; margin-bottom: 10px; }}
            @media (max-width: 640px) {{ .metric-container {{ grid-template-columns: 1fr 1fr; }} }}
            .metric-box {{ background-color: #262730; padding: 15px; border-radius: 8px; text-align: center; }}
            .metric-label {{ font-size: 12px; color: #aaaaaa; }}
            .metric-value {{ font-size: 24px; font-weight: bold; color: #ffffff; }}
            </style>
            <div class="metric-container">
                <div class="metric-box"><div class="metric-label">総トレード数</div><div class="metric-value">{count_all}回</div></div>
                <div class="metric-box"><div class="metric-label">勝率</div><div class="metric-value">{win_rate_all:.1%}</div></div>
                <div class="metric-box"><div class="metric-label">PF（総利益 ÷ 総損失）</div><div class="metric-value">{pf_all:.2f}</div></div>
                <div class="metric-box"><div class="metric-label">期待値</div><div class="metric-value">{res_df['PnL'].mean():.2%}</div></div>
            </div>
            """, unsafe_allow_html=True)
            st.divider()
            
            # レポート作成
            report = []
            report.append("=================\n BACKTEST REPORT \n=================")
            report.append(f"\nPeriod: {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}\n")
            for t in tickers:
                tdf = res_df[res_df['Ticker'] == t]
                if tdf.empty: continue
                wins = tdf[tdf['PnL'] > 0]
                losses = tdf[tdf['PnL'] <= 0]
                cnt = len(tdf); wr = len(wins)/cnt if cnt>0 else 0
                avg_win = wins['PnL'].mean() if not wins.empty else 0
                avg_loss = losses['PnL'].mean() if not losses.empty else 0
                pf = wins['PnL'].sum()/abs(losses['PnL'].sum()) if losses['PnL'].sum()!=0 else float('inf')
                report.append(f">>> TICKER: {t}")
                report.append(f"トレード数: {cnt} | 勝率: {wr:.1%} | 利益平均: {avg_win:+.2%} | 損失平均: {avg_loss:+.2%} | PF: {pf:.2f} | 期待値: {tdf['PnL'].mean():+.2%}\n")
            st.caption("右上のコピーボタンで全文コピーできます↓")
            st.code("\n".join(report), language="text")

        with tab2: # 勝ちパターン（ver 2.9方式）
            st.markdown("### 🤖 勝ちパターン分析")
            st.divider()
            for t in tickers:
                tdf = res_df[res_df['Ticker'] == t].copy()
                if tdf.empty: continue
                st.markdown(f"#### [{t}]")
                pat_stats = tdf.groupby('Pattern')['PnL'].agg(['count', lambda x: (x>0).mean(), 'mean']).reset_index()
                pat_stats.columns = ['パターン', 'トレード数', '勝率', '平均損益']
                pat_stats['勝率'] = pat_stats['勝率'].apply(lambda x: f"{x:.1%}")
                pat_stats['平均損益'] = pat_stats['平均損益'].apply(lambda x: f"{x:+.2%}")
                pat_stats['トレード数'] = pat_stats['トレード数'].astype(str)
                st.dataframe(pat_stats.style.set_properties(**{'text-align': 'left'}), hide_index=True, use_container_width=True)
                
                min_g = np.floor(tdf['Gap(%)'].min()); max_g = np.ceil(tdf['Gap(%)'].max())
                if np.isnan(min_g): min_g=-3.0; max_g=1.0
                bins_g = np.arange(min_g, max_g+0.5, 0.5)
                tdf['GapRange'] = pd.cut(tdf['Gap(%)'], bins=bins_g)
                gap_stats = tdf.groupby('GapRange', observed=True)['PnL'].agg(['count', lambda x: (x>0).mean()]).reset_index()
                gap_valid = gap_stats[gap_stats['count']>=2]
                if gap_valid.empty: gap_valid = gap_stats
                best_g = gap_valid.loc[gap_valid['<lambda_0>'].idxmax()]
                
                tdf['VWAP_Diff'] = ((tdf['In'] - tdf['EntryVWAP']) / tdf['EntryVWAP']) * 100
                min_v = np.floor(tdf['VWAP_Diff'].min()*2)/2; max_v = np.ceil(tdf['VWAP_Diff'].max()*2)/2
                if np.isnan(min_v): min_v=-1.0; max_v=1.0
                bins_v = np.arange(min_v, max_v+0.2, 0.2)
                tdf['VwapRange'] = pd.cut(tdf['VWAP_Diff'], bins=bins_v)
                vwap_valid = tdf.groupby('VwapRange', observed=True)['PnL'].agg(['count', lambda x: (x>0).mean()]).reset_index()
                vwap_valid = vwap_valid[vwap_valid['count']>=2]
                if vwap_valid.empty: vwap_valid = vwap_stats
                best_v = vwap_valid.loc[vwap_valid['<lambda_0>'].idxmax()]
                
                def get_time_range(dt): return f"{dt.strftime('%H:%M')}～{(dt + timedelta(minutes=5)).strftime('%H:%M')}"
                tdf['TimeRange'] = tdf['Entry'].apply(get_time_range)
                time_valid = tdf.groupby('TimeRange')['PnL'].agg(['count', lambda x: (x>0).mean()]).reset_index()
                time_valid = time_valid[time_valid['count']>=2]
                if time_valid.empty: time_valid = time_stats
                best_t = time_valid.loc[time_valid['<lambda_0>'].idxmax()]
                
                gap_txt = "ギャップアップ" if best_g['GapRange'].left >= 0 else "ギャップダウン"
                st.info(f"**🏆 最高勝率パターン**\n\n"
                        f"最も勝率が高かったのは、**{gap_txt} ({best_g['GapRange'].left:.1f}% ～ {best_g['GapRange'].right:.1f}%)** スタートで、"
                        f"VWAPから **{best_v['VwapRange'].left:.1f}% ～ {best_v['VwapRange'].right:.1f}%** の位置にある時、"
                        f"**{best_t['TimeRange']}** にエントリーするパターンです。\n\n"
                        f"(Gap勝率: {best_g['<lambda_0>']:.1%} / VWAP勝率: {best_v['<lambda_0>']:.1%} / 時間勝率: {best_t['<lambda_0>']:.1%})")
                st.divider()

        # 3-6. グラフ等はver 3.8と同様のため省略せず実装
        with tab3:
            # ギャップ分析（省略なし）
            for t in tickers:
                tdf = res_df[res_df['Ticker'] == t].copy()
                if tdf.empty: continue
                st.markdown(f"### [{t}]")
                st.markdown("##### 始値ギャップ方向と成績")
                tdf['GapDir'] = tdf['Gap(%)'].apply(lambda x: 'ギャップアップ' if x > 0 else ('ギャップダウン' if x < 0 else 'フラット'))
                gap_dir_stats = tdf.groupby('GapDir').agg(Count=('PnL', 'count'), WinRate=('PnL', lambda x: (x > 0).mean()), AvgPnL=('PnL', 'mean')).reset_index()
                gap_dir_stats['WinRate'] = gap_dir_stats['WinRate'].apply(lambda x: f"{x:.1%}")
                gap_dir_stats['AvgPnL'] = gap_dir_stats['AvgPnL'].apply(lambda x: f"{x:+.2%}")
                gap_dir_stats['Count'] = gap_dir_stats['Count'].astype(str)
                gap_dir_stats.columns = ['方向', 'トレード数', '勝率', '平均損益']
                st.dataframe(gap_dir_stats.style.set_properties(**{'text-align': 'left'}), hide_index=True, use_container_width=True)
                st.markdown("##### ギャップ幅ごとの勝率")
                min_g = np.floor(tdf['Gap(%)'].min()); max_g = np.ceil(tdf['Gap(%)'].max())
                if np.isnan(min_g): min_g = -3.0; max_g = 1.0
                bins_g = np.arange(min_g, max_g + 0.5, 0.5)
                tdf['GapRange'] = pd.cut(tdf['Gap(%)'], bins=bins_g)
                gap_range_stats = tdf.groupby('GapRange', observed=True).agg(Count=('PnL', 'count'), WinRate=('PnL', lambda x: (x > 0).mean()), AvgPnL=('PnL', 'mean')).reset_index()
                def format_interval(i): return f"{i.left:.1f}% ～ {i.right:.1f}%"
                gap_range_stats['RangeLabel'] = gap_range_stats['GapRange'].apply(format_interval)
                disp_gap = gap_range_stats[['RangeLabel', 'Count', 'WinRate', 'AvgPnL']].copy()
                disp_gap['WinRate'] = disp_gap['WinRate'].apply(lambda x: f"{x:.1%}")
                disp_gap['AvgPnL'] = disp_gap['AvgPnL'].apply(lambda x: f"{x:+.2%}")
                disp_gap['Count'] = disp_gap['Count'].astype(str)
                disp_gap.columns = ['ギャップ幅', 'トレード数', '勝率', '平均損益']
                st.dataframe(disp_gap.style.set_properties(**{'text-align': 'left'}), hide_index=True, use_container_width=True)
                st.divider()

        with tab4:
            # VWAP分析
             for t in tickers:
                tdf = res_df[res_df['Ticker'] == t].copy()
                if tdf.empty: continue
                st.markdown(f"### [{t}]")
                st.markdown("##### エントリー時のVWAPと勝率")
                tdf['VWAP乖離(%)'] = ((tdf['In'] - tdf['EntryVWAP']) / tdf['EntryVWAP']) * 100
                min_dev = np.floor(tdf['VWAP乖離(%)'].min() * 2) / 2
                max_dev = np.ceil(tdf['VWAP乖離(%)'].max() * 2) / 2
                if np.isnan(min_dev): min_dev = -1.0; max_dev = 1.0
                bins = np.arange(min_dev, max_dev + 0.2, 0.2)
                tdf['Range'] = pd.cut(tdf['VWAP乖離(%)'], bins=bins)
                vwap_stats = tdf.groupby('Range', observed=True).agg(Count=('PnL', 'count'), WinRate=('PnL', lambda x: (x > 0).mean()), AvgPnL=('PnL', 'mean')).reset_index()
                def format_vwap_interval(i): return f"{i.left:.1f}% ～ {i.right:.1f}%"
                vwap_stats['RangeLabel'] = vwap_stats['Range'].apply(format_vwap_interval)
                display_stats = vwap_stats[['RangeLabel', 'Count', 'WinRate', 'AvgPnL']].copy()
                display_stats['WinRate'] = display_stats['WinRate'].apply(lambda x: f"{x:.1%}")
                display_stats['AvgPnL'] = display_stats['AvgPnL'].apply(lambda x: f"{x:+.2%}")
                display_stats['Count'] = display_stats['Count'].astype(str)
                display_stats.columns = ['乖離率レンジ', 'トレード数', '勝率', '平均損益']
                st.dataframe(display_stats.style.set_properties(**{'text-align': 'left'}), hide_index=True, use_container_width=True)
                st.divider()

        with tab5:
            # 時間分析
            for t in tickers:
                tdf = res_df[res_df['Ticker'] == t].copy()
                if tdf.empty: continue
                st.markdown(f"### [{t}]")
                st.markdown("##### エントリー時間帯ごとの勝率")
                def get_time_range(dt): return f"{dt.strftime('%H:%M')}～{(dt + timedelta(minutes=5)).strftime('%H:%M')}"
                tdf['TimeRange'] = tdf['Entry'].apply(get_time_range)
                time_stats = tdf.groupby('TimeRange')['PnL'].agg(['count', lambda x: (x>0).mean(), 'mean']).reset_index()
                time_disp = time_stats.copy()
                time_disp['WinRate'] = time_disp['<lambda_0>'].apply(lambda x: f"{x:.1%}")
                time_disp['AvgPnL'] = time_disp['mean'].apply(lambda x: f"{x:+.2%}")
                time_disp['Count'] = time_disp['count'].astype(str)
                time_disp = time_disp[['TimeRange', 'Count', 'WinRate', 'AvgPnL']]
                time_disp.columns = ['時間帯', 'トレード数', '勝率', '平均損益']
                st.dataframe(time_disp.style.set_properties(**{'text-align': 'left'}), hide_index=True, use_container_width=True)
                st.divider()

        with tab6:
            # 詳細ログ
            log_report = []
            for t in tickers:
                tdf = res_df[res_df['Ticker'] == t].copy().sort_values('Entry', ascending=False).reset_index(drop=True)
                if tdf.empty: continue
                tdf['VWAP乖離(%)'] = ((tdf['In'] - tdf['EntryVWAP']) / tdf['EntryVWAP']) * 100
                log_report.append(f"[{t}] 取引履歴")
                log_report.append("-" * 80)
                for i, row in tdf.iterrows():
                    entry_str = row['Entry'].strftime('%Y-%m-%d %H:%M')
                    if pd.notna(row['EntryVWAP']):
                        vwap_val = int(round(row['EntryVWAP']))
                        vwap_dev = f"{row['VWAP乖離(%)']:+.2f}%"
                    else:
                        vwap_val = "-"; vwap_dev = "-"
                    line = f"Entry: {entry_str} | Type: {row['Pattern']} | PnL: {row['PnL']:+.2%} | Gap: {row['Gap(%)']:+.2f}% | VWAP: {vwap_val} (乖離 {vwap_dev}) | Reason: {row['Reason']}"
                    log_report.append(line)
                log_report.append("\n")
            st.caption("右上のコピーボタンで全文コピーできます↓")
            st.code("\n".join(log_report), language="text")
