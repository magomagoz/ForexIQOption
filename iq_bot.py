import streamlit as st
import pandas as pd
import pandas_ta as ta
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from iqoptionapi.stable_api import IQ_Option
from datetime import datetime
from PIL import Image
import base64

# Metti il tuo logo.png nella stessa cartella del file .py
logo = Image.open("banner1.png")  # 400x100px ideale
#st.image(logo, use_column_width=True, caption="IQ Signals PRO")

st.set_page_config(page_title="IQ Signals PRO", page_icon="🚀", layout="wide")

# SIDEBAR
with st.sidebar:
    st.header("⚙️ Config")
    
    # **EMAIL SALVATA AUTOMATICAMENTE**
    email = st.text_input(
        "Email Practice", 
        value=st.session_state['saved_email'],  # ✅ SIEMPRE RIPORTA LA TUA MAIL
        key="email_input",
        help="La tua email viene salvata automaticamente"
    )
    
    # SALVA EMAIL NEL SESSION STATE
    st.session_state['saved_email'] = st.session_state['email_input']    

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
            df['from'] = pd.to_datetime(df['from'], unit='s')
            df.set_index('from', inplace=True)
            
            # INDICATORI
            df['RSI'] = ta.rsi(df['close'], length=14)
            macd = ta.macd(df['close'])
            df['MACD'] = macd['MACD_12_26_9']
            df['MACD_signal'] = macd['MACDs_12_26_9']
            
            # SEGNALI
            df['prev_MACD'] = df['MACD'].shift(1)
            df['prev_signal'] = df['MACD_signal'].shift(1)
            
            df['BUY_SIGNAL'] = (
                (df['RSI'] < rsi_buy) & 
                (df['MACD'] > df['MACD_signal']) &
                (df['prev_MACD'] <= df['prev_signal'])
            )
            
            df['SELL_SIGNAL'] = (
                (df['RSI'] > rsi_sell) & 
                (df['MACD'] < df['MACD_signal']) &
                (df['prev_MACD'] >= df['prev_signal'])
            )
            
            st.session_state['df'] = df
            
            # SALVA NUOVI SEGNALI NELLA CRONOLOGIA
            new_buys = df[df['BUY_SIGNAL'] == True].tail(1)
            new_sells = df[df['SELL_SIGNAL'] == True].tail(1)
            
            if not new_buys.empty:
                signal = {
                    'time': new_buys.index[-1].strftime('%H:%M:%S'),
                    'type': '🟢 BUY',
                    'price': f"{new_buys['close'].iloc[-1]:.5f}",
                    'rsi': f"{new_buys['RSI'].iloc[-1]:.1f}",
                    'macd': f"{new_buys['MACD'].iloc[-1]:.5f}"
                }
                if signal not in st.session_state['signal_history']:
                    st.session_state['signal_history'].insert(0, signal)
                    if len(st.session_state['signal_history']) > 20:
                        st.session_state['signal_history'].pop()
            
            if not new_sells.empty:
                signal = {
                    'time': new_sells.index[-1].strftime('%H:%M:%S'),
                    'type': '🔴 SELL',
                    'price': f"{new_sells['close'].iloc[-1]:.5f}",
                    'rsi': f"{new_sells['RSI'].iloc[-1]:.1f}",
                    'macd': f"{new_sells['MACD'].iloc[-1]:.5f}"
                }
                if signal not in st.session_state['signal_history']:
                    st.session_state['signal_history'].insert(0, signal)
                    if len(st.session_state['signal_history']) > 20:
                        st.session_state['signal_history'].pop()
            
        except Exception as e:
            st.error(f"Dati: {e}")
    
    # GRAFICO
    if 'df' in st.session_state:
        df = st.session_state['df']
        fig = make_subplots(rows=3, cols=1, subplot_titles=('💹 PREZZO', '📊 MACD', '🎯 RSI'),
                          row_heights=[0.55, 0.225, 0.225], vertical_spacing=0.08)
        
        fig.add_trace(go.Scatter(x=df.index[-60:], y=df['close'][-60:], name='Close', 
                               line=dict(width=3, color='#00ff88')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index[-60:], y=df['MACD'][-60:], name='MACD', 
                               line=dict(color='orange', width=2)), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index[-60:], y=df['MACD_signal'][-60:], name='Signal', 
                               line=dict(color='red', width=2)), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index[-60:], y=df['RSI'][-60:], name='RSI', 
                               line=dict(color='purple', width=2.5)), row=3, col=1)
        
        fig.add_hline(y=rsi_buy, line_dash="solid", line_color="#00ff00", line_width=4, 
                     annotation_text="🟢 BUY", row=3, col=1)
        fig.add_hline(y=rsi_sell, line_dash="solid", line_color="#ff0000", line_width=4, 
                     annotation_text="🔴 SELL", row=3, col=1)
        fig.add_hline(y=50, line_dash="dash", line_color="gray", row=3, col=1)
        fig.add_hline(y=0, line_dash="dot", line_color="gray", row=2, col=1)
        
        fig.update_layout(height=650, title=f"🎯 {pair} 1m - IQ OPTION TURBO", 
                        showlegend=False, margin=dict(t=90))
        st.plotly_chart(fig, use_container_width=True)
    
    # PANEL DESTRO
    with right_col:
        st.header("📈 LIVE STATUS")
        if 'df' in st.session_state:
            df = st.session_state['df'].iloc[-1]
            st.metric("💰 PREZZO ENTRATA", f"{df['close']:.5f}")
            st.metric("📊 RSI", f"{df['RSI']:.1f}")
            st.metric("🔥 MACD", f"{df['MACD']:.5f}")
    
    # **CRONOLOGIA SEGNALI IN FONDO**
    st.markdown("---")
    st.subheader("📋 CRONOLOGIA SEGNALI (ultimi 20)")
    
    if 'signal_history' in st.session_state and st.session_state['signal_history']:
        signals_df = pd.DataFrame(st.session_state['signal_history'])
        st.dataframe(signals_df, use_container_width=True, height=300)
    else:
        st.info("⏳ Nessun segnale ancora generato")
