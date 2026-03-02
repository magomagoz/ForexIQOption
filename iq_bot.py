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

# --- INIZIALIZZAZIONE STATO (Previene errori riga 76) ---
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'active_trades' not in st.session_state:
    st.session_state.active_trades = {}
if 'signal_history' not in st.session_state:
    st.session_state.signal_history = []
if 'scanner_last_update' not in st.session_state:
    st.session_state.scanner_last_update = 0

# --- CONFIG E FUNZIONI ---
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")

def send_telegram_signal(signal_type, pair, price, rsi, macd):
    if not TELEGRAM_TOKEN: return
    timestamp = datetime.now().strftime("%H:%M:%S")
    message = f"🚀 *SENTINEL AI*\n*{signal_type} - {pair}*\n💰 *Prezzo Entrata:* `{price}`\n📊 *RSI:* `{rsi}`\n⏰ *Ora* {timestamp}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=5)
    except: pass

def play_trade_sound(sound_type="alert"):
    sounds = {"buy": "https://www.soundjay.com/misc/sounds/bell-ringing-05.wav", "win": "https://www.soundjay.com/misc/sounds/ching-15.wav"}
    st.audio(sounds.get(sound_type, sounds["buy"]), autoplay=True)

st.set_page_config(page_title="Sentinel AI", page_icon="🚀", layout="wide")

# Logo
try:
    logo = Image.open("banner.png")
    st.image(logo, use_column_width=True, caption="IQ Signals PRO")
except:
    st.image("https://via.placeholder.com/800x100/0066cc/white?text=SENTINEL+AI", use_column_width=True)

# **SIDEBAR - GESTIONE LOGIN**
with st.sidebar:
    st.header("⚙️ **TRADING IQ OPTION**")
    
    # Se NON è connesso, mostra i campi di login
    if not st.session_state.connected:
        email = st.text_input("Email Practice", value="mago_magoz@libero.it")
        password = st.text_input("Password", type="password")
        
        if st.button("🔌 **CONNETTI**", type="secondary", use_container_width=True):
            try:
                Iq = IQ_Option(email, password)
                check, reason = Iq.connect()
                if check:
                    st.session_state['iq'] = Iq
                    st.session_state.connected = True
                    st.session_state['pair'] = "EURUSD"
                    st.success("✅ CONNESSO!")
                    st.rerun()
                else:
                    st.error(f"❌ {reason}")
            except Exception as e:
                st.error(f"❌ Errore: {str(e)}")
    
    # Se È connesso, mostra solo il tasto disconnetti e info sessione
    else:
        st.success(f"🟢 Account: {st.session_state.get('email', 'Collegato')}")
        if st.button("🔴 **DISCONNETTI**", type="secondary", use_container_width=True):
            try:
                st.session_state['iq'].close()
            except:
                pass
            # Reset completo dello stato
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# --- CORE LOGIC: IL MOTORE DEI SEGNALI ---
# Usiamo .get per sicurezza totale
if st.session_state.get('connected'):
    Iq = st.session_state.iq
    
    col1, col2, col3 = st.columns(3)
    with col1: rsi_buy = st.number_input("🟢 RSI Buy (Sotto)", value=45)
    with col2: rsi_sell = st.number_input("🔴 RSI Sell (Sopra)", value=55)
    with col3: mode = st.radio("Modalità", ["Aggressiva", "Prudente"], index=0)

    st.session_state.scanner = st.toggle("🔍 ATTIVA SCANNER AUTOMATICO", value=True)

    if st.session_state.get('scanner'):
        curr_t = time_module.time()
        # Scan ogni 5 secondi
        if curr_t - st.session_state.get('scanner_last_update', 0) > 5:
            ALL_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "GBPJPY"]
            
            for pair in ALL_PAIRS:
                try:
                    candles = Iq.get_candles(pair, 60, 40, curr_t)
                    df = pd.DataFrame(candles)
                    df['RSI'] = ta.rsi(df['close'], length=7)
                    macd_df = ta.macd(df['close'], fast=8, slow=17, signal=9)
                    
                    curr_rsi = df['RSI'].iloc[-1]
                    curr_macd = macd_df['MACD_8_17_9'].iloc[-1]
                    curr_signal = macd_df['MACDs_8_17_9'].iloc[-1]
                    price = df['close'].iloc[-1]

                    buy_condition = curr_rsi < rsi_buy and curr_macd > curr_signal
                    sell_condition = curr_rsi > rsi_sell and curr_macd < curr_signal

                    if (buy_condition or sell_condition) and pair not in st.session_state.active_trades:
                        direction = "BUY" if buy_condition else "SELL"
                        
                        st.session_state.active_trades[pair] = {
                            'entry_price': price,
                            'entry_time': curr_t,
                            'direction': direction
                        }
                        
                        st.toast(f"🚀 {direction} {pair}", icon="🔥")
                        play_trade_sound()
                        send_telegram_signal(direction, pair, price, round(curr_rsi, 2), 0)
                        
                        st.session_state.signal_history.append({
                            'time': datetime.now().strftime("%H:%M:%S"),
                            'pair': pair,
                            'type': direction,
                            'rsi': f"{curr_rsi:.1f}",
                            'price': price
                        })
                except:
                    continue
            
            st.session_state.scanner_last_update = curr_t

    # --- VISUALIZZAZIONE ---
    st.subheader("📡 Segnali Rilevati (Aggressivi)")
    if st.session_state.signal_history:
        st.table(pd.DataFrame(st.session_state.signal_history).tail(5))
    else:
        st.info("Scanner in esecuzione... Attendo movimenti di mercato.")

    # Cleanup trades simulati
    for p in list(st.session_state.active_trades.keys()):
        if time_module.time() - st.session_state.active_trades[p]['entry_time'] > 60:
            del st.session_state.active_trades[p]

    time_module.sleep(1)
    st.rerun()
else:
    # Messaggio se non connesso
    st.warning("👈 Effettua il login nella sidebar per avviare Sentinel AI")
