import streamlit as st
import pandas as pd
import pandas_ta as ta
import pytz
import time as time_module
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json
import os
import websocket
from datetime import datetime

# --- 1. CONFIGURAZIONI E ASSET ---
DERIV_APP_ID = "1089"
INITIAL_STAKE = 100.0

DERIV_TOKEN = st.sidebar.text_input("🔑 Deriv API Token", value = "FfHFQiTimFwP7mi", type="password")

ALL_PAIRS = ["R_50", "R_75", "R_100", "1HZ50V", "1HZ75V", "1HZ100V"]
icons = {p: "📊" for p in ALL_PAIRS}

fuso_roma = pytz.timezone('Europe/Rome')

# Inizializzazione Session State
if 'mtg_step' not in st.session_state: st.session_state.mtg_step = 0
if 'active_trades' not in st.session_state: st.session_state.active_trades = {}
if 'scanner_on' not in st.session_state: st.session_state.scanner_on = False

# --- LOGICA DI SEGNALE: TRIPLA CONVERGENZA ---
def get_tripla_convergenza_signal(df):
    # 1. Indicatori
    df['EMA_20'] = ta.ema(df['close'], length=20)
    df['EMA_50'] = ta.ema(df['close'], length=50)
    df['RSI'] = ta.rsi(df['close'], length=7)
    bb = ta.bbands(df['close'], length=20, std=2.20)
    
    df['BB_Upper'] = bb['BBU_20_2.2']
    df['BB_Lower'] = bb['BBL_20_2.2']
    
    last = df.iloc[-1]
    
    # Logica BUY: Trend UP (Close > EMA50) E Prezzo < BB Lower E RSI < 20
    if (last['close'] > last['EMA_50']) and (last['close'] <= last['BB_Lower']) and (last['RSI'] <= 20):
        return "BUY"
    
    # Logica SELL: Trend DOWN (Close < EMA50) E Prezzo > BB Upper E RSI > 80
    elif (last['close'] < last['EMA_50']) and (last['close'] >= last['BB_Upper']) and (last['RSI'] >= 80):
        return "SELL"
        
    return "WAIT"

# --- FUNZIONI API DERIV ---
def send_deriv_request(request):
    try:
        ws = websocket.create_connection(f"wss://ws.binaryws.com/websockets/v3?app_id={DERIV_APP_ID}")
        if DERIV_TOKEN:
            ws.send(json.dumps({"authorize": DERIV_TOKEN}))
            ws.recv() # Ricevi conferma autorizzazione
        ws.send(json.dumps(request))
        res = json.loads(ws.recv())
        ws.close()
        return res
    except Exception as e:
        st.error(f"Errore connessione: {e}")
        return None

def execute_trade(symbol, direction, amount, multiplier, sl, tp):
    req = {
        "buy": 1,
        "price": amount,
        "parameters": {
            "amount": amount,
            "basis": "stake",
            "contract_type": "MULTUP" if direction == "BUY" else "MULTDOWN",
            "currency": "USD",
            "multiplier": multiplier,
            "symbol": symbol,
            "limit_order": {
                "stop_loss": sl,
                "take_profit": tp
            }
        }
    }
    return send_deriv_request(req)

# --- LOGICA SEGNALE (TRIPLA CONVERGENZA) ---
def check_signal(df, rsi_buy, rsi_sell, bb_std):
    df['EMA_20'] = ta.ema(df['close'], length=20)
    df['EMA_50'] = ta.ema(df['close'], length=50)
    df['RSI'] = ta.rsi(df['close'], length=7)
    bb = ta.bbands(df['close'], length=20, std=bb_std)
    
    # Pulizia nomi colonne BB
    bbu_col = f'BBU_20_{bb_std}'
    bbl_col = f'BBL_20_{bb_std}'
    
    last = df.iloc[-1]
    
    # BUY: Trend UP + Touch Lower BB + RSI Low
    if last['close'] > last['EMA_50'] and last['close'] <= bb[bbl_col].iloc[-1] and last['RSI'] <= rsi_buy:
        return "BUY"
    # SELL: Trend DOWN + Touch Upper BB + RSI High
    if last['close'] < last['EMA_50'] and last['close'] >= bb[bbu_col].iloc[-1] and last['RSI'] >= rsi_sell:
        return "SELL"
    return "WAIT"
    
def get_signals(df):
    # Indicatori
    df['EMA_20'] = ta.ema(df['close'], length=20)
    df['EMA_50'] = ta.ema(df['close'], length=50)
    df['RSI'] = ta.rsi(df['close'], length=7)
    bb = ta.bbands(df['close'], length=20, std=2.5)
    df['BB_Upper'] = bb['BBU_20_2.5']
    df['BB_Lower'] = bb['BBL_20_2.5']
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Logica: Trend (EMA) + Ipervenduto/comprato (RSI + BB)
    # BUY: Prezzo sopra EMA50 (Trend Up) e tocca BB Lower + RSI basso
    if last['close'] > last['EMA_50'] and last['close'] < last['BB_Lower'] and last['RSI'] < 30:
        return "BUY"
    # SELL: Prezzo sotto EMA50 (Trend Down) e tocca BB Upper + RSI alto
    elif last['close'] < last['EMA_50'] and last['close'] > last['BB_Upper'] and last['RSI'] > 70:
        return "SELL"
    return "WAIT"

# --- 3. CONNESSIONE DATI ---
def get_candles(pair, timeframe_sec, count):
    try:
        ws = websocket.create_connection(f"wss://ws.binaryws.com/websockets/v3?app_id={DERIV_APP_ID}", timeout=5)
        req = {"ticks_history": pair, "end": "latest", "count": count, "style": "candles", "granularity": timeframe_sec}
        ws.send(json.dumps(req))
        res = json.loads(ws.recv())
        ws.close()
        if 'candles' in res:
            return res['candles'], "DERIV_ALGO"
        return None, "No data"
    except: return None, "Error"

# --- 4. INTERFACCIA STREAMLIT ---
st.set_page_config(page_title="Sentinel AI - Synthetic Edition", layout="wide")
st.image("banner.png")
st.title("🛡️ Algoritmo Indici Sintetici")
st.caption("Operatività H24 - Analisi Tecnica Pura")

if 'scanner_on' not in st.session_state: st.session_state.scanner_on = False

with st.sidebar:
    st.header("Parametri Algoritmo")
    st.write("**Filtri Attivi:**")
    st.info("- EMA 20/50 (Trend)\n- BB 20, 2.20 (Volatilità)\n- RSI 20/80 (Oscillatore)")
    if st.button("START/STOP SCANNER", type="primary", use_container_width=True):
        st.session_state.scanner_on = not st.session_state.scanner_on

# Visualizzazione 10 Asset
cols = st.columns(5)
for i, pair in enumerate(ALL_PAIRS):
    with cols[i % 5]:
        st.button(f"📊 {pair}", key=f"btn_{pair}", use_container_width=True)


if st.session_state.scanner_on:
    st.subheader("📡 Monitoraggio Real-Time")
    
    for pair in ALL_PAIRS:
        candles, _ = get_candles(pair, 60, 100)
        if candles:
            df = pd.DataFrame(candles)
            signal = get_tripla_convergenza_signal(df)
            
            if signal != "WAIT":
                st.warning(f"🚨 SEGNALE {signal} RILEVATO SU {pair}!")
                # Qui si può inserire la logica di esecuzione trade o notifica Telegram
    
    st.divider()
    st.subheader("Parametri Tecnici")
    ema_fast = st.number_input("EMA Veloce", value=20)
    ema_slow = st.number_input("EMA Lenta", value=50)
    st.info("Lo scanner ignora i mercati reali. Fokus su Volatility Indices.")


    # Session State per i trade attivi
if 'active_contracts' not in st.session_state: st.session_state.active_contracts = {}

# --- SIDEBAR: CONTROLLO REALTIME ---
with st.sidebar:
    st.header("🎮 Trading Control Panel")
    st.session_state.auto_trade = st.toggle("🤖 Esecuzione Automatica", value=False)
    
    st.divider()
    st.subheader("💰 Gestione Rischio")
    stake = st.number_input("Stake ($)", value=10.0, step=1.0)
    mult = st.selectbox("Moltiplicatore", [10, 20, 30, 50, 100], index=2)
    
    st.divider()
    st.subheader("🎯 Target Real-Time")
    # Questi valori possono essere modificati mentre il bot gira
    tp_val = st.slider("Take Profit ($)", 1.0, 50.0, 5.0)
    sl_val = st.slider("Stop Loss ($)", 1.0, 10.0, 5.0)
    
    st.divider()
    st.subheader("📈 Sensibilità")
    rsi_b = st.number_input("RSI Buy Level", value=20)
    rsi_s = st.number_input("RSI Sell Level", value=80)
    bb_dev = st.number_input("BB Std Dev", value=2.2)

# --- 5. DASHBOARD PRINCIPALE ---
col_stats = st.columns(len(ALL_PAIRS[:5]))
for i, pair in enumerate(ALL_PAIRS[:5]):
    col_stats[i].metric(pair, "LIVE", delta="24/7")

if st.session_state.scanner_on:
    st.toast("Scansione algoritmica in corso...")

    st.divider()


    # Grafico dettagliato dell'ultimo asset
    st.divider()
    selected = st.selectbox("Analisi Tecnica Dettagliata:", ALL_PAIRS)
    c_data, _ = get_candles(selected, 60, 100)
    if c_data:
        df_plot = pd.DataFrame(c_data)
        df_plot['EMA_20'] = ta.ema(df_plot['close'], length=20)
        df_plot['EMA_50'] = ta.ema(df_plot['close'], length=50)
        df_plot['RSI'] = ta.rsi(df_plot['close'], length=7)
        bb_plot = ta.bbands(df_plot['close'], length=20, std=2.20)
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
        # Prezzo e EMA/BB
        fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['open'], high=df_plot['high'], low=df_plot['low'], close=df_plot['close'], name="Candele"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_plot.index, y=bb_plot['BBU_20_2.2'], line=dict(color='rgba(173, 216, 230, 0.5)'), name="BB Upper"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_plot.index, y=bb_plot['BBL_20_2.2'], line=dict(color='rgba(173, 216, 230, 0.5)'), fill='tonexty', name="BB Lower"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['EMA_50'], line=dict(color='orange', width=2), name="EMA 50 (Trend)"), row=1, col=1)
        
        # RSI
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['RSI'], line=dict(color='magenta'), name="RSI"), row=2, col=1)
        fig.add_hline(y=20, line_color="green", row=2, col=1)
        fig.add_hline(y=80, line_color="red", row=2, col=1)

        fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

    st.rerun()
    
# --- 6. RIMOZIONE LOGICHE TEMPORALI ---
# Nota: rimosse le funzioni get_market_status, draw_market_map_inverted e get_daily_economic_alerts
# perché non influenzano gli indici sintetici generati da RNG.

st.sidebar.success("✅ Modalità Sintetici Attiva: Nessun ritardo notturno.")


# --- MAIN UI ---
st.title("🛡️ Sentinel AI Pro - Automation")

if not DERIV_TOKEN:
    st.warning("Inserisci il tuo API Token nella sidebar per iniziare.")
else:
    # Loop Scanner
    for pair in ALL_PAIRS:
        # 1. Recupero Dati
        res_candles = send_deriv_request({
            "ticks_history": pair, "count": 100, "end": "latest", "style": "candles", "granularity": 60
        })
        
        if res_candles and 'candles' in res_candles:
            df = pd.DataFrame(res_candles['candles'])
            signal = check_signal(df, rsi_b, rsi_s, bb_dev)
            
            # 2. Logica Esecuzione
            if signal != "WAIT" and st.session_state.auto_trade:
                if pair not in st.session_state.active_contracts:
                    st.info(f"Tentativo di apertura {signal} su {pair}...")
                    trade_res = execute_trade(pair, signal, stake, mult, sl_val, tp_val)
                    
                    if "buy" in trade_res:
                        st.success(f"Trade aperto! ID: {trade_res['buy']['contract_id']}")
                        st.session_state.active_contracts[pair] = trade_res['buy']['contract_id']
                    else:
                        st.error(f"Errore: {trade_res.get('error', {}).get('message')}")

    # Visualizzazione Trade Attivi
    if st.session_state.active_contracts:
        st.divider()
        st.subheader("📑 Posizioni Aperte")
        for p, c_id in list(st.session_state.active_contracts.items()):
            col1, col2 = st.columns([3, 1])
            col1.write(f"Asset: **{p}** | Contract ID: `{c_id}`")
            if col2.button("Chiudi", key=f"close_{c_id}"):
                # Logica per chiusura forzata (sell)
                close_res = send_deriv_request({"sell": c_id, "price": 0})
                if "sell" in close_res:
                    st.toast(f"Chiuso {p} con profitto: {close_res['sell']['profit']}")
                    del st.session_state.active_contracts[p]
                    st.rerun()

if st.session_state.scanner_on:
    time_module.sleep(10)
    st.rerun()
