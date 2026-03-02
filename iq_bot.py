import streamlit as st
import pandas as pd
import pandas_ta as ta
import time as time_module
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from iqoptionapi.stable_api import IQ_Option
from PIL import Image
import requests
from datetime import datetime, time

# --- CONFIG E FUNZIONI (Invariate) ---
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")

def send_telegram_signal(signal_type, pair, price, rsi, macd):
    if not TELEGRAM_TOKEN: return
    timestamp = datetime.now().strftime("%H:%M:%S")
    message = f"🚀 *SENTINEL AI*\n*{signal_type} - {pair}*\nPrezzo: `{price}`\nRSI: `{rsi}`\nOra: {timestamp}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=5)
    except: pass

def play_trade_sound(sound_type="alert"):
    sounds = {"buy": "https://www.soundjay.com/misc/sounds/bell-ringing-05.wav", "win": "https://www.soundjay.com/misc/sounds/ching-15.wav"}
    st.audio(sounds.get(sound_type, sounds["buy"]), autoplay=True)

st.set_page_config(page_title="Sentinel AI - Aggressive Mode", page_icon="🚀", layout="wide")

# --- LOGICA DI CONNESSIONE (Invariata) ---
if 'connected' not in st.session_state: st.session_state.connected = False

with st.sidebar:
    st.header("⚙️ CONFIGURAZIONE")
    if not st.session_state.connected:
        email = st.text_input("Email", value="tua_email@esempio.com")
        password = st.text_input("Password", type="password")
        if st.button("🔌 CONNETTI"):
            Iq = IQ_Option(email, password)
            check, reason = Iq.connect()
            if check:
                st.session_state.iq = Iq
                st.session_state.connected = True
                st.rerun()
    else:
        st.success("🟢 Connesso")
        if st.button("🔴 DISCONNETTI"):
            st.session_state.connected = False
            st.rerun()

# --- CORE LOGIC: IL MOTORE DEI SEGNALI ---
if st.session_state.connected:
    Iq = st.session_state.iq
    
    # Inizializzazione parametri se mancanti
    if 'active_trades' not in st.session_state: st.session_state.active_trades = {}
    if 'signal_history' not in st.session_state: st.session_state.signal_history = []
    if 'scanner_last_update' not in st.session_state: st.session_state.scanner_last_update = 0

    col1, col2, col3 = st.columns(3)
    with col1: rsi_buy = st.number_input("🟢 RSI Buy (Sotto)", value=45) # Alzato da 28 a 45
    with col2: rsi_sell = st.number_input("🔴 RSI Sell (Sopra)", value=55) # Abbassato da 72 a 55
    with col3: mode = st.radio("Modalità", ["Aggressiva (Sempre)", "Prudente (Solo Incroci)"], index=0)

    st.session_state.scanner = st.toggle("🔍 ATTIVA SCANNER AUTOMATICO", value=True)

    if st.session_state.scanner:
        curr_t = time_module.time()
        if curr_t - st.session_state.scanner_last_update > 5: # Scan veloce ogni 5 secondi
            ALL_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "GBPJPY"]
            
            for pair in ALL_PAIRS:
                try:
                    # Candele a 1 minuto
                    candles = Iq.get_candles(pair, 60, 40, curr_t)
                    df = pd.DataFrame(candles)
                    
                    # Indicatori veloci
                    df['RSI'] = ta.rsi(df['close'], length=7)
                    macd_df = ta.macd(df['close'], fast=8, slow=17, signal=9)
                    
                    curr_rsi = df['RSI'].iloc[-1]
                    curr_macd = macd_df['MACD_8_17_9'].iloc[-1]
                    curr_signal = macd_df['MACDs_8_17_9'].iloc[-1]
                    price = df['close'].iloc[-1]

                    # --- LOGICA DI TRIGGER APERTA ---
                    buy_condition = curr_rsi < rsi_buy and curr_macd > curr_signal
                    sell_condition = curr_rsi > rsi_sell and curr_macd < curr_signal

                    if (buy_condition or sell_condition) and pair not in st.session_state.active_trades:
                        direction = "BUY" if buy_condition else "SELL"
                        
                        # Esecuzione Trade Virtuale (per test segnali)
                        st.session_state.active_trades[pair] = {
                            'entry_price': price,
                            'entry_time': curr_t,
                            'direction': direction
                        }
                        
                        msg = f"{'🟢' if direction == 'BUY' else '🔴'} TRADE {direction} su {pair}"
                        st.toast(msg, icon="🚀")
                        play_trade_sound()
                        send_telegram_signal(direction, pair, price, round(curr_rsi, 2), 0)
                        
                        st.session_state.signal_history.append({
                            'time': datetime.now().strftime("%H:%M:%S"),
                            'pair': pair,
                            'type': direction,
                            'rsi': f"{curr_rsi:.1f}",
                            'price': price
                        })

                except Exception as e:
                    continue
            
            st.session_state.scanner_last_update = curr_t

    # --- VISUALIZZAZIONE ---
    st.subheader("📡 Segnali Rilevati (Aggressivi)")
    if st.session_state.signal_history:
        st.table(pd.DataFrame(st.session_state.signal_history).tail(5))
    else:
        st.info("In attesa di segnali... Con i valori attuali (45/55) ne vedrai molti a breve.")

    # Pulizia automatica trade simulati dopo 60s
    for p in list(st.session_state.active_trades.keys()):
        if time_module.time() - st.session_state.active_trades[p]['entry_time'] > 60:
            del st.session_state.active_trades[p]

    time_module.sleep(1)
    st.rerun()
