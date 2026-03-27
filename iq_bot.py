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
# Inserite le 10 coppie/indici sintetici principali
ALL_PAIRS = ["R_10", "R_25", "R_50", "R_75", "R_100", "1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V", "1HZ100V"]
icons = {p: "📊" for p in ALL_PAIRS}

fuso_roma = pytz.timezone('Europe/Rome')

# Inizializzazione Session State
if 'mtg_step' not in st.session_state: st.session_state.mtg_step = 0
if 'active_trades' not in st.session_state: st.session_state.active_trades = {}
if 'scanner_on' not in st.session_state: st.session_state.scanner_on = False

# --- 2. LOGICA SEGNALI CON EMA 20/50 ---
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
st.title("🚀 Sentinel AI: Indici Sintetici")
st.caption("Operatività H24 basata su Algoritmi Generativi - Analisi Tecnica Pura")

with st.sidebar:
    st.header("Controllo Scanner")
    if st.button("Lancia/Stop Scanner", type="primary"):
        st.session_state.scanner_on = not st.session_state.scanner_on
    
    st.divider()
    st.subheader("Parametri Tecnici")
    ema_fast = st.number_input("EMA Veloce", value=20)
    ema_slow = st.number_input("EMA Lenta", value=50)
    st.info("Lo scanner ignora i mercati reali. Fokus su Volatility Indices.")

# --- 5. DASHBOARD PRINCIPALE ---
col_stats = st.columns(len(ALL_PAIRS[:5]))
for i, pair in enumerate(ALL_PAIRS[:5]):
    col_stats[i].metric(pair, "LIVE", delta="24/7")

if st.session_state.scanner_on:
    st.toast("Scansione algoritmica in corso...")
    
    # Selezione Asset per Grafico
    selected_asset = st.selectbox("Analisi Dettagliata Asset:", ALL_PAIRS)
    raw_data, _ = get_candles(selected_asset, 60, 100)
    
    if raw_data:
        df = pd.DataFrame(raw_data)
        df['EMA_20'] = ta.ema(df['close'], length=20)
        df['EMA_50'] = ta.ema(df['close'], length=50)
        
        # Grafico con EMA
        fig = make_subplots(rows=1, cols=1)
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Price"))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_20'], line=dict(color='yellow', width=1.5), name="EMA 20"))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_50'], line=dict(color='cyan', width=2), name="EMA 50"))
        
        fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

# --- 6. RIMOZIONE LOGICHE TEMPORALI ---
# Nota: rimosse le funzioni get_market_status, draw_market_map_inverted e get_daily_economic_alerts
# perché non influenzano gli indici sintetici generati da RNG.

st.sidebar.success("✅ Modalità Sintetici Attiva: Nessun ritardo notturno.")

if st.session_state.scanner_on:
    time_module.sleep(10)
    st.rerun()
