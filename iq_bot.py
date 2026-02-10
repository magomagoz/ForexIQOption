import streamlit as st
import pandas as pd
import pandas_ta as ta
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from iqoptionapi.stable_api import IQ_Option
from datetime import datetime
import base64

st.set_page_config(page_title="IQ Signals PRO", page_icon="🚀", layout="wide")

# SOUNDS (base64 per cross-browser)
def play_sound(sound_type):
    """Suona alert BUY/SELL"""
    if sound_type == "buy":
        sound_b64 = "data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAo"
    else:  # sell
        sound_b64 = "data:audio/wav;base64,UklGRp4GAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAo"
    
    st.markdown(f"""
    <audio autoplay="true">
        <source src="{sound_b64}" type="audio/wav">
    </audio>
    """, unsafe_allow_html=True)

# LOGO CENTRALE
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown("""
    <div style='text-align: center; padding: 20px 0;'>
        <h1 style='color: #00ff88; font-size: 48px; margin: 0; font-weight: bold; 
                   text-shadow: 2px 2px 4px rgba(0,0,0,0.5);'>
            🚀 IQ SIGNALS PRO
        </h1>
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
                if 'signal_history' not in st.session_state:
                    st.session_state['signal_history'] = []
                st.rerun()
            else:
                st.error(f"❌ {reason}")
        except Exception as e:
            st.error(f"❌ {e}")

# **POPUP MODALE CENTRALE CON BOTTONE CHIUDI**
if st.session_state.get('connected', False):
    # Controlla nuovi segnali
    if 'df' in st.session_state:
        df = st.session_state['df']
        buy_signals = df[df['BUY_SIGNAL'] == True].tail(1)
        sell_signals = df[df['SELL_SIGNAL'] == True].tail(1)
        
        # NUOVO BUY
        if not buy_signals.empty and st.session_state.get('show_buy_alert', False):
            latest = buy_signals.iloc[-1]
            play_sound("buy")
            st.session_state['current_alert'] = {
                'type': 'BUY', 'price': latest['close'], 'rsi': latest['RSI'], 
                'macd': latest['MACD'], 'time': latest.name
            }
        
        # NUOVO SELL  
        elif not sell_signals.empty and st.session_state.get('show_sell_alert', False):
            latest = sell_signals.iloc[-1]
            play_sound("sell")
            st.session_state['current_alert'] = {
                'type': 'SELL', 'price': latest['close'], 'rsi': latest['RSI'], 
                'macd': latest['MACD'], 'time': latest.name
            }
    
    # **MOSTRA POPUP SE ATTIVO**
    if st.session_state.get('show_alert_modal', False):
        alert = st.session_state['current_alert']
        st.markdown(f"""
        <div style='position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
        background: linear-gradient(45deg, {'#00ff88' if alert['type']=='BUY' else '#ff4444'}, 
        {'#00cc66' if alert['type']=='BUY' else '#cc0000'}); 
        padding: 40px; border-radius: 30px; border: 6px solid 
        {'#00ff00' if alert['type']=='BUY' else '#ff0000'};
        z-index: 2000; font-size: 28px; font-weight: bold; text-align: center; 
        color: black; min-width: 450px; max-width: 500px; box-shadow: 0 25px 60px rgba(0,0,0,0.8);'>
            <div style='font-size: 44px; margin-bottom: 20px;'>
                {'🚀🟢 BUY' if alert['type']=='BUY' else '🔻🔴 SELL'}
            </div>
            <div style='font-size: 36px; margin: 10px 0;'>
                💰 **ENTRATA: {alert['price']:.5f}**
            </div>
            <div style='font-size: 26px; margin: 8px 0;'>
                📊 **RSI: {alert['rsi']:.1f}** | 🔥 **MACD: {alert['macd']:.5f}**
            </div>
            <div style='font-size: 38px; margin: 20px 0; color: 
            {"#00ff00" if alert['type']=='BUY' else "#ffaaaa"};'>
                **{alert['type']} 1 MINUTO ORA!**
            </div>
            <div style='margin-top: 25px;'>
                <button onclick='document.querySelector(\"[data-testid=\\\\\"stAlert\\\\\"]\").style.display=\\\\"none\\\\";' 
                style='background: rgba(255,255,255,0.9); color: black; border: none; 
                padding: 15px 30px; border-radius: 25px; font-size: 20px; font-weight: bold; 
                cursor: pointer; box-shadow: 0 5px 15px rgba(0,0,0,0.3);'>
                ✅ CHIUDI ALERT
                </button>
            </div>
        </div>
        <style>
        body {{ overflow: hidden; }}
        </style>
        """, unsafe_allow_html=True)

# MAIN CONTENT
if st.session_state.get('connected', False):
    # COUNTDOWN
    #next_refresh = st.session_state.get('next_refresh', time.time() + 60)
    #remaining =
