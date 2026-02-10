import streamlit as st
import pandas as pd
import pandas_ta as ta
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from iqoptionapi.stable_api import IQ_Option
from datetime import datetime

st.set_page_config(page_title="IQ Signals PRO", page_icon="🚀", layout="wide")

# LOGO CENTRALE
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown("""
    <div style='text-align: center; padding: 20px 0;'>
        <h1 style='color: #00ff88; font-size: 48px; margin: 0; font-weight: bold; 
                   text-shadow: 2px 2px 4px rgba(0,0,0,0.5);'>
            🚀 IQ SIGNALS PRO
        </h1>
        <p style='color: #ffffff; font-size: 20px; margin: 5px 0 0 0;'>
            Turbo Options 1m • RSI + MACD • Alert Centrali
        </p>
    </div>
    """, unsafe_allow_html=True)

# SIDEBAR
with st.sidebar:
    st.header("⚙️ Config")
    email = st.text_input("Email Practice", type="password")
    password = st.text_input("Password", type="password")
    pair = st.selectbox("Coppia", ["EURUSD", "GBPUSD", "USDJPY"])
    rsi_buy = st.slider("RSI Buy Level", 20, 40, 30)
    rsi_sell = st.slider("RSI Sell Level", 60, 80, 70)
    
    if st.button("🔗 CONNETTI PRACTICE", use_container_width=True):
        try:
            Iq = IQ_Option(email, password)
            check, reason = Iq.connect()
            if check:
                st.session_state['iq'] = Iq
                st.session_state['connected'] = True
                st.session_state['email'] = email
                st.session_state['pair'] = pair
                st.success("✅ CONNESSO!")
                st.balloons()
                st.session_state['signal_history'] = []
            else:
                st.error(f"❌ {reason}")
        except Exception as e:
            st.error(f"❌ {e}")

# **POPUP ALERT CENTRALE COMPLETO**
if st.session_state.get('connected', False) and 'df' in st.session_state:
    df = st.session_state['df']
    
    # Controlla NUOVI segnali
    buy_signals = df[df['BUY_SIGNAL'] == True]
    sell_signals = df[df['SELL_SIGNAL'] == True]
    
    if not buy_signals.empty:
        latest_buy = buy_signals.iloc[-1]
        st.markdown(f"""
        <div style='position: fixed; top: 25%; left: 50%; transform: translate(-50%, -50%);
        background: linear-gradient(45deg, #00ff88, #00cc66); padding: 30px; border-radius: 25px;
        border: 5px solid #00ff00; z-index: 1000; font-size: 28px; font-weight: bold;
        box-shadow: 0 20px 50px rgba(0,255,0,0.7); text-align: center; color: black; 
        min-width: 400px;'>
            <div style='font-size: 36px; margin-bottom: 15px;'>🚀 **SEGNALE BUY**</div>
            <div><b>💰 Prezzo Entrata:</b> <span style='color: #00ff00; font-size: 32px;'>{latest_buy['close']:.5f}</span></div>
            <div><b>📊 RSI:</b> <span style='color: #ff00ff;'>{latest_buy['RSI']:.1f}</span></div>
            <div><b>🔥 MACD:</b> <span style='color: #ff8800;'>{latest_buy['MACD']:.5f}</span></div>
            <div style='font-size: 34px; color: #00ff00; margin-top: 15px;'>**HIGHER 1 MINUTO ORA!**</div>
        </div>
        """, unsafe_allow_html=True)
    
    elif not sell_signals.empty:
        latest_sell = sell_signals.iloc[-1]
        st.markdown(f"""
        <div style='position: fixed; top: 25%; left: 50%; transform: translate(-50%, -50%);
        background: linear-gradient(45deg, #ff4444, #cc0000); padding: 30px; border-radius: 25px;
        border: 5px solid #ff0000; z-index: 1000; font-size: 28px; font-weight: bold;
        box-shadow: 0 20px 50px rgba(255,0,0,0.7); text-align: center; color: white; 
        min-width: 400px;'>
            <div style='font-size: 36px; margin-bottom: 15px;'>🔻 **SEGNALE SELL**</div>
            <div><b>💰 Prezzo Entrata:</b> <span style='color: #ffaaaa; font-size: 32px;'>{latest_sell['close']:.5f}</span></div>
            <div><b>📊 RSI:</b> <span style='color: #ffaa00;'>{latest_sell['RSI']:.1f}</span></div>
            <div><b>🔥 MACD:</b> <span style='color: #ff5500;'>{latest_sell['MACD']:.5f}</span></div>
            <div style='font-size: 34px; color: #ffaaaa; margin-top: 15px;'>**LOWER 1 MINUTO ORA!**</div>
        </div>
        """, unsafe_allow_html=True)

# MAIN LOGIC
if st.session_state.get('connected', False):
    # COUNTDOWN
    next_refresh = st.session_state.get('next_refresh', time.time() + 60)
    remaining = max(0, next_refresh - time.time())
    st.metric("⏱️ AUTO-REFRESH TRA", f"{int(remaining)}s")
    
    if remaining <= 0:
        st.session_state['next_refresh'] = time.time() + 60
        st.rerun()
    
    Iq = st.session_state['iq']
    left_col, right_col = st.columns([3, 1])
    
    with left_col:
        st.subheader("📊 GRAFICO REALTIME")
        try:
            candles = Iq.get_candles(pair, 60, 150, time.time())
            df = pd.DataFrame(candles)
            df['from'] = pd.to_datetime(df['from'], unit=
