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

# --- セッション状態の初期化 ---
if 'view_mode' not in st.session_state:
    st.session_state['view_mode'] = 'individual'  # 初期値は個別検証モード
if 'trigger_rank_scan' not in st.session_state:
    st.session_state['trigger_rank_scan'] = False # ランキング実行の予約フラグ

# --- 銘柄名マッピング (日経225 + 追加6銘柄 = 全231銘柄) ---
TICKER_NAME_MAP = {
    # 水産・食品
    "1332.T": "ニッスイ", "2002.T": "日清粉G", "2269.T": "明治HD", "2282.T": "日本ハム", "2501.T": "サッポロHD",
    "2502.T": "アサヒG", "2503.T": "キリンHD", "2801.T": "キッコーマン", "2802.T": "味の素", "2871.T": "ニチレイ", "2914.T": "JT",
    # 繊維・化学
    "3101.T": "東洋紡", "3103.T": "ユニチカ", "3401.T": "帝人", "3402.T": "東レ", "3405.T": "クラレ", "3407.T": "旭化成", "3861.T": "王子HD", "3863.T": "日本製紙",
    "4004.T": "レゾナック", "4005.T": "住友化学", "4021.T": "日産化学", "4042.T": "東ソー", "4043.T": "トクヤマ",
    "4061.T": "デンカ", "4063.T": "信越化学", "4151.T": "協和キリン", "4183.T": "三井化学", "4188.T": "三菱ケミＧ",
    "4208.T": "ＵＢＥ", "4452.T": "花王", "4901.T": "富士フイルム", "4911.T": "資生堂",
    "4502.T": "武田薬品", "4503.T": "アステラス製薬", "4506.T": "住友ファーマ", "4507.T": "塩野義製薬", "4519.T": "中外製薬",
    "4523.T": "エーザイ", "4543.T": "テルモ", "4568.T": "第一三共", "4578.T": "大塚ＨＤ",
    # 石油・ゴム・金属
    "1605.T": "ＩＮＰＥＸ", "5019.T": "出光興産", "5020.T": "ＥＮＥＯＳ", "5101.T": "横浜ゴム", "5108.T": "ブリヂストン",
    "5201.T": "ＡＧＣ", "5202.T": "日本板硝子", "5214.T": "日電硝", "5232.T": "住友大阪セメント", "5233.T": "太平洋セメント", "5301.T": "東海カーボン",
    "5332.T": "ＴＯＴＯ", "5333.T": "日本碍子", "5401.T": "日本製鉄", "5406.T": "神戸製鋼所", "5411.T": "ＪＦＥ",
    "5541.T": "大平洋金属", "5631.T": "日本製鋼所", "5706.T": "三井金属", "5711.T": "三菱マテリアル", "5713.T": "住友金属鉱山",
    "5714.T": "ＤＯＷＡ", "5801.T": "古河電気工業", "5802.T": "住友電気工業", "5803.T": "フジクラ", "5947.T": "リンナイ",
    # 機械・電機
    "6098.T": "リクルート", "6103.T": "オークマ", "6113.T": "アマダ", "6146.T": "ディスコ", "6273.T": "ＳＭＣ",
    "6301.T": "小松製作所", "6302.T": "住友重機械", "6305.T": "日立建機", "6326.T": "クボタ", "6361.T": "荏原製作所",
    "6367.T": "ダイキン工業", "6471.T": "日本精工", "6472.T": "ＮＴＮ", "6473.T": "ジェイテクト", "6479.T": "ミネベアミツミ",
    "6501.T": "日立", "6503.T": "三菱電機", "6504.T": "富士電機", "6506.T": "安川電機", "6526.T": "ソシオネクスト", "6594.T": "ニデック",
    "6645.T": "オムロン", "6701.T": "日本電気", "6702.T": "富士通", "6723.T": "ルネサス", "6724.T": "セイコーエプソン",
    "6752.T": "パナソニック", "6753.T": "シャープ", "6758.T": "ソニーグループ", "6762.T": "ＴＤＫ", "6770.T": "アルプスアルパイン",
    "6841.T": "横河電機", "6857.T": "アドバンテスト", "6861.T": "キーエンス", "6902.T": "デンソー", "6920.T": "レーザーテック", "6952.T": "カシオ",
    "6954.T": "ファナック", "6971.T": "京セラ", "6976.T": "太陽誘電", "6981.T": "村田製作所", "6988.T": "日東電工", "7735.T": "SCREEN",
    # 輸送・精密
    "4902.T": "コニカミノル", "7011.T": "三菱重工業", "7012.T": "川崎重工業", "7013.T": "ＩＨＩ", "7186.T": "横浜ＦＧ", "7201.T": "日産自動車",
    "7202.T": "いすゞ自動車", "7203.T": "トヨタ自動車", "7205.T": "日野自動車", "7211.T": "三菱自動車工業", "7261.T": "マツダ",
    "7267.T": "本田技研工業", "7269.T": "スズキ", "7270.T": "ＳＵＢＡＲＵ", "7272.T": "ヤマハ発動機",
    "7731.T": "ニコン", "7733.T": "オリンパス", "7741.T": "ＨＯＹＡ", "7751.T": "キヤノン", "7752.T": "リコー", "7762.T": "シチズン時計",
    # 商社・金融・不動産・サービス・通信
    "1721.T": "コムシスHD", "1801.T": "大成建設", "1802.T": "大林組", "1803.T": "清水建設", "1808.T": "長谷工", "1812.T": "鹿島建設",
    "1925.T": "大和ハウス", "1928.T": "積水ハウス", "1963.T": "日揮HD", "3064.T": "モノタロウ", "3086.T": "Ｊフロント", "3092.T": "ＺＯＺＯ", 
    "3099.T": "三越伊勢丹", "3289.T": "東急不動産", "3382.T": "セブン＆アイ", "3659.T": "ネクソン", "4385.T": "メルカリ", "6178.T": "日本郵政", 
    "7974.T": "任天堂", "8001.T": "伊藤忠", "8002.T": "丸紅", "8015.T": "豊田通商",
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
    # 追加銘柄 (日経225外の銘柄を含む、ユーザー指定の6銘柄)
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

/* 見出し（###）のサイズを一括で小さくする */
    h3 {
        font-size: 1.4rem !important;
        font-weight: 600 !important;
        margin-top: 10px !important;
        margin-bottom: -5px !important;
    }
    
/* 見出し2（####）のサイズを一括で小さくする */
    h4 {
        font-size: 1.4rem !important;
        font-weight: 600 !important;
        margin-top: 10px !important;
    }
    
/* 小見出し（#####）のサイズを一括で小さくする */
    h5 {
        font-size: 1.2rem !important;
        font-weight: 500 !important;
        margin-top: 10px !important;
    }
    
    th, td { text-align: left !important; }
    </style>
    """, unsafe_allow_html=True)

st.markdown("""
    <div style='margin-bottom: 20px;'>
        <h1 style='font-weight: 400; font-size: 46px; margin: 0; padding: 0;'>BACK TESTER</h1>
        <div style='font-weight: 300; font-size: 20px; margin: 0; padding: 0; color: #aaaaaa;'>DAY TRADING MANAGER｜ver 6.2</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("""
    <style>
    /* --- サイドバー専用の設定 (メイン画面には影響しません) --- */

    /* パラメーター設定 (header) のサイズ調整 */
    [data-testid="stSidebar"] h2 {
        font-size: 1.2rem !important;
        font-weight: 700 !important;
    }

    /* ⏰ 時間設定 / エントリー条件 / 決済ルール (subheader) */
    [data-testid="stSidebar"] h3 {
        font-size: 1.2rem !important;
        font-weight: 700 !important;
        margin-top: 15px !important;
    }

    /* 説明テキスト */
    [data-testid="stSidebar"] .stMarkdown p {
        font-size: 0.9rem !important;
    }

    /* チェックボックスのラベル (VWAPより上でエントリーなど) */
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
        font-size: 0.9rem !important;
        font-weight: 500 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 基本関数 ---
def get_trade_pattern(row, gap_pct):
    check_vwap = row['VWAP'] if pd.notna(row['VWAP']) else row['Close']
    if (gap_pct <= -0.004) and (row['Close'] > check_vwap): return "A：反転狙い"
    elif (-0.003 <= gap_pct < 0.003) and (row['Close'] > row['EMA5']): return "D：上昇継続"
    elif (gap_pct >= 0.005) and (row.get('RSI14', 50) >= 65): return "C：ブレイク"
    elif (gap_pct >= 0.003) and (row['Close'] > row['EMA5']): return "B：押目上昇"
    return "E：他タイプ"

# データ取得（5分足）
@st.cache_data(ttl=600)
def fetch_intraday(ticker, start, end):
    try:
        df = yf.download(ticker, start=start, end=datetime.now(), interval="5m", progress=False, multi_level_index=False, auto_adjust=False)
        return df
    except: return pd.DataFrame()

# ATR算出ロジックを含む関数
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

# 銘柄名取得（辞書優先）
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
st.sidebar.write("")
st.sidebar.subheader("📉 エントリー条件")
u_vwap = st.sidebar.checkbox("**VWAP** より上でエントリー", value=True)
st.sidebar.write("")
u_ema = st.sidebar.checkbox("**EMA5** より上でエントリー", value=True)
st.sidebar.write("")
u_rsi = st.sidebar.checkbox("**RSI** が45以上or上向き", value=True)
st.sidebar.write("")
u_macd = st.sidebar.checkbox("**MACD** が上向き", value=True)
st.sidebar.divider()

g_min = st.sidebar.slider("寄付ダウン下限 (%)", -10.0, 0.0, -3.0, 0.05) / 100
g_max = st.sidebar.slider("寄付アップ上限 (%)", -5.0, 5.0, 1.0, 0.05) / 100

st.sidebar.subheader("💰 決済ルール")
ts_s = st.sidebar.number_input("トレイリング開始 (%)", 0.1, 5.0, 0.5, 0.05) / 100
ts_w = st.sidebar.number_input("下がったら成行注文 (%)", 0.1, 5.0, 0.2, 0.05) / 100
sl_f = st.sidebar.number_input("損切り (%) ※ATR非使用時", -5.0, -0.1, -0.5, 0.05) / 100
st.sidebar.divider()

st.sidebar.subheader("📉 **動的損切り設定 (ATR)**")
u_atr = st.sidebar.checkbox("ATR損切りを使用", value=True)
a_mul = st.sidebar.number_input("ATR倍率", 0.5, 5.0, 1.5, 0.1)
a_min = st.sidebar.number_input("最低損切り (%)", 0.1, 5.0, 0.5, 0.1) / 100

# ★追加：ランキング検索条件
st.sidebar.divider()
st.sidebar.subheader("🔍 ランキング検索条件")
# 株価範囲スライダー (500円単位、デフォルト500〜5000円)
p_range = st.sidebar.slider("株価範囲 (円)", 0, 20000, (500, 5000), 500)
p_min, p_max = p_range

# サイドバー内のボタン
# ★ここが重要：変数に代入せず、クリックされたら即座にモードを切り替えてRerunする
if st.sidebar.button("ランキング生成", type="primary", use_container_width=True, key="side_rank_btn"):
    st.session_state['view_mode'] = 'ranking'
    st.session_state['trigger_rank_scan'] = True # スキャン開始フラグ
    st.rerun()

# パラメータ辞書の更新 (株価フィルター用の値を追加)
params = {
    'days': days_back, 'start_t': s_t, 'end_t': e_t, 'u_vwap': u_vwap, 'u_ema': u_ema, 'u_rsi': u_rsi, 'u_macd': u_macd,
    'g_min': g_min, 'g_max': g_max, 'ts_start': ts_s, 'ts_width': ts_w, 'sl_fix': sl_f, 'u_atr': u_atr, 'atr_mul': a_mul, 'atr_min': a_min,
    'p_min': p_min, 'p_max': p_max # ★株価フィルター用
}

# サイドバーのボタンが押された場合、ランキングタブのボタンが押されたのと同じ挙動にするためのフラグ
if side_rank_btn:
    st.session_state['trigger_rank_scan'] = True

# --- モード管理の初期化 ---
if 'view_mode' not in st.session_state:
    st.session_state['view_mode'] = 'individual' # 初期値は個別モード

# --- メインロジック（入力・実行エリア） ---
if st.session_state['view_mode'] == 'individual':
    # 個別モードの時だけ、銘柄入力とバックテスト実行ボタンを表示
    ticker_input = st.text_input("銘柄コード (カンマ区切り)", "8267.T")
    tickers = [t.strip() for t in ticker_input.split(",") if t.strip()]

if st.button("バックテスト実行", type="primary", key="main_btn"):
        # 実行時に個別モードを維持
        st.session_state['view_mode'] = 'individual'
    
    end_date = datetime.now(); start_date = end_date - timedelta(days=days_back); all_trades = []
    pb = st.progress(0); st_text = st.empty(); t_names = {}
    for i, t in enumerate(tickers):
        st_text.text(f"Testing {t}..."); pb.progress((i+1)/len(tickers))
        df = fetch_intraday(t, start_date, end_date)
        p_map, o_map, a_map = fetch_daily_stats_maps(t, start_date)
        all_trades.extend(run_ticker_simulation(t, df, p_map, o_map, a_map, params))
        t_names[t] = get_ticker_name(t)
    pb.empty(); st_text.empty()
    st.session_state['res_df'] = pd.DataFrame(all_trades)
    st.session_state['start_date'] = start_date
    st.session_state['end_date'] = end_date
    st.session_state['t_names'] = t_names

else:
    # ランキングモードの時は、個別検証に戻るためのボタンだけを表示
    if st.button("← 個別銘柄検証に戻る", use_container_width=False):
        st.session_state['view_mode'] = 'individual'
        st.rerun()

# --- 結果表示エリア ---
# 個別テスト結果がある、またはランキング結果がある、またはランキングスキャン中なら表示
if 'res_df' in st.session_state or 'last_rank_df' in st.session_state or st.session_state['view_mode'] == 'ranking':
    res_df = st.session_state.get('res_df', pd.DataFrame())
    start_date = st.session_state.get('start_date', datetime.now() - timedelta(days=days_back))
    end_date = st.session_state.get('end_date', datetime.now())
    ticker_names = st.session_state.get('t_names', {})
      
    # タブの定義 (v5.9の5つ + ランキング)
    tab1, tab2, tab3, tab4, tab5, tab6, tab_rank = st.tabs(["📊 サマリー", "🏅 勝ちパターン", "📉 ギャップ分析", "🧐 VWAP分析", "🕒 時間分析", "📝 詳細ログ", "🏆 ランキング"])

    with tab1: # サマリー
        count_all = len(res_df)
        wins_all = res_df[res_df['PnL'] > 0]
        losses_all = res_df[res_df['PnL'] <= 0]
        win_rate_all = len(wins_all) / count_all if count_all > 0 else 0
        gross_win = res_df[res_df['PnL']>0]['PnL'].sum()
        gross_loss = abs(res_df[res_df['PnL']<=0]['PnL'].sum())
        pf_all = gross_win/gross_loss if gross_loss > 0 else float('inf')
        expectancy_all = res_df['PnL'].mean()

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
            <div class="metric-box"><div class="metric-label">期待値</div><div class="metric-value">{expectancy_all:.2%}</div></div>
        </div>
        """, unsafe_allow_html=True)
        st.divider()
    
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
                
            t_name = ticker_names.get(t, t)
            report.append(f">>> TICKER: {t} | {t_name}")
            report.append(f"トレード数: {cnt} | 勝率: {wr:.1%} | 利益平均: {avg_win:+.2%} | 損失平均: {avg_loss:+.2%} | PF: {pf:.2f} | 期待値: {tdf['PnL'].mean():+.2%}\n")
        st.caption("右上のコピーボタンで全文コピーできます↓")
        st.code("\n".join(report), language="text")

    with tab2: # 勝ちパターン
        st.markdown("### 🏅 勝ちパターン分析")
        st.caption("チャートパターン別の成績分析と、ベストなエントリー条件を言語化して勝ちパターンを抽出します。")
        for t in tickers:
            tdf = res_df[res_df['Ticker'] == t].copy()
            if tdf.empty: continue
            t_name = ticker_names.get(t, t)
            st.markdown(f"#### [{t}] {t_name}")
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
                    f"(GAP勝率: {best_g['<lambda_0>']:.1%} / VWAP勝率: {best_v['<lambda_0>']:.1%} / 時間勝率: {best_t['<lambda_0>']:.1%})")
            st.divider()

    with tab3: # ギャップ分析
        for t in tickers:
            tdf = res_df[res_df['Ticker'] == t].copy()
            if tdf.empty: continue
            t_name = ticker_names.get(t, t)
            st.markdown(f"### [{t}] {t_name}")
            
            # --- 1. 始値ギャップ方向の分析 ---
            st.markdown("##### 始値ギャップ方向と成績")
            tdf['GapDir'] = tdf['Gap(%)'].apply(lambda x: 'ギャップアップ' if x > 0 else ('ギャップダウン' if x < 0 else 'フラット'))
            
            # ★修正：['PnL'] を指定し、名前付き集計（Named Aggregation）で計算
            gap_dir_stats = tdf.groupby('GapDir', observed=True).agg(
                Count=('PnL', 'count'), 
                WinRate=('PnL', lambda x: (x > 0).mean()), 
                AvgPnL=('PnL', 'mean')
            ).reset_index()
            
            # 表示用に整形
            gap_dir_disp = gap_dir_stats.copy()
            gap_dir_disp['WinRate'] = gap_dir_disp['WinRate'].apply(lambda x: f"{x:.1%}")
            gap_dir_disp['AvgPnL'] = gap_dir_disp['AvgPnL'].apply(lambda x: f"{x:+.2%}")
            gap_dir_disp['Count'] = gap_dir_disp['Count'].astype(str)
            gap_dir_disp.columns = ['方向', 'トレード数', '勝率', '平均損益']
            
            # 表を表示
            st.dataframe(gap_dir_disp.style.set_properties(**{'text-align': 'left'}), hide_index=True, use_container_width=True)

            # --- 2. ギャップ幅ごとの分析 ---
            st.markdown("##### ギャップ幅ごとの勝率")
            min_g = np.floor(tdf['Gap(%)'].min()); max_g = np.ceil(tdf['Gap(%)'].max())
            if np.isnan(min_g): min_g = -3.0; max_g = 1.0
            bins_g = np.arange(min_g, max_g + 0.5, 0.5)
            tdf['GapRange'] = pd.cut(tdf['Gap(%)'], bins=bins_g)
            
            # ★修正：['PnL'] を指定し、名前付き集計で計算
            gap_range_stats = tdf.groupby('GapRange', observed=True).agg(
                Count=('PnL', 'count'), 
                WinRate=('PnL', lambda x: (x > 0).mean()), 
                AvgPnL=('PnL', 'mean')
            ).reset_index()
            
            def format_interval(i): return f"{i.left:.1f}% ～ {i.right:.1f}%"
            gap_range_stats['RangeLabel'] = gap_range_stats['GapRange'].apply(format_interval)
            
            disp_gap = gap_range_stats[['RangeLabel', 'Count', 'WinRate', 'AvgPnL']].copy()
            disp_gap['WinRate'] = disp_gap['WinRate'].apply(lambda x: f"{x:.1%}")
            disp_gap['AvgPnL'] = disp_gap['AvgPnL'].apply(lambda x: f"{x:+.2%}")
            disp_gap['Count'] = disp_gap['Count'].astype(str)
            disp_gap.columns = ['ギャップ幅', 'トレード数', '勝率', '平均損益']
            
            st.dataframe(disp_gap.style.set_properties(**{'text-align': 'left'}), hide_index=True, use_container_width=True)
            st.divider()

    with tab4: # VWAP分析
        for t in tickers:
            tdf = res_df[res_df['Ticker'] == t].copy()
            if tdf.empty: continue
            t_name = ticker_names.get(t, t)
            st.markdown(f"### [{t}] {t_name}")
            st.markdown("##### エントリー時のVWAPと勝率")
            
            # VWAP乖離の計算
            tdf['VWAP乖離(%)'] = ((tdf['In'] - tdf['EntryVWAP']) / tdf['EntryVWAP']) * 100
            
            min_dev = np.floor(tdf['VWAP乖離(%)'].min() * 2) / 2
            max_dev = np.ceil(tdf['VWAP乖離(%)'].max() * 2) / 2
            if np.isnan(min_dev): min_dev = -1.0; max_dev = 1.0
            bins = np.arange(min_dev, max_dev + 0.2, 0.2)
            tdf['Range'] = pd.cut(tdf['VWAP乖離(%)'], bins=bins)
            
            # ★修正：['PnL'] を指定して集計（Named Aggregation形式）
            vwap_stats = tdf.groupby('Range', observed=True).agg(
                Count=('PnL', 'count'), 
                WinRate=('PnL', lambda x: (x > 0).mean()), 
                AvgPnL=('PnL', 'mean')
            ).reset_index()
            
            def format_vwap_interval(i): return f"{i.left:.1f}% ～ {i.right:.1f}%"
            vwap_stats['RangeLabel'] = vwap_stats['Range'].apply(format_vwap_interval)
            
            display_stats = vwap_stats[['RangeLabel', 'Count', 'WinRate', 'AvgPnL']].copy()
            display_stats['WinRate'] = display_stats['WinRate'].apply(lambda x: f"{x:.1%}")
            display_stats['AvgPnL'] = display_stats['AvgPnL'].apply(lambda x: f"{x:+.2%}")
            display_stats['Count'] = display_stats['Count'].astype(str)
            display_stats.columns = ['乖離率レンジ', 'トレード数', '勝率', '平均損益']
            
            st.dataframe(display_stats.style.set_properties(**{'text-align': 'left'}), hide_index=True, use_container_width=True)
            st.divider()

    with tab5: # 時間分析
        for t in tickers:
            tdf = res_df[res_df['Ticker'] == t].copy()
            if tdf.empty: continue
            t_name = ticker_names.get(t, t)
            st.markdown(f"### [{t}] {t_name}")
            st.markdown("##### エントリー時間帯ごとの勝率")
            
            def get_time_range(dt): return f"{dt.strftime('%H:%M')}～{(dt + timedelta(minutes=5)).strftime('%H:%M')}"
            
            # カラム名を 'TimeRange' に統一
            tdf['TimeRange'] = tdf['Entry'].apply(get_time_range)
            
            # ★修正：['PnL'] を指定して集計
            time_stats = tdf.groupby('TimeRange')['PnL'].agg(['count', lambda x: (x>0).mean(), 'mean']).reset_index()
            
            time_disp = time_stats.copy()
            time_disp.columns = ['時間帯', 'count', 'win_rate', 'mean'] # カラム名整理
            time_disp['WinRate'] = time_disp['win_rate'].apply(lambda x: f"{x:.1%}")
            time_disp['AvgPnL'] = time_disp['mean'].apply(lambda x: f"{x:+.2%}")
            time_disp['Count'] = time_disp['count'].astype(str)
            
            # 表示用
            final_disp = time_disp[['時間帯', 'Count', 'WinRate', 'AvgPnL']]
            final_disp.columns = ['時間帯', 'トレード数', '勝率', '平均損益']
            
            st.dataframe(final_disp, hide_index=True, use_container_width=True)
            st.divider()

    with tab6: # 詳細ログ
        log_report = []
        for t in tickers:
            tdf = res_df[res_df['Ticker'] == t].copy().sort_values('Entry', ascending=False).reset_index(drop=True)
            if tdf.empty: continue
            tdf['VWAP乖離(%)'] = ((tdf['In'] - tdf['EntryVWAP']) / tdf['EntryVWAP']) * 100
            t_name = ticker_names.get(t, t)
            log_report.append(f"[{t}] {t_name} 取引履歴")
            log_report.append("-" * 80)
            for i, row in tdf.iterrows():
                entry_str = row['Entry'].strftime('%Y-%m-%d %H:%M')
                if pd.notna(row['EntryVWAP']):
                    vwap_val = int(round(row['EntryVWAP']))
                    vwap_dev = f"{row['VWAP乖離(%)']:+.2f}%"
                    vwap_str = f"{vwap_val} (乖離 {vwap_dev})"
                else:
                    vwap_str = "- (乖離 -)"
                
                # ★修正：買・売の金額を int() で囲み、小数点以下を切り捨て
                line = (
                    f"{entry_str} | "
                    f"前終値：{int(row['PrevClose'])} | 始値：{int(row['DayOpen'])} | "
                    f"{row['Pattern']} | "
                    f"PnL: {row['PnL']:+.2%} | Gap: {row['Gap(%)']:+.2f}% | "
                    f"買：{int(row['In'])} | 売：{int(row['Out'])} | "
                    f"VWAP: {vwap_str} | "
                    f"{row['Reason']}"
                )
                log_report.append(line)
            log_report.append("\n")
        st.caption("右上のコピーボタンで全文コピーできます↓")
        st.code("\n".join(log_report), language="text")
    
    with tab_rank:
        st.markdown("### 🏆 登録銘柄ランキング")
        st.caption("日経225＋αをスキャンして、上位20銘柄を抽出します。") 
        # 進行状況と結果を表示する専用の「器」
        # ※ st.session_state['trigger_rank_scan'] が True なら即座にスキャンを開始するようにしてください。 
        ranking_container = st.container()
        
        # モードを強制的にランキングに変更
        if st.button("ランキング生成（全銘柄スキャン）", type="primary", key="rank_gen_btn_tab", use_container_width=True):
            st.session_state['view_mode'] = 'ranking'
            st.session_state['trigger_rank_scan'] = True
            st.rerun()
        
        if rank_gen_clicked or st.session_state.get('trigger_rank_scan', False):
            # サイドバーからのフラグを一度リセット（無限ループ防止）
            st.session_state['trigger_rank_scan'] = False
            
            rank_list = []
            all_tickers = list(TICKER_NAME_MAP.keys())
            
            with ranking_container:
                with st.status(f"🔍 全{len(all_tickers)}銘柄を分析中...", expanded=True) as status:
                    pb_r = st.progress(0)
                    for i, t in enumerate(all_tickers):
                        status.update(label=f"Scanning {i+1}/{len(all_tickers)}: {t}", state="running")
                        pb_r.progress((i+1)/len(all_tickers))
                        
                        df_r = fetch_intraday(t, start_date, end_date)
                        
                        # ★エラー回避：データが空の場合はスキップ
                        if df_r.empty:
                            continue
                        
                        # 株価範囲の判定
                        current_price = df_r['Close'].iloc[-1]
                        if not (params['p_min'] <= current_price <= params['p_max']):
                            continue

                        # シミュレーション実行
                        p_map, o_map, a_map = fetch_daily_stats_maps(t, start_date)
                        
                        # 前日比の計算
                        change_pct = 0.0
                        try:
                            d_close = df_r['Close'].dropna()
                            if len(d_close) >= 2:
                                last_p = d_close.iloc[-1]
                                prev_p = p_map.get(d_close.index[-1].strftime('%Y-%m-%d'))
                                if prev_p: change_pct = (last_p - prev_p) / prev_p
                        except: pass

                        t_trades = run_ticker_simulation(t, df_r, p_map, o_map, a_map, params)
                        if t_trades:
                            tdf = pd.DataFrame(t_trades)
                            wins = tdf[tdf['PnL'] > 0]; losses = tdf[tdf['PnL'] <= 0]
                            rank_list.append({
                                '銘柄コード': t, '銘柄名': get_ticker_name(t), '前日比': change_pct,
                                '回数': len(tdf), '勝率': len(wins)/len(tdf), 
                                '利益平均': wins['PnL'].mean() if not wins.empty else 0,
                                '損失平均': losses['PnL'].mean() if not losses.empty else 0,
                                'PF': wins['PnL'].sum()/abs(losses['PnL'].sum()) if not losses.empty and losses['PnL'].sum()!=0 else 9.99,
                                '期待値': tdf['PnL'].mean()
                            })
                    
                    status.update(label="✅ スキャン完了！", state="complete", expanded=False)
                    pb_r.empty()

            if rank_list:
                st.session_state['last_rank_df'] = pd.DataFrame(rank_list).sort_values('期待値', ascending=False)
                st.rerun()

        # 結果の表示（計算終了後、または保存された結果がある場合）
        if 'last_rank_df' in st.session_state:
            st.write("---")
            rdf = st.session_state['last_rank_df'].head(20)
            st.dataframe(
                rdf.style.format({
                    '前日比': '{:+.2%}', '勝率': '{:.1%}', '利益平均': '{:+.2%}', '損失平均': '{:+.2%}', '期待値': '{:+.2%}', 'PF': '{:.2f}'
                }), 
                use_container_width=True, hide_index=True, height=735 
            )
            if st.button("ランキング表示をリセット"):
                del st.session_state['last_rank_df']; st.rerun()
