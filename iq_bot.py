import streamlit as st
import pandas as pd
import pandas_ta as ta
import time as time_module
from iqoptionapi.stable_api import IQ_Option
from PIL import Image
import requests
from datetime import datetime

# --- 1. INIZIALIZZAZIONE STATO (Assoluta priorità) ---
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'signal_history' not in st.session_state:
    st.session_state.signal_history = []
if 'active_trades' not in st.session_state:
    st.session_state.active_trades = {}
if 'scanner_last_update' not in st.session_state:
    st.session_state.scanner_last_update = 0

# --- 2. CONFIG E FUNZIONI ---
def send_telegram_signal(signal_type, pair, price, rsi):
    token = st.secrets.get("TELEGRAM_TOKEN", "")
    chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
    if not token: return
    msg = f"🚀 *SENTINEL AI - {signal_type}*\n💶 Pair: {pair}\n💰 *Prezzo:* {price}\n📊 *RSI:* {rsi}\n🔥 *MACD:* {macd}\n⏰ *Ora:* {timestamp}\n⚠️ *Entra Ora!*"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try: requests.post(url, data={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})
    except: pass

st.set_page_config(page_title="Sentinel AI", page_icon="🚀", layout="wide")

# Logo
try:
    logo = Image.open("banner.png")
    st.image(logo, use_column_width=True, caption="IQ Signals PRO")
except:
    st.image("https://via.placeholder.com/800x100/0066cc/white?text=SENTINEL+AI", use_column_width=True)
    
# **SIDEBAR COMPLETO**
with st.sidebar:
    st.header("⚙️ **TRADING IQ OPTION**")    
    if not st.session_state.connected:
        # VISIBILE SOLO PRIMA DEL LOGIN
        email = st.text_input("Email", value="mago_magoz@libero.it")
        password = st.text_input("Password", type="password")
        if st.button("🔌 CONNETTI ORA", type="secondary"):
            Iq = IQ_Option(email, password)
            check, reason = Iq.connect()
            if check:
                st.session_state.iq = Iq
                st.session_state.connected = True
                st.rerun()
            else:
                st.error(f"Errore: {reason}")
    else:
        # VISIBILE SOLO DOPO IL LOGIN
        st.success("🟢 STATUS: COLLEGATO")
        if st.button("🚪 SCOLLEGA ACCOUNT", type="primary"):
            st.session_state.connected = False
            if 'iq' in st.session_state: del st.session_state['iq']
            st.rerun()

# --- 4. DASHBOARD PRINCIPALE ---
if st.session_state.connected:
    Iq = st.session_state.iq
    
    col1, col2, col3 = st.columns(3)
    with col1: rsi_buy = st.number_input("🟢 RSI Buy", value=45)
    with col2: rsi_sell = st.number_input("🔴 RSI Sell", value=55)
    with col3: 
        # SPIEGAZIONE MODALITÀ
        mode = st.radio("Strategia", ["Aggressiva", "Prudente"], help="Aggressiva: segnale immediato | Prudente: aspetta incrocio MACD")

    if st.toggle("🔍 AVVIA SCANNER", value=True):
        curr_t = time_module.time()
        if curr_t - st.session_state.scanner_last_update > 5:
            PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"]
            
            for pair in PAIRS:
                try:
                    candles = Iq.get_candles(pair, 60, 50, curr_t)
                    df = pd.DataFrame(candles)
                    df['RSI'] = ta.rsi(df['close'], length=7)
                    macd = ta.macd(df['close'])
                    
                    c_rsi = df['RSI'].iloc[-1]
                    c_macd = macd.iloc[-1, 0] # MACD Line
                    c_sig = macd.iloc[-1, 2]  # Signal Line
                    p_macd = macd.iloc[-2, 0] # MACD Precedente
                    p_sig = macd.iloc[-2, 2]  # Signal Precedente

                    # --- LOGICA DIFFERENZIATA ---
                    if mode == "Aggressiva":
                        buy = c_rsi < rsi_buy and c_macd > c_sig
                        sell = c_rsi > rsi_sell and c_macd < c_sig
                    else:
                        # PRUDENTE: Richiede il crossover (la linea MACD deve aver appena tagliato la Signal)
                        buy = c_rsi < rsi_buy and p_macd <= p_sig and c_macd > c_sig
                        sell = c_rsi > rsi_sell and p_macd >= p_sig and c_macd < c_sig

                    if (buy or sell) and pair not in st.session_state.active_trades:
                        direction = "BUY" if buy else "SELL"
                        st.session_state.active_trades[pair] = curr_t
                        st.session_state.signal_history.append({
                            "Ora": datetime.now().strftime("%H:%M"),
                            "Coppia": pair, "Tipo": direction, "RSI": round(c_rsi, 1)
                        })
                        send_telegram_signal(direction, pair, df['close'].iloc[-1], round(c_rsi, 1))
                        st.toast(f"Segnale {direction} su {pair}")
                except: continue
            
            st.session_state.scanner_last_update = curr_t

    st.subheader("📊 Storico Recente")
    st.table(pd.DataFrame(st.session_state.signal_history).tail(5))
    
    # Cleanup trades simulati
    for p in list(st.session_state.active_trades.keys()):
        if time_module.time() - st.session_state.active_trades[p] > 60:
            del st.session_state.active_trades[p]
            
    time_module.sleep(1)
    st.rerun()
else:
    st.info("👋 Benvenuto! Usa la barra a sinistra per connetterti ai mercati.")
