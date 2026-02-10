import streamlit as st
import pandas as pd
import pandas_ta as ta
import time
from iqoptionapi.stable_api import IQ_Option  # pip install iqoptionapi

st.title("🔍 IQ Option Practice Data Reader + Segnali Forex 1m")

# Login (usa solo account PRACTICE)
email = st.text_input("Email IQ Option Practice", type="password")
password = st.text_input("Password Practice", type="password")
pair = st.selectbox("Coppia Forex", ["EURUSD", "GBPUSD", "USDJPY"])

if st.button("🔗 Connetti a IQ Option Practice"):
    if email and password:
        with st.spinner("Connessione..."):
            try:
                Iq = IQ_Option(email, password)
                check, reason = Iq.connect()
                
                if check:
                    st.success("✅ Connesso al conto Practice!")
                    st.session_state['iq'] = Iq
                    st.session_state['connected'] = True
                else:
                    st.error(f"❌ Errore login: {reason}")
            except Exception as e:
                st.error(f"❌ Errore: {e}")

if 'connected' in st.session_state:
    Iq = st.session_state['iq']
    
    if st.button("📊 Carica Candele 1m + Analizza Segnali", type="primary"):
        with st.spinner("Lettura dati IQ Option..."):
            try:
                # Ottieni balance practice
                balance = Iq.get_balance()
                st.info(f"💰 Balance Practice: ${balance}")
                
                # Carica ultime 100 candele 1m
                candles = Iq.get_candles(pair, 60, 100, time.time())
                df = pd.DataFrame(candles)
                df['from'] = pd.to_datetime(df['from'], unit='s')
                df.set_index('from', inplace=True)
                
                # Calcola indicatori
                df['RSI'] = ta.rsi(df['close'], length=14)
                macd = ta.macd(df['close'])
                df['MACD'] = macd['MACD_12_26_9']
                df['MACD_signal'] = macd['MACDs_12_26_9']
                
                # SEGNALE BUY: RSI < 35 + MACD crossover
                df['prev_MACD'] = df['MACD'].shift(1)
                df['prev_signal'] = df['MACD_signal'].shift(1)
                df['BUY_SIGNAL'] = (
                    (df['RSI'] < 35) & 
                    (df['MACD'] > df['MACD_signal']) &
                    (df['prev_MACD'] <= df['prev_signal'])
                )
                
                st.session_state['df'] = df
                
                # Grafici
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("💹 Prezzo")
                    st.line_chart(df['close'].tail(50))
                with col2:
                    st.subheader("📈 RSI + MACD")
                    st.line_chart(df[['RSI', 'MACD', 'MACD_signal']].tail(50))
                
                # Segnali
                signals = df[df['BUY_SIGNAL'] == True]
                if not signals.empty:
                    st.markdown("## 🚀 **SEGNALI BUY RILEVATI**")
                    st.dataframe(signals[['close', 'RSI', 'MACD']].tail(5).round(4))
                    st.balloons()
                else:
                    st.info("ℹ️ Nessun segnale BUY al momento")
                
            except Exception as e:
                st.error(f"❌ Errore dati: {e}")

# Auto-refresh ogni 30 secondi
time.sleep(1)
if st.button("🔄 Refresh Dati (30s)"):
    st.rerun()
