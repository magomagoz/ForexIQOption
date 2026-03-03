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
    # Link aggiornati e funzionanti per evitare la barra grigia di errore
    sounds = {
        "buy": "https://actions.google.com/sounds/v1/alarms/beep_short.ogg",
        "win": "https://actions.google.com/sounds/v1/cartoon/clink_vibrant.ogg"
    }
    try:
        st.audio(sounds.get(sound_type, sounds["buy"]), autoplay=True)
    except:
        pass # Evita di mostrare la barra di errore se il caricamento fallisce

st.set_page_config(page_title="Sentinel AI", page_icon="🚀", layout="wide")

# 1. INIZIALIZZAZIONE STATO
if 'connected' not in st.session_state: st.session_state.connected = False
if 'active_trades' not in st.session_state: st.session_state.active_trades = {}
if 'signal_history' not in st.session_state: st.session_state.signal_history = []
if 'local_balance' not in st.session_state: st.session_state.local_balance = 0

# --- SIDEBAR: LOGIN ---
with st.sidebar:
    st.header("⚙️ AI TRADING PLATFORM")
    if not st.session_state.connected:
        email = st.text_input("Email", value="mago_magoz@libero.it")
        password = st.text_input("Password", type="password")
        tipo_conto = st.radio("Seleziona Conto", ["DEMO", "REALE"])
        
        if st.button("🔌 CONNETTI"):
            Iq_obj = IQ_Option(email, password)
            check, reason = Iq_obj.connect()
            
            if check:
                mode = "PRACTICE" if tipo_conto == "DEMO" else "REAL"
                Iq_obj.change_balance(mode)
                st.session_state.iq_client = Iq_obj # Salviamo con questo nome
                st.session_state.connected = True
                st.session_state.account_type = tipo_conto
                st.session_state.local_balance = Iq_obj.get_balance()
                st.rerun()
            else:
                st.error(f"❌ Errore: {reason}")
    else:
        st.success(f"🟢 {st.session_state.account_type} LIVE")
        st.session_state.stake = st.number_input("💰 Stake Virtuale ($)", value=10.0, step=5.0)
        if st.button("🔴 SCOLLEGA"):
            st.session_state.connected = False
            st.rerun()

# --- MAIN DASHBOARD ---
if st.session_state.connected:
    # Usiamo lo stesso nome salvato nella session_state
    Iq = st.session_state.iq_client 
    
    # Header Saldo
    try:
        curr_actual = Iq.get_balance()
    except:
        curr_actual = st.session_state.local_balance

    st.metric(
        label=f"💵 SALDO {st.session_state.account_type} (Sentinel AI)", 
        value=f"{st.session_state.local_balance:.2f} $",
        delta=f"{st.session_state.local_balance - curr_actual:.2f} $ vs IQ"
    )
    
    st.divider()

    # --- SCANNER ---
    st.subheader("👁️ Scanner FOREX")
    col1, col2, col3 = st.columns(3)
    with col1: rsi_buy = st.number_input("🟢 RSI Buy", value=45)
    with col2: rsi_sell = st.number_input("🔴 RSI Sell", value=55)
    with col3: timeframe = st.selectbox("Timeframe", [60, 300], index=0)

    ALL_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"]
    now_ts = time_module.time()
    
    if st.toggle("🔍 Attiva Scansione", value=True):
        for pair in ALL_PAIRS:
            try:
                candles = Iq.get_candles(pair, timeframe, 50, now_ts)
                df = pd.DataFrame(candles)
                df['RSI'] = ta.rsi(df['close'], length=7)
                macd = ta.macd(df['close'], fast=8, slow=17, signal=9)
                
                curr_rsi = df['RSI'].iloc[-1]
                price = df['close'].iloc[-1]
                
                # Logica Segnali
                is_buy = curr_rsi < rsi_buy and macd['MACD_8_17_9'].iloc[-1] > macd['MACDs_8_17_9'].iloc[-1]
                is_sell = curr_rsi > rsi_sell and macd['MACD_8_17_9'].iloc[-1] < macd['MACDs_8_17_9'].iloc[-1]

                if (is_buy or is_sell) and pair not in st.session_state.active_trades:
                    direction = "BUY" if is_buy else "SELL"
                    st.session_state.active_trades[pair] = {'entry_time': now_ts, 'entry_price': price, 'direction': direction}
                    st.session_state.signal_history.append({
                        'time': datetime.now().strftime("%H:%M:%S"), 'pair': pair, 'dir': direction, 
                        'price': f"{price:.5f}", 'rsi': round(curr_rsi, 1), 'result': "⏳ In corso..."
                    })
                    send_telegram_signal(direction, pair, price, curr_rsi, 0)
                    play_trade_sound("buy")
                    st.toast(f"🚀 {direction} su {pair}!", icon="🔥")
            except: continue

    # --- VERIFICA ESITI ---
    for pair, trade in list(st.session_state.active_trades.items()):
        if now_ts - trade['entry_time'] >= 60:
            try:
                res = Iq.get_candles(pair, 60, 1, now_ts)
                exit_p = res[0]['close']
                win = (trade['direction'] == "BUY" and exit_p > trade['entry_price']) or \
                      (trade['direction'] == "SELL" and exit_p < trade['entry_price'])
                
                esito = "✅ WIN" if win else "❌ LOSS"
                stake = st.session_state.get('stake', 10)
                st.session_state.local_balance += (stake * 0.85) if win else -stake

                for s in reversed(st.session_state.signal_history):
                    if s['pair'] == pair and s['result'] == "⏳ In corso...":
                        s['result'] = esito
                        if win: play_trade_sound("win")
                        break
                del st.session_state.active_trades[pair]
            except: continue

    # --- TABELLA E GRAFICO ---
    st.divider()
    
    # Statistiche Win Rate
    if st.session_state.signal_history:
        w = sum(1 for s in st.session_state.signal_history if "✅" in str(s.get('result')))
        l = sum(1 for s in st.session_state.signal_history if "❌" in str(s.get('result')))
        total = w + l
        st.metric("🏆 PERFORMANCE LIVE", f"Win Rate: {(w/total*100 if total>0 else 0):.1f}%", f"W: {w} | L: {l}")

    # Tabella Invertita (Ultimo in alto)
    if st.session_state.signal_history:
        df_show = pd.DataFrame(st.session_state.signal_history).iloc[::-1]
        # Forza le colonne per evitare KeyError
        for c in ['time', 'pair', 'dir', 'price', 'rsi', 'result']:
            if c not in df_show.columns: df_show[c] = "-"
        st.dataframe(df_show[['time', 'pair', 'dir', 'price', 'rsi', 'result']], use_container_width=True, hide_index=True)

    # Refresh automatico
    time_module.sleep(3)
    st.rerun()
