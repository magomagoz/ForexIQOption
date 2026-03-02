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

# --- CONFIGURAZIONI ---
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")

def send_telegram_signal(signal_type, pair, price, rsi, macd):
    timestamp = datetime.now().strftime("%H:%M:%S")
    message = f"🚀 *SENTINEL AI*\n*{signal_type} - {pair}*\n💰 Prezzo: `{price:.5f}`\n📊 RSI: `{rsi:.1f}`\n⏰ Ora: {timestamp}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=5)
    except: pass

def play_trade_sound(sound_type="buy"):
    sounds = {
        "buy": "https://www.soundjay.com/misc/sounds/bell-ringing-05.wav",
        "sell": "https://www.soundjay.com/misc/sounds/bell-ringing-05.wav"
    }
    st.audio(sounds.get(sound_type, sounds["buy"]), autoplay=True)

st.set_page_config(page_title="Sentinel AI", page_icon="🚀", layout="wide")

# --- LOGICA DI CONNESSIONE E STATO ---
if 'connected' not in st.session_state: st.session_state.connected = False
if 'active_trades' not in st.session_state: st.session_state.active_trades = {}
if 'signal_history' not in st.session_state: st.session_state.signal_history = []

with st.sidebar:
    st.header("⚙️ TRADING IQ OPTION")
    if not st.session_state.connected:
        email = st.text_input("Email", value="mago_magoz@libero.it")
        password = st.text_input("Password", type="password")
        if st.button("🔌 CONNETTI", type="primary", use_container_width=True):
            Iq = IQ_Option(email, password)
            check, reason = Iq.connect()
            if check:
                st.session_state.iq = Iq
                st.session_state.connected = True
                st.rerun()
            else: st.error(f"❌ {reason}")
    else:
        st.success("🟢 STATUS: COLLEGATO")
        if st.button("🔴 SCOLLEGA ACCOUNT", use_container_width=True):
            st.session_state.connected = False
            st.rerun()
        
        # Sessioni
        now_cet = datetime.now().time()
        st.subheader("🌍 SESSIONI")
        for city, (start, end) in {"LONDRA 🇬🇧": (time(9,0), time(18,0)), "NEW YORK 🇺🇸": (time(14,0), time(23,0))}.items():
            status = "🟢" if start <= now_cet <= end else "🔴"
            st.write(f"{status} {city}")

# --- MAIN DASHBOARD ---
if st.session_state.connected:
    Iq = st.session_state.iq

    # PARAMETRI
    col1, col2, col3 = st.columns(3)
    with col1: rsi_buy = st.number_input("🟢 RSI Buy (Sotto)", value=45)
    with col2: rsi_sell = st.number_input("🔴 RSI Sell (Sopra)", value=55)
    with col3: timeframe = st.selectbox("Timeframe", [60, 300], index=0)

    st.session_state.scanner = st.toggle("🔍 Attiva Scanner FOREX", value=True)

    if st.session_state.scanner:
        ALL_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"]
        now_ts = time_module.time()
        
        for pair in ALL_PAIRS:
            try:
                candles = Iq.get_candles(pair, timeframe, 50, now_ts)
                df = pd.DataFrame(candles)
                df['RSI'] = ta.rsi(df['close'], length=7)
                macd = ta.macd(df['close'], fast=8, slow=17, signal=9)
                
                curr_rsi = df['RSI'].iloc[-1]
                curr_macd = macd['MACD_8_17_9'].iloc[-1]
                curr_sig = macd['MACDs_8_17_9'].iloc[-1]
                price = df['close'].iloc[-1]

                # Condizioni
                is_buy = curr_rsi < rsi_buy and curr_macd > curr_sig
                is_sell = curr_rsi > rsi_sell and curr_macd < curr_sig

                # TRIGGER (CORRETTO E INDENTATO)
                if (is_buy or is_sell) and pair not in st.session_state.active_trades:
                    direction = "BUY" if is_buy else "SELL"
                    st.session_state.active_trades[pair] = {'time': now_ts}
                    
                    st.session_state.signal_history.append({
                        'time': datetime.now().strftime("%H:%M:%S"),
                        'pair': pair, 
                        'dir': direction, 
                        'price': f"{price:.5f}", 
                        'rsi': round(curr_rsi, 2)
                    })

                    send_telegram_signal(direction, pair, price, curr_rsi, 0)
                    play_trade_sound()
                    st.toast(f"🚀 SEGNALE {direction} su {pair}!", icon="🔥")

            except: continue

    # GRAFICO
    pair_display = st.selectbox("Seleziona Grafico", ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"])
    # ... (Codice grafico Plotly come prima) ...

    # TABELLA STORICO
    st.subheader("📋 Storico Segnali Recenti")
    if st.session_state.signal_history:
        signals_df = pd.DataFrame(st.session_state.signal_history).tail(15)
        rename_map = {'time': '⏰ ORA', 'pair': '💱 COPPIA', 'dir': '🚀 TIPO', 'price': '💰 PREZZO', 'rsi': '📊 RSI'}
        st.dataframe(signals_df.rename(columns=rename_map), use_container_width=True, hide_index=True)
    else:
        st.info("⏳ Scanner attivo... in attesa di segnali.")

    # Cleanup e Refresh
    for p in list(st.session_state.active_trades.keys()):
        if time_module.time() - st.session_state.active_trades[p]['time'] > 60:
            del st.session_state.active_trades[p]

    time_module.sleep(2)
    st.rerun()
