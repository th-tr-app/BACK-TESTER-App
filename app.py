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

# --- 銘柄名マッピング ---
TICKER_NAME_MAP = {
    # 水産・食品
    "1332.T": "ニッスイ", "2002.T": "日清粉G", "2269.T": "明治HD", "2282.T": "日本ハム", "2501.T": "サッポロHD",
    "2502.T": "アサヒG", "2503.T": "キリンHD", "2801.T": "キッコーマン", "2802.T": "味の素", "2871.T": "ニチレイ", "2914.T": "JT",
    # 繊維・化学
    "3101.T": "東洋紡", "3103.T": "ユニチカ", "3401.T": "帝人", "3402.T": "東レ", "3861.T": "王子HD", "3863.T": "日本製紙",
    "4004.T": "レゾナック", "4005.T": "住友化学", "4021.T": "日産化学", "4042.T": "東ソー", "4043.T": "トクヤマ",
    "4061.T": "デンカ", "4063.T": "信越化学", "4151.T": "協和キリン", "4183.T": "三井化学", "4188.T": "三菱ケミＧ",
    "4208.T": "ＵＢＥ", "4452.T": "花王", "4901.T": "富士フイルム", "4911.T": "資生堂",
    "4502.T": "武田薬品", "4503.T": "アステラス製薬", "4506.T": "住友ファーマ", "4507.T": "塩野義製薬", "4519.T": "中外製薬",
    "4523.T": "エーザイ", "4543.T": "テルモ", "4568.T": "第一三共", "4578.T": "大塚ＨＤ",
    # 石油・ゴム・金属
    "5019.T": "出光興産", "5020.T": "ＥＮＥＯＳ", "5101.T": "横浜ゴム", "5108.T": "ブリヂストン",
    "5201.T": "ＡＧＣ", "5202.T": "日本板硝子", "5232.T": "住友大阪セメント", "5233.T": "太平洋セメント", "5301.T": "東海カーボン",
    "5332.T": "ＴＯＴＯ", "5333.T": "日本碍子", "5401.T": "日本製鉄", "5406.T": "神戸製鋼所", "5411.T": "ＪＦＥ",
    "5541.T": "大平洋金属", "5631.T": "日本製鋼所", "5706.T": "三井金属", "5711.T": "三菱マテリアル", "5713.T": "住友金属鉱山",
    "5714.T": "ＤＯＷＡ", "5801.T": "古河電気工業", "5802.T": "住友電気工業", "5803.T": "フジクラ",
    # 機械・電機
    "6098.T": "リクルート", "6103.T": "オークマ", "6113.T": "アマダ", "6146.T": "ディスコ", "6273.T": "ＳＭＣ",
    "6301.T": "小松製作所", "6302.T": "住友重機械", "6305.T": "日立建機", "6326.T": "クボタ", "6361.T": "荏原製作所",
    "6367.T": "ダイキン工業", "6471.T": "日本精工", "6472.T": "ＮＴＮ", "6473.T": "ジェイテクト", "6479.T": "ミネベアミツミ",
    "6501.T": "日立", "6503.T": "三菱電機", "6504.T": "富士電機", "6506.T": "安川電機", "6594.T": "ニデック",
    "6645.T": "オムロン", "6701.T": "日本電気", "6702.T": "富士通", "6723.T": "ルネサス", "6724.T": "セイコーエプソン",
    "6752.T": "パナソニック", "6753.T": "シャープ", "6758.T": "ソニーグループ", "6762.T": "ＴＤＫ", "6770.T": "アルプスアルパイン",
    "6841.T": "横河電機", "6857.T": "アドバンテスト", "6902.T": "デンソー", "6920.T": "レーザーテック", "6952.T": "カシオ",
    "6954.T": "ファナック", "6971.T": "京セラ", "6976.T": "太陽誘電", "6981.T": "村田製作所", "6988.T": "日東電工", "7735.T": "SCREEN",
    # 輸送・精密
    "7011.T": "三菱重工業", "7012.T": "川崎重工業", "7013.T": "ＩＨＩ", "7186.T": "横浜ＦＧ", "7201.T": "日産自動車",
    "7202.T": "いすゞ自動車", "7203.T": "トヨタ自動車", "7205.T": "日野自動車", "7211.T": "三菱自動車工業", "7261.T": "マツダ",
    "7267.T": "本田技研工業", "7269.T": "スズキ", "7270.T": "ＳＵＢＡＲＵ", "7272.T": "ヤマハ発動機",
    "7731.T": "ニコン", "7733.T": "オリンパス", "7741.T": "ＨＯＹＡ", "7751.T": "キヤノン", "7752.T": "リコー", "7762.T": "シチズン時計",
    # 商社・金融・不動産・サービス・通信
    "1721.T": "コムシスHD", "1801.T": "大成建設", "1802.T": "大林組", "1803.T": "清水建設", "1808.T": "長谷工", "1812.T": "鹿島建設",
    "1925.T": "大和ハウス", "1928.T": "積水ハウス", "1963.T": "日揮HD", "8001.T": "伊藤忠", "8002.T": "丸紅", "8015.T": "豊田通商",
    "8031.T": "三井物産", "8035.T": "東京エレクトロン", "8053.T": "住友商事", "8058.T": "三菱商事", "8233.T": "高島屋", "8252.T": "丸井グループ",
    "8253.T": "クレディセゾン", "8267.T": "イオン", "8304.T": "あおぞら銀行", "8306.T": "三菱ＵＦＪ", "8308.T": "りそなＨＤ",
    "8309.T": "三井住友トラスト", "8316.T": "三井住友ＦＧ", "8331.T": "千葉銀行", "8354.T": "ふくおかＦＧ", "8411.T": "みずほＦＧ",
    "8591.T": "オリックス", "8601.T": "大和証券Ｇ", "8604.T": "野村ＨＤ", "8630.T": "ＳＯＭＰＯ", "8725.T": "ＭＳ＆ＡＤ",
    "8750.T": "第一生命ＨＤ", "8766.T": "東京海上", "8795.T": "Ｔ＆Ｄ", "8801.T": "三井不動産", "8802.T": "三菱地所", "8804.T": "東京建物",
    "8830.T": "住友不動産", "2413.T": "エムスリー", "2432.T": "ディーエヌエー", "4307.T": "野村総研", "4324.T": "電通グループ",
    "4661.T": "ＯＬＣ", "4689.T": "ラインヤフー", "4704.T": "トレンド", "4751.T": "サイバーエージェント", "4755.T": "楽天グループ",
    "9001.T": "東武鉄道", "9005.T": "東急", "9007.T": "小田急電鉄", "9008.T": "京王電鉄", "9009.T": "京成電鉄", "9020.T": "ＪＲ東日本",
    "9021.T": "ＪＲ西日本", "9022.T": "ＪＲ東海", "9101.T": "日本郵船", "9104.T": "商船三井", "9107.T": "川崎汽船", "9201.T": "日本航空",
    "9202.T": "ＡＮＡ", "9301.T": "三菱倉庫", "9432.T": "ＮＴＴ", "9433.T": "ＫＤＤＩ", "9434.T": "ソフトバンク", "9501.T": "東電ＨＤ",
    "9502.T": "中部電力", "9503.T": "関西電力", "9531.T": "東京瓦斯", "9532.T": "大阪瓦斯", "9602.T": "東宝", "9735.T": "セコム",
    "9766.T": "コナミＧ", "9843.T": "ニトリＨＤ", "9983.T": "ファーストリテイリング", "9984.T": "ソフトバンクグループ", "4062.T": "イビデン",
    "3697.T": "ＳＨＩＦＴ", "6532.T": "ベイカレント", "9613.T": "ＮＴＴデータ", "6963.T": "ローム", "2768.T": "双日", "5831.T": "しずおかＦＧ",
    # 追加銘柄
    "4403.T": "日油", "6315.T": "TOWA", "3436.T": "SUMCO", "7003.T": "三井E&S", "1570.T": "日経レバ", "7453.T": "良品計画",
}

# CSS (左揃え・テーブル調整)
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
        <h3 style='font-weight: 300; font-size: 20px; margin: 0; padding: 0; color: #aaaaaa;'>DAY TRADING MANAGER｜ver 6.0 Ranking</h3>
    </div>
    """, unsafe_allow_html=True)

# --- 基本関数 ---
def get_trade_pattern(row, gap_pct):
    check_vwap = row['VWAP'] if pd.notna(row['VWAP']) else row['Close']
    if (gap_pct <= -0.004) and (row['Close'] > check_vwap): return "A：反転狙い"
    elif (-0.003 <= gap_pct < 0.003) and (row['Close'] > row['EMA5']): return "D：上昇継続"
    elif (gap_pct >= 0.005) and (row.get('RSI14', 50) >= 65): return "C：ブレイク"
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
        df.index = df.index.tz_localize('UTC').tz_convert('Asia/Tokyo') if df.index.tzinfo is None else df.index.tz_convert('Asia/Tokyo')
        
        tr = pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))], axis=1).max(axis=1)
        atr_prev = tr.rolling(window=14).mean().shift(1)
        
        p_map = {d.strftime('%Y-%m-%d'): c for d, c in zip(df.index, df['Close'].shift(1)) if pd.notna(c)}
        o_map = {d.strftime('%Y-%m-%d'): o for d, o in zip(df.index, df['Open']) if pd.notna(o)}
        a_map = {d.strftime('%Y-%m-%d'): a for d, a in zip(df.index, atr_prev) if pd.notna(a)}
        return p_map, o_map, a_map
    except: return p_map, o_map, a_map

@st.cache_data(ttl=86400)
def get_ticker_name(ticker):
    return TICKER_NAME_MAP.get(ticker, ticker)

# --- シミュレーション・コアロジック (個別・ランキング共通) ---
def run_ticker_simulation(ticker, df, pc_map, co_map, a_map, params):
    trades = []
    if df.empty: return trades
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    df.index = df.index.tz_localize('UTC').tz_convert('Asia/Tokyo') if df.index.tzinfo is None else df.index.tz_convert('Asia/Tokyo')
    
    df['EMA5'] = EMAIndicator(close=df['Close'], window=5).ema_indicator()
    df['RSI14'] = RSIIndicator(close=df['Close'], window=14).rsi()
    df['RSI14_P'] = df['RSI14'].shift(1)
    macd = MACD(close=df['Close'])
    df['MH'] = macd.macd_diff(); df['MH_P'] = df['MH'].shift(1)
    
    unique_dates = np.unique(df.index.date)
    for d in unique_dates:
        day = df[df.index.date == d].copy().between_time('09:00', '15:00')
        if day.empty: continue
        day['VWAP'] = (day['Close'] * day['Volume']).cumsum() / day['Volume'].cumsum().replace(0, np.nan)
        date_str = d.strftime('%Y-%m-%d')
        pc = pc_map.get(date_str); do = co_map.get(date_str)
        if pc is None or do is None: continue
        gap_v = (do - pc) / pc
        
        in_pos = False; entry_p = 0; stop_p = 0; t_high = 0; t_active = False; sl_rec = 0
        for ts, row in day.iterrows():
            if not in_pos:
                if params['start_t'] <= ts.time() <= params['end_t'] and params['g_min'] <= gap_v <= params['g_max']:
                    c_vwap = (row['Close'] > row['VWAP']) if params['u_vwap'] else True
                    c_ema = (row['Close'] > row['EMA5']) if params['u_ema'] else True
                    c_rsi = (row['RSI14'] > 45 and row['RSI14'] > row['RSI14_P']) if params['u_rsi'] else True
                    c_macd = (row['MH'] > row['MH_P']) if params['u_macd'] else True
                    
                    if c_vwap and c_ema and c_rsi and c_macd:
                        entry_p = row['Close'] * 1.0003; in_pos = True; entry_t = ts; entry_vwap = row['VWAP']
                        # ATR損切り計算
                        if params['u_atr']:
                            av = a_map.get(date_str)
                            sl_rec = max(params['atr_min'], (av/entry_p)*params['atr_mul']) if av and entry_p>0 else abs(params['sl_fix'])
                        else: sl_rec = abs(params['sl_fix'])
                        stop_p = entry_p * (1 - sl_rec); t_high = row['High']; t_active = False
            else:
                t_high = max(t_high, row['High'])
                if not t_active and t_high >= entry_p * (1 + params['ts_start']): t_active = True
                ex_p = None; rsn = ""
                if t_active and row['Low'] <= t_high * (1 - params['ts_width']):
                    ex_p = t_high * (1 - params['ts_width']) * 0.9997; rsn = "トレーリング"
                elif row['Low'] <= stop_p: ex_p = stop_p * 0.9997; rsn = "損切り"
                elif ts.time() >= time(14, 55): ex_p = row['Close'] * 0.9997; rsn = "時間切れ"
                
                if ex_p:
                    trades.append({'Ticker': ticker, 'Entry': entry_t, 'Exit': ts, 'PnL': (ex_p - entry_p)/entry_p, 'In': entry_p, 'Out': ex_p, 'Reason': rsn, 'Pattern': get_trade_pattern(row, gap_v), 'Gap(%)': gap_v*100, 'EntryVWAP': entry_vwap, 'PrevClose': pc, 'DayOpen': do, 'SL設定(%)': sl_rec*100})
                    in_pos = False; break
    return trades

# --- UI サイドバー ---
st.sidebar.header("⚙️ パラメーター設定")
days_back = st.sidebar.slider("過去何日分を取得", 10, 59, 59)
st.sidebar.subheader("⏰ 時間設定")
s_t = st.sidebar.time_input("開始時間", time(9, 0), step=300)
e_t = st.sidebar.time_input("終了時間", time(9, 15), step=300)
st.sidebar.subheader("📉 エントリー条件")
u_vwap = st.sidebar.checkbox("**VWAP** より上でエントリー", value=True)
u_ema = st.sidebar.checkbox("**EMA5** より上でエントリー", value=True)
u_rsi = st.sidebar.checkbox("**RSI** が45以上or上向き", value=True)
u_macd = st.sidebar.checkbox("**MACD** が上向き", value=True)
st.sidebar.divider()
g_min = st.sidebar.slider("寄付ダウン下限 (%)", -10.0, 0.0, -3.0, 0.05) / 100
g_max = st.sidebar.slider("寄付アップ上限 (%)", -5.0, 5.0, 1.0, 0.05) / 100
st.sidebar.subheader("💰 決済ルール")
ts_s = st.sidebar.number_input("トレイリング開始 (%)", 0.1, 5.0, 0.5, 0.05) / 100
ts_w = st.sidebar.number_input("下がったら成行注文 (%)", 0.1, 5.0, 0.2, 0.05) / 100
sl_f = st.sidebar.number_input("損切り (%) ※ATR非使用時", -5.0, -0.1, -0.5, 0.05) / 100
st.sidebar.divider()
st.sidebar.write("📉 **動的損切り設定 (ATR)**")
u_atr = st.sidebar.checkbox("ATR損切りを使用", value=True)
a_mul = st.sidebar.number_input("ATR倍率", 0.5, 5.0, 1.5, 0.1)
a_min = st.sidebar.number_input("最低損切り (%)", 0.1, 5.0, 0.5, 0.1) / 100

params = {
    'days': days_back, 'start_t': s_t, 'end_t': e_t, 'u_vwap': u_vwap, 'u_ema': u_ema, 'u_rsi': u_rsi, 'u_macd': u_macd,
    'g_min': g_min, 'g_max': g_max, 'ts_start': ts_s, 'ts_width': ts_w, 'sl_fix': sl_f, 'u_atr': u_atr, 'atr_mul': a_mul, 'atr_min': a_min
}

# --- メインロジック ---
ticker_input = st.text_input("銘柄コード (カンマ区切り)", "8267.T")
tickers = [t.strip() for t in ticker_input.split(",") if t.strip()]
main_btn = st.button("バックテスト実行", type="primary", key="main_btn")
st.divider()

if main_btn:
    end_date = datetime.now(); start_date = end_date - timedelta(days=days_back)
    all_trades = []
    pb = st.progress(0); st_text = st.empty()
    for i, t in enumerate(tickers):
        st_text.text(f"Testing {t}..."); pb.progress((i+1)/len(tickers))
        df = fetch_intraday(t, start_date, end_date)
        p_map, o_map, a_map = fetch_daily_stats_maps(t, start_date)
        all_trades.extend(run_ticker_simulation(t, df, p_map, o_map, a_map, params))
    pb.empty(); st_text.empty()
    st.session_state['res_df'] = pd.DataFrame(all_trades)
    st.session_state['start_date'] = start_date

# --- 結果表示タブ ---
if 'res_df' in st.session_state:
    res_df = st.session_state['res_df']
    start_date = st.session_state.get('start_date', datetime.now())

    # タブの定義 (v5.9の5つ + ランキング)
    tab1, tab2, tab3, tab4, tab5, tab6, tab_rank = st.tabs(["📊 サマリー", "🤖 勝ちパターン", "📝 詳細ログ", "🏆 ランキング"])

 with tab1: # サマリー
        if not res_df.empty:
            count_all = len(res_df); wins = res_df[res_df['PnL'] > 0]
            losses = res_df[res_df['PnL'] <= 0]
            win_rate = len(wins) / count_all if count_all > 0 else 0
            gross_win = wins['PnL'].sum(); gross_loss = abs(losses['PnL'].sum())
            pf = gross_win / gross_loss if gross_loss > 0 else float('inf')
            expectancy = res_df['PnL'].mean()

            st.markdown(f"""
            <div style='display: flex; justify-content: space-around; background-color: #262730; padding: 20px; border-radius: 10px;'>
                <div style='text-align: center;'><div style='color: #aaa;'>総トレード数</div><div style='font-size: 24px;'>{count_all}回</div></div>
                <div style='text-align: center;'><div style='color: #aaa;'>勝率</div><div style='font-size: 24px;'>{win_rate:.1%}</div></div>
                <div style='text-align: center;'><div style='color: #aaa;'>PF</div><div style='font-size: 24px;'>{pf:.2f}</div></div>
                <div style='text-align: center;'><div style='color: #aaa;'>期待値</div><div style='font-size: 24px;'>{expectancy:.2%}</div></div>
            </div>
            """, unsafe_allow_html=True)
            st.divider()
            # レポートテキスト出力
            report = ["=================\n BACKTEST REPORT \n================="]
            report.append(f"\nPeriod: {start_date.strftime('%Y-%m-%d')} - {datetime.now().strftime('%Y-%m-%d')}\n")
            for t in tickers:
                tdf = res_df[res_df['Ticker'] == t]
                if tdf.empty: continue
                tw = tdf[tdf['PnL'] > 0]; tl = tdf[tdf['PnL'] <= 0]
                report.append(f">>> TICKER: {t} | {get_ticker_name(t)}")
                report.append(f"トレード数: {len(tdf)} | 勝率: {len(tw)/len(tdf):.1%} | 期待値: {tdf['PnL'].mean():+.2%}\n")
            st.code("\n".join(report))
        else: st.warning("条件に合うトレードはありません。")

    with tab2: # 勝ちパターン
        st.markdown("### 🤖 勝ちパターン分析")
        for t in tickers:
            tdf = res_df[res_df['Ticker'] == t].copy()
            if tdf.empty: continue
            st.markdown(f"#### [{t}] {get_ticker_name(t)}")
            pat_stats = tdf.groupby('Pattern')['PnL'].agg(['count', lambda x: (x>0).mean(), 'mean']).reset_index()
            pat_stats.columns = ['パターン', 'トレード数', '勝率', '平均損益']
            st.dataframe(pat_stats, use_container_width=True, hide_index=True)

    with tab3: # ギャップ分析
        for t in tickers:
            tdf = res_df[res_df['Ticker'] == t].copy()
            if tdf.empty: continue
            st.markdown(f"### [{t}] {get_ticker_name(t)}")
            tdf['方向'] = tdf['Gap(%)'].apply(lambda x: 'ギャップアップ' if x > 0 else 'ギャップダウン')
            st.dataframe(tdf.groupby('方向')['PnL'].agg(['count', lambda x: (x>0).mean(), 'mean']), use_container_width=True)

    with tab4: # VWAP分析
        for t in tickers:
            tdf = res_df[res_df['Ticker'] == t].copy()
            if tdf.empty: continue
            tdf['VWAP乖離(%)'] = ((tdf['In'] - tdf['EntryVWAP']) / tdf['EntryVWAP']) * 100
            v_bins = tdf.groupby(pd.cut(tdf['VWAP乖離(%)'], bins=np.arange(-1.0, 1.2, 0.2)), observed=True).agg(['count', lambda x: (x>0).mean(), 'mean'])
            st.write(f"#### [{t}] VWAP乖離別成績")
            st.dataframe(v_bins, use_container_width=True)

    with tab5: # 時間分析
        for t in tickers:
            tdf = res_df[res_df['Ticker'] == t].copy()
            if tdf.empty: continue
            tdf['時間帯'] = tdf['Entry'].apply(lambda dt: dt.strftime('%H:%M'))
            st.write(f"#### [{t}] 時間帯別成績")
            st.dataframe(tdf.groupby('時間帯')['PnL'].agg(['count', lambda x: (x>0).mean(), 'mean']), use_container_width=True)

    with tab6: # 詳細ログ
        st.dataframe(res_df.sort_values('Entry', ascending=False), use_container_width=True)

    with tab_rank: # 🏆 ランキング機能
        st.markdown("### 🏆 登録銘柄バックテスト・ランキング")
        st.caption("サイドバーの設定条件で、全登録銘柄をスキャンします。")
        if st.button("ランキング生成（全銘柄スキャン開始）", type="primary"):
            rank_list = []
            all_tickers = list(TICKER_NAME_MAP.keys())
            pb_r = st.progress(0); st_text_r = st.empty()
            end_date = datetime.now(); start_date = end_date - timedelta(days=days_back)
            
            for i, t in enumerate(all_tickers):
                st_text_r.text(f"Scanning {i+1}/{len(all_tickers)}: {t}"); pb_r.progress((i+1)/len(all_tickers))
                df = fetch_intraday(t, start_date, end_date)
                p_map, o_map, a_map = fetch_daily_stats_maps(t, start_date)
                t_trades = run_ticker_simulation(t, df, p_map, o_map, a_map, params)
                
                if t_trades:
                    tdf = pd.DataFrame(t_trades)
                    wins = tdf[tdf['PnL'] > 0]; losses = tdf[tdf['PnL'] <= 0]
                    gw = wins['PnL'].sum(); gl = abs(losses['PnL'].sum())
                    rank_list.append({
                        '銘柄コード': t, '銘柄名': get_ticker_name(t), 'トレード数': len(tdf),
                        '勝率': len(wins)/len(tdf), '利益平均': wins['PnL'].mean() if not wins.empty else 0,
                        '損失平均': losses['PnL'].mean() if not losses.empty else 0,
                        'PF': gw/gl if gl > 0 else 9.99, '期待値': tdf['PnL'].mean()
                    })
            
            pb_r.empty(); st_text_r.empty()
            if rank_list:
                rdf = pd.DataFrame(rank_list).sort_values('期待値', ascending=False).head(20)
                st.success("スキャン完了！上位20銘柄を表示します。")
                st.dataframe(
                    rdf.style.format({
                        '勝率': '{:.1%}', '利益平均': '{:+.2%}', '損失平均': '{:+.2%}', '期待値': '{:+.2%}', 'PF': '{:.2f}'
                    }), 
                    use_container_width=True, hide_index=True
                )
            else: st.error("該当銘柄がありませんでした。")
