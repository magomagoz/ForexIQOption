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

# --- CONFIGURAZIONI E TELEGRAM (Tuo codice originale) ---
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")

def send_telegram_signal(signal_type, pair, price, rsi, macd):
    timestamp = datetime.now().strftime("%H:%M:%S")
    message = f"🚀 *SENTINEL AI*\n*{signal_type} - {pair}*\n💰 Prezzo: `{price:.5f}`\n📊 RSI: `{rsi:.1f}`\n⏰ {timestamp}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=5)
    except: pass

st.set_page_config(page_title="Sentinel AI", page_icon="🚀", layout="wide")

# Logo
try:
    logo = Image.open("banner.png")
    st.image(logo, use_column_width=True, caption="IQ Signals PRO")
except:
    st.image("https://via.placeholder.com/800x100/0066cc/white?text=SENTINEL+AI", use_column_width=True)

# --- LOGICA DI CONNESSIONE ---
if 'connected' not in st.session_state: st.session_state.connected = False
if 'active_trades' not in st.session_state: st.session_state.active_trades = {}
if 'signal_history' not in st.session_state: st.session_state.signal_history = []

with st.sidebar:
    st.header("⚙️ TRADING IQ OPTION")
    if not st.session_state.connected:
        email = st.text_input("Email", value="mago_magoz@libero.it")
        password = st.text_input("Password", type="password")
        if st.button("🔌 CONNETTI"):
            Iq = IQ_Option(email, password)
            check, reason = Iq.connect()
            if check:
                st.session_state.iq = Iq
                st.session_state.connected = True
                st.rerun()
    else:
        st.success("🟢 IQ OPTION LIVE")
        # --- SESSIONI DI MERCATO ---
        now_cet = datetime.now().time()
        st.subheader("🌍 SESSIONI DI MERCATO")
        for city, (start, end) in {"LONDRA 🇬🇧": (time(9,0), time(18,0)), "NEW YORK 🇺🇸": (time(14,0), time(23,0)), "SYDNEY 🇦🇺": (time(23,0), time(8,0)), "TOKYO 🇯🇵": (time(1,0), time(10,0))}.items():
            status = "🟢 " if start <= now_cet <= end else "🔴 "
            st.write(f"{status} {city}")

# --- MAIN DASHBOARD ---
if st.session_state.connected:
    Iq = st.session_state.iq
    
    # 1. PARAMETRI AGGRESSIVI (MODIFICATI PER RILEVARE DI PIÙ)
    col1, col2, col3 = st.columns(3)
    with col1: 
        rsi_buy = st.number_input("🟢 RSI Buy (Soglia Alta = +Segnali)", value=45) # Alzato da 28
    with col2: 
        rsi_sell = st.number_input("🔴 RSI Sell (Soglia Bassa = +Segnali)", value=55) # Abbassato da 72
    with col3:
        timeframe = st.selectbox("Timeframe", [60, 300], index=0)

    # 2. SCANNER MULTI-PAIR
    st.session_state.scanner = st.toggle("🔍 Attiva Scanner FOREX", value=True)
    
    if st.session_state.scanner:
        ALL_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"]
        placeholder = st.empty()
        
        for pair in ALL_PAIRS:
            try:
                candles = Iq.get_candles(pair, timeframe, 50, time_module.time())
                df = pd.DataFrame(candles)
                df['RSI'] = ta.rsi(df['close'], length=7) # Periodo corto = più nervoso/più segnali
                macd = ta.macd(df['close'], fast=8, slow=17, signal=9)
                
                curr_rsi = df['RSI'].iloc[-1]
                curr_macd = macd['MACD_8_17_9'].iloc[-1]
                curr_sig = macd['MACDs_8_17_9'].iloc[-1]
                price = df['close'].iloc[-1]

                # --- LOGICA APERTA (AGGIUSTATA) ---
                # Non aspettiamo più il cross perfetto, basta che la direzione sia corretta
                is_buy = curr_rsi < rsi_buy and curr_macd > curr_sig
                is_sell = curr_rsi > rsi_sell and curr_macd < curr_sig

                if (is_buy or is_sell) and pair not in st.session_state.active_trades:
                    direction = "BUY" if is_buy else "SELL"
                    st.session_state.active_trades[pair] = {'time': time_module.time(), 'price': price}
                    st.session_state.signal_history.append({
                        'time': datetime.now().strftime("%H:%M:%S"),
                        'pair': pair, 'dir': direction, 'rsi': round(curr_rsi, 1)
                    })
                    send_telegram_signal(direction, pair, price, curr_rsi, 0)
                    #st.toast(f"🚀 SEGNALE {direction} su {pair}!", icon="🔥")

                    # Sostituisci st.toast con questo:
                    with st.container():
                        st.warning(f" NUOVO SEGNALE: {direction} su {pair}! 🚀", icon="🔥")
                        if st.button(f"OK, Visto ({pair})", key=f"btn_{pair}_{curr_t}"):
                            st.rerun()

            
            except: continue

    # 3. GRAFICO (Il tuo Plotly originale)
    pair_display = st.selectbox("Seleziona Grafico", ALL_PAIRS)
    candles = Iq.get_candles(pair_display, 60, 100, time_module.time())
    df_plot = pd.DataFrame(candles)
    df_plot['RSI'] = ta.rsi(df_plot['close'], length=7)
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['open'], high=df_plot['max'], low=df_plot['min'], close=df_plot['close']), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['RSI'], line=dict(color='purple')), row=2, col=1)
    fig.add_hline(y=rsi_buy, line_color="green", row=2, col=1)
    fig.add_hline(y=rsi_sell, line_color="red", row=2, col=1)
    fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- TABELLA SEGNALI VERIFICATA ---
    st.header("📋 Storico Segnali Recenti")
    if st.session_state.signal_history:
        # CORREZIONE: Selezione colonne con nomi esatti e doppie quadre
        signals_df = pd.DataFrame(st.session_state.signal_history).tail(50)
        
        # Rinominia colonne per estetica
        display_df = signals_df[['time', 'pair', 'dir', 'price', 'rsi']].copy()
        display_df.columns = [['⏰ ORA', '💱 COPPIA', 'AZIONE', '💰 PREZZO', '📊 RSI']]
        
        st.dataframe(display_df, use_container_width=True, height=300, hide_index=True)
    else:
        st.info("⏳ In attesa di segnali...")

    # Pulizia active trades e rerun
    for p in list(st.session_state.active_trades.keys()):
        if time_module.time() - st.session_state.active_trades[p]['time'] > 60:
            del st.session_state.active_trades[p]
    
    time_module.sleep(2)
    st.rerun()
    
    #if st.session_state.get('signal_history', []):
        
