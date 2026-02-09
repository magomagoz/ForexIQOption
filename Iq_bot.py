import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import time

st.title("Analizzatore Segnali Forex 1m (Demo Educativa)")

symbol = st.text_input("Pair Forex (es. EURUSD=X)", "EURUSD=X")
period = st.selectbox("Periodo", ["1d", "5d", "1mo"])

if st.button("Analizza Segnali"):
    data = yf.download(symbol, period=period, interval="1m")
    data['RSI'] = ta.rsi(data['Close'], length=14)
    macd = ta.macd(data['Close'])
    data['MACD'] = macd['MACD_12_26_9']
    data['MACD_signal'] = macd['MACDs_12_26_9']
    
    # Segnale buy semplice: RSI < 30 e MACD > signal
    data['Signal'] = 0
    data.loc[(data['RSI'] < 30) & (data['MACD'] > data['MACD_signal']), 'Signal'] = 1
    
    st.line_chart(data[['Close', 'RSI']])
    st.dataframe(data.tail(10)[['Close', 'RSI', 'MACD', 'MACD_signal', 'Signal']])
    
    buys = data[data['Signal'] == 1]
    if not buys.empty:
        st.success(f"Ultimi segnali BUY: {len(buys)}")
        st.dataframe(buys[['Close']].tail())
