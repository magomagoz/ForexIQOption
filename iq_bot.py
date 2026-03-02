import streamlit as st
import pandas as pd
import pandas_ta as ta
import time as time_module
from iqoptionapi.stable_api import IQ_Option
from datetime import datetime
import requests

# --- 1. SETUP STATO INIZIALE ---
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'active_trades' not in st.session_state:
    st.session_state.active_trades = {}
if 'signal_history' not in st.session_state:
    st.session_state.signal_history = []
if 'scanner_last_update' not in st.session_state:
    st.session_state.scanner_last_update = 0

st.set_page_config(page_title="Sentinel AI", layout="wide")

# --- 2. SIDEBAR DINAMICA (Senza tasti fantasma) ---
with st.sidebar:
    st.header("⚙️ TRADING CONTROL")
    
    # Creiamo un contenitore unico per il Login
    login_container = st.container()
    
    if not st.session_state.connected:
        with login_container:
            email = st.text_input("Email Practice", value="mago_magoz@libero.it", key="login_email")
            password = st.text_input("Password", type="password", key="login_pass")
            if st.button("🔌 CONNETTI ORA", type="primary", use_container_width=True):
                try:
                    Iq = IQ_Option(email, password)
                    check, reason = Iq.connect()
                    if check:
                        st.session_state.iq = Iq
                        st.session_state.connected = True
                        st.session_state.user_email = email
                        st.rerun() # Forza il reset immediato della UI
                    else:
                        st.error(f"Errore: {reason}")
                except Exception as e:
                    st.error(f"Errore connessione: {e}")
    else:
        # Se connesso, il login_container sopra è vuoto. Mostriamo solo lo scollegamento.
        st.success(f"🟢 STATUS: COLLEGATO")
        st.info(f"👤 {st.session_state.get('user_email')}")
        if st.button("🔴 SCOLLEGA ACCOUNT", type="secondary", use_container_width=True):
            st.session_state.connected = False
            if 'iq' in st.session_state:
                del st.session_state['iq']
            st.rerun()

# --- 3. LOGICA DI TRADING (Aggressiva vs Prudente) ---
if st.session_state.connected:
    # Recuperiamo l'istanza Iq
    Iq = st.session_state.iq
    
    # Header Parametri
    c1, c2, c3 = st.columns(3)
    with c1: rsi_buy = st.number_input("🟢 RSI Buy", value=45)
    with c2: rsi_sell = st.number_input("🔴 RSI Sell", value=55)
    with c3: 
        mode = st.radio("Strategia", ["Aggressiva", "Prudente"], horizontal=True)

    # Spiegazione visiva della strategia scelta
    if mode == "Aggressiva":
        st.caption("🚀 **Aggressiva**: Segnale appena l'RSI entra in zona e il MACD è favorevole.")
    else:
        st.caption("🛡️ **Prudente**: Segnale solo se il MACD ha appena effettuato un INCROCIO (Crossover).")
        
    if st.toggle("🔍 AVVIA SCANNER", value=True):
        curr_t = time_module.time()
        
        # Refresh ogni 5 secondi
        if curr_t - st.session_state.scanner_last_update > 5:
            PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "GBPJPY"]
            
            for pair in PAIRS:
                try:
                    candles = Iq.get_candles(pair, 60, 50, curr_t)
                    df = pd.DataFrame(candles)
                    df['RSI'] = ta.rsi(df['close'], length=7)
                    macd_all = ta.macd(df['close'], fast=8, slow=17, signal=9)
                    
                    # Estrazione valori per Crossover
                    c_rsi = df['RSI'].iloc[-1]
                    c_macd = macd_all['MACD_8_17_9'].iloc[-1]
                    c_sig = macd_all['MACDs_8_17_9'].iloc[-1]
                    p_macd = macd_all['MACD_8_17_9'].iloc[-2]
                    p_sig = macd_all['MACDs_8_17_9'].iloc[-2]

                    # --- LOGICA DEI SEGNALI ---
                    if mode == "Aggressiva":
                        # Entra subito se la condizione è presente
                        buy = c_rsi < rsi_buy and c_macd > c_sig
                        sell = c_rsi > rsi_sell and c_macd < c_sig
                    else:
                        # Entra solo se c'è stato l'incrocio nell'ultima candela
                        buy = c_rsi < rsi_buy and (p_macd <= p_sig and c_macd > c_sig)
                        sell = c_rsi > rsi_sell and (p_macd >= p_sig and c_macd < c_sig)

                    if (buy or sell) and pair not in st.session_state.active_trades:
                        direction = "BUY" if buy else "SELL"
                        st.session_state.active_trades[pair] = curr_t
                        st.session_state.signal_history.append({
                            "Ora": datetime.now().strftime("%H:%M:%S"),
                            "Coppia": pair, "Tipo": direction, "RSI": round(c_rsi, 4)
                        })
                        st.toast(f"🔥 NUOVO SEGNALE: {direction} su {pair}")
                except:
                    continue
            
            st.session_state.scanner_last_update = curr_t

    # --- 4. VISUALIZZAZIONE STORICO ---
    st.subheader("📊 Storico Recente")
    if st.session_state.signal_history:
        # Convertiamo in DF per visualizzarlo come nella tua foto
        df_hist = pd.DataFrame(st.session_state.signal_history).tail(10)
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
    
    # Cleanup trades simulati (1 minuto)
    for p in list(st.session_state.active_trades.keys()):
        if time_module.time() - st.session_state.active_trades[p] > 60:
            del st.session_state.active_trades[p]

    # Refresh automatico della pagina per lo scanner
    time_module.sleep(1)
    st.rerun()
else:
    st.warning("👈 Effettua il Login per far sparire i tasti e avviare lo scanner.")
