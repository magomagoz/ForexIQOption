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
import requests
from datetime import datetime

# **CONFIG TELEGRAM** (metti nella sidebar)
TELEGRAM_TOKEN = "8235666467:AAGCsvEhlrzl7bH537bJTjsSwQ3P3PMRW10"  # Il tuo token
TELEGRAM_CHAT_ID = "7191509088"         # Il tuo Chat ID

def send_telegram_signal(signal_type, pair, price, rsi, macd):
    """Invia notifica Telegram completa"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    message = f"""
*SENTINEL AI*

*🚀 {signal_type} - {pair.upper()}*
💰 *Prezzo Entrata:* `{price:.5f}`
📊 *RSI:* `{rsi:.1f}`
🔥 *MACD:* `{macd:.5f}`
⏰ *Ora:* {timestamp}

{'🟢 Esito 1m!' if signal_type == 'BUY' else '🔴 ESITO 1m!'}
"""
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, data=payload, timeout=5)
        return response.json()
    except:
        return None

st.set_page_config(page_title="Sentinel AI", page_icon="🚀", layout="wide")

# Metti il tuo logo.png nella stessa cartella del file .py
logo = Image.open("banner.png")  # 400x100px ideale
st.image(logo, use_column_width=True, caption="IQ Signals PRO")

# **SIDEBAR con tasto dinamico CONNETTI/ESCI**
with st.sidebar:
    st.header("⚙️ Trading IQ Option")
    
    # SOLO credenziali se NON connesso
    if not st.session_state.get('connected', False):
        email = st.text_input("Email Practice", value="mago_magoz@libero.it")
        password = st.text_input("Password", type="password")
        
        if st.button("🔗 **CONNETTI**", type="primary", use_container_width=True):
            try:
                Iq = IQ_Option(email, password)
                check, reason = Iq.connect()
                if check:
                    st.session_state['iq'] = Iq
                    st.session_state['connected'] = True
                    st.session_state['email'] = email
                    st.session_state['pair'] = "EURUSD"
                    st.session_state['signal_history'] = []
                    st.success("✅ CONNESSO!")
                    st.balloons()
                    st.rerun()
                else:
                    st.error(f"❌ {reason}")
            except Exception as e:
                st.error(f"❌ {e}")
    
    # **CONFIG TRADING + TASTO ESCI se CONNESSO**
    else:
        st.success(f"🟢 Connesso: {st.session_state['email']}")
        
        st.header("📊 Trading Desk")
        st.session_state['pair'] = st.selectbox(
            "Coppia", 
            ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"], 
            index=0
        )
        st.session_state['rsi_buy'] = st.slider("RSI Buy", 20, 40, 30)
        st.session_state['rsi_sell'] = st.slider("RSI Sell", 60, 80, 70)
        
        # ✅ TASTO ESCI (rosso)
        if st.button("🔴 **ESCI**", type="secondary", use_container_width=True):
            try:
                st.session_state['iq'].close()  # Chiude connessione IQ Option
            except:
                pass
            # Pulisce tutto
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("👋 Disconnesso!")
            st.rerun()

# **POPUP con ❌ INTEGRATO e TELEGRAM**
if st.session_state.get('connected', False) and 'df' in st.session_state:
    df = st.session_state['df']
    pair = st.session_state.get('pair', 'EURUSD')
    
    # NON MOSTRA se chiuso manualmente
    if st.session_state.get('hide_popup', False):
        pass
    else:
        buy_signals = df[df['BUY_SIGNAL'] == True].tail(1)
        sell_signals = df[df['SELL_SIGNAL'] == True].tail(1)
        
        # **POPUP BUY con ❌ DENTRO**
        if not buy_signals.empty:
            latest_buy = buy_signals.iloc[-1]
            st.markdown(f"""
            <div id="buy_popup" style='position: fixed; top: 35%; left: 50%; transform: translate(-50%, -50%);
            background: linear-gradient(45deg, #00ff88, #00cc66); padding: 35px; border-radius: 25px;
            border: 5px solid #00ff00; z-index: 1000; font-size: 28px; font-weight: bold;
            box-shadow: 0 20px 50px rgba(0,255,0,0.7); text-align: center; color: black; 
            min-width: 450px;'>
                <button onclick="document.getElementById('buy_popup').style.display='none'; 
                                window.parent.document.getElementById('close_buy_popup').click();"
                style='position: absolute; top: 12px; right: 15px; background: rgba(255,68,68,0.8); 
                       border: none; border-radius: 50%; width: 45px; height: 45px; font-size: 24px; 
                       color: white; cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.3);'>
                ❌</button>
                <div style='font-size: 36px; margin-bottom: 15px;'>🚀 **BUY {pair.upper()}**</div>
                <div><b>💰 Prezzo Entrata:</b> <span style='color: #00ff00; font-size: 32px;'>{latest_buy['close']:.5f}</span></div>
                <div style='font-size: 34px; color: #00ff00; margin-top: 15px;'>**HIGHER 1 MINUTO ORA!**</div>
            </div>
            """, unsafe_allow_html=True)
            
            # TELEGRAM
            send_telegram_signal("🟢 BUY", pair, latest_buy['close'], latest_buy['RSI'], latest_buy['MACD'])
        
        # **POPUP SELL con ❌ DENTRO**
        elif not sell_signals.empty:
            latest_sell = sell_signals.iloc[-1]
            st.markdown(f"""
            <div id="sell_popup" style='position: fixed; top: 35%; left: 50%; transform: translate(-50%, -50%);
            background: linear-gradient(45deg, #ff4444, #cc0000); padding: 35px; border-radius: 25px;
            border: 5px solid #ff0000; z-index: 1000; font-size: 28px; font-weight: bold;
            box-shadow: 0 20px 50px rgba(255,0,0,0.7); text-align: center; color: white; 
            min-width: 450px;'>
                <button onclick="document.getElementById('sell_popup').style.display='none'; 
                                window.parent.document.getElementById('close_sell_popup').click();"
                style='position: absolute; top: 12px; right: 15px; background: rgba(255,255,255,0.9); 
                       border: none; border-radius: 50%; width: 45px; height: 45px; font-size: 24px; 
                       color: #ff4444; cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.3);'>
                ❌</button>
                <div style='font-size: 36px; margin-bottom: 15px;'>🔻 **SELL {pair.upper()}**</div>
                <div><b>💰 Prezzo Entrata:</b> <span style='color: #ffaaaa; font-size: 32px;'>{latest_sell['close']:.5f}</span></div>
                <div style='font-size: 34px; color: #ffaaaa; margin-top: 15px;'>**LOWER 1 MINUTO ORA!**</div>
            </div>
            """, unsafe_allow_html=True)
            
            # TELEGRAM
            send_telegram_signal("🔴 SELL", pair, latest_sell['close'], latest_sell['RSI'], latest_sell['MACD'])

    # **TASTI NASCOSTI per chiudere popup** (fuori dal controllo popup)
    if st.button("", key="close_buy_popup", help=""):
        st.session_state['hide_popup'] = True
        st.rerun()
    if st.button("", key="close_sell_popup", help=""):
        st.session_state['hide_popup'] = True
        st.rerun()

# **SCANNER MULTI-VALUTE ogni 60s + GRAFICO SINGOLO separato**

# Lista valute principali per scanning
ALL_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"]

# **SCANNER BACKGROUND** (esegue ogni 60s)
if st.session_state.get('connected', False):
    if 'scanner_data' not in st.session_state:
        st.session_state['scanner_data'] = {}
        st.session_state['scanner_last_update'] = 0
    
    # Scanner ogni 60s
    current_time = time.time()
    if current_time - st.session_state['scanner_last_update'] > 60:
        with st.spinner("🔍 Scanning globale..."):
            Iq = st.session_state['iq']
            st.session_state['scanner_data'] = {}
            
            for pair in ALL_PAIRS:
                try:
                    # Ultime 50 candele per analisi veloce
                    candles = Iq.get_candles(pair, 60, 50, time.time())
                    df = pd.DataFrame(candles)
                    df['from'] = pd.to_datetime(df['from'], unit='s')
                    df.set_index('from', inplace=True)
                    
                    # Indicatori rapidi
                    df['RSI'] = ta.rsi(df['close'], length=14)
                    macd = ta.macd(df['close'])
                    df['MACD'] = macd['MACD_12_26_9']
                    df['MACD_signal'] = macd['MACDs_12_26_9']
                    
                    # Segnali
                    latest_rsi = df['RSI'].iloc[-1]
                    macd_bullish = df['MACD'].iloc[-1] > df['MACD_signal'].iloc[-1]
                    
                    signal = ""
                    if latest_rsi < 30 and macd_bullish:
                        signal = "🟢 COMPRA"
                    elif latest_rsi > 70 and not macd_bullish:
                        signal = "🔴 VENDI"
                    else:
                        signal = "⚪ ATTESA SEGNALE"
                    
                    st.session_state['scanner_data'][pair] = {
                        'price': df['close'].iloc[-1],
                        'rsi': latest_rsi,
                        'signal': signal
                    }
                    
                except:
                    st.session_state['scanner_data'][pair] = {'price': 0, 'rsi': 0, 'signal': '❌ ERR'}
            
            st.session_state['scanner_last_update'] = current_time
            st.success("✅ Scanner aggiornato!")

    # **TABELLA SCANNER** (separata dal grafico)
    st.subheader("🔍 SCANNER VALUTE (Aggiornato ogni 60s)")
    if st.session_state.get('scanner_data'):
        scanner_df = pd.DataFrame(st.session_state['scanner_data']).T
        scanner_df = scanner_df[['signal', 'price', 'rsi']].round(5)
        st.dataframe(scanner_df, use_container_width=True, height=400)
        
    Iq = st.session_state['iq']

    # **LIVE STATUS SOPRA GRAFICO - LARGHEZZA PIENA**
    st.subheader("📈 LIVE STATUS")
    if 'df' in st.session_state:
        df = st.session_state['df'].iloc[-1]
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("💰 PREZZO", f"{df['close']:.5f}", delta=None)
        with col2:
            st.metric("📊 RSI", f"{df['RSI']:.1f}", delta=None)
        with col3:
            st.metric("🔥 MACD", f"{df['MACD']:.5f}", delta=None)
        with col4:
            trend = "🟢 BULL" if df['MACD'] > df['MACD_signal'] else "🔴 BEAR"
            st.metric("⚡ TREND", trend, delta=None)

    st.markdown("---")

# **GRAFICO CENTRALE - CORRETTO**
if st.session_state.get('connected', False):
    Iq = st.session_state['iq']
    pair = st.session_state.get('pair', 'EURUSD')  # Dalla sidebar
    rsi_buy = st.session_state.get('rsi_buy', 30)
    rsi_sell = st.session_state.get('rsi_sell', 70)
    
    st.subheader(f"📊 GRAFICO REALTIME - {pair.upper()}")
    
    try:
        # CARICA DATI COPPIA SCELTA (SOLO 1 try!)
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
        
        # CRONOLOGIA SEGNALI
        new_buys = df[df['BUY_SIGNAL'] == True].tail(1)
        new_sells = df[df['SELL_SIGNAL'] == True].tail(1)

        if not new_buys.empty:
            signal = {
                'time': new_buys.index[-1].strftime('%H:%M:%S'),
                'pair': pair,  # ✅ VALUTA AGGIUNTA
                'type': '🟢 BUY',
                'price_entry': f"{new_buys['close'].iloc[-1]:.5f}",
                'rsi': f"{new_buys['RSI'].iloc[-1]:.1f}",
                'macd': f"{new_buys['MACD'].iloc[-1]:.5f}",
                'outcome': '⏳ PENDENTE'  # ✅ ESITO INIZIALE
            }
            if 'signal_history' not in st.session_state:
                st.session_state['signal_history'] = []
            if signal not in st.session_state['signal_history']:
                st.session_state['signal_history'].insert(0, signal)
                if len(st.session_state['signal_history']) > 20:
                    st.session_state['signal_history'].pop()
        
        # SELL
        if not new_sells.empty:
            signal = {
                'time': new_sells.index[-1].strftime('%H:%M:%S'),
                'pair': pair,  # ✅ VALUTA AGGIUNTA
                'type': '🔴 SELL',
                'price_entry': f"{new_sells['close'].iloc[-1]:.5f}",
                'rsi': f"{new_sells['RSI'].iloc[-1]:.1f}",
                'macd': f"{new_sells['MACD'].iloc[-1]:.5f}",
                'outcome': '⏳ PENDENTE'  # ✅ ESITO INIZIALE
            }
            if signal not in st.session_state['signal_history']:
                st.session_state['signal_history'].insert(0, signal)
                if len(st.session_state['signal_history']) > 20:
                    st.session_state['signal_history'].pop()
        
        # GRAFICO CANDELE ULTIMA ORA
        df_last_hour = df.tail(60).copy()
        fig = make_subplots(
            rows=3, cols=1,
            subplot_titles=(f'💹 PREZZO', 'RSI', 'MACD'),
            row_heights=[0.5, 0.175, 0.175],
            vertical_spacing=0.05,
            shared_xaxes=True
        )
        
        # CANDELE
        fig.add_trace(go.Candlestick(
            x=df_last_hour.index, open=df_last_hour['open'], 
            high=df_last_hour['max'], low=df_last_hour['min'], 
            close=df_last_hour['close'], increasing_line_color='#00ff88', 
            decreasing_line_color='#ff4444'), row=1, col=1)
        
        # RSI + LIVELLI
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['RSI'], 
                               line=dict(color='purple', width=2)), row=2, col=1)
        fig.add_hline(y=rsi_buy, line_dash="solid", line_color="#00ff00", line_width=3, row=2, col=1)
        fig.add_hline(y=rsi_sell, line_dash="solid", line_color="#ff0000", line_width=3, row=2, col=1)
        
        # MACD
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['MACD'], 
                               line=dict(color='orange', width=2)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['MACD_signal'], 
                               line=dict(color='red', width=2)), row=3, col=1)
        fig.add_hline(y=0, line_dash="dot", line_color="gray", row=3, col=1)
                
        # RIGHE VERTICALI
        for i in range(0, len(df_last_hour), 5):  # Ogni 5min per non appesantire
            fig.add_vline(x=df_last_hour.index[i], line_dash="dot", line_color="gray", 
                         opacity=0.3, row=1, col=1, layer="below")
            fig.add_vline(x=df_last_hour.index[i], line_dash="dot", line_color="gray", 
                         opacity=0.3, row=2, col=1, layer="below")
            fig.add_vline(x=df_last_hour.index[i], line_dash="dot", line_color="gray", 
                         opacity=0.3, row=3, col=1, layer="below")
            fig.add_vline(x=df_last_hour.index[i], line_dash="dot", line_color="gray", 
                         opacity=0.3, row=4, col=1, layer="below")
        
        fig.update_layout(height=900, showlegend=False, title=f"🎯 {pair.upper()} - ULTIMA ORA", 
                         xaxis_rangeslider_visible=False, margin=dict(t=100))
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"❌ Dati {pair}: {e}")

    # **CHECK ESITI dopo 1 minuto**
    if 'signal_history' in st.session_state:
        for i, signal in enumerate(st.session_state['signal_history']):
            if signal['outcome'] == '⏳ PENDENTE':
                signal_time = datetime.strptime(signal['time'], '%H:%M:%S')
                now = datetime.now().time()
                time_diff = (datetime.combine(datetime.now().date(), now) - datetime.combine(datetime.now().date(), signal_time)).seconds
                
                if time_diff >= 60:  # 1 minuto passato
                    try:
                        # RILEGGE prezzo dopo 1m
                        candles = Iq.get_candles(signal['pair'], 60, 2, time.time())
                        latest_price = pd.DataFrame(candles)['close'].iloc[-1]
                        entry_price = float(signal['price_entry'])
                        
                        # CALCOLA ESITO
                        if signal['type'] == '🟢 COMPRA':
                            outcome = "✅ WIN" if latest_price > entry_price else "❌ LOSS"
                        else:  # SELL
                            outcome = "✅ WIN" if latest_price < entry_price else "❌ LOSS"
                        
                        st.session_state['signal_history'][i]['outcome'] = outcome
                        st.session_state['signal_history'][i]['price_exit'] = f"{latest_price:.5f}"
                        
                    except:
                        st.session_state['signal_history'][i]['outcome'] = '❓ ERRORE'
 
    # **CRONOLOGIA SEGNALI IN FONDO**
    st.markdown("---")
    st.subheader("📋 CRONOLOGIA SEGNALI")
    
    if 'signal_history' in st.session_state and st.session_state['signal_history']:
        signals_df = pd.DataFrame(st.session_state['signal_history'])
        # ORDINA colonne
        cols = ['time', 'pair', 'type', 'price_entry', 'rsi', 'macd', 'outcome']
        signals_df = signals_df[cols]
        st.dataframe(signals_df, use_container_width=True, height=350)
    else:
        st.info("⏳ Nessun segnale generato")
