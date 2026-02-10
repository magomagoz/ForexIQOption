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
🚀 *IQ SIGNALS PRO* 🚀

*{signal_type} {pair}*
💰 *Prezzo Entrata:* `{price:.5f}`
📊 *RSI:* `{rsi:.1f}`
🔥 *MACD:* `{macd:.5f}`
⏰ *Ora:* {timestamp}

{'🟢 HIGHER 1m ORA!' if signal_type == 'BUY' else '🔴 LOWER 1m ORA!'}
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

st.set_page_config(page_title="IQ Signals PRO", page_icon="🚀", layout="wide")

# Metti il tuo logo.png nella stessa cartella del file .py
logo = Image.open("banner1.png")  # 400x100px ideale
st.image(logo, use_column_width=True, caption="IQ Signals PRO")

# SIDEBAR
with st.sidebar:
    st.header("⚙️ Config")
    email = st.text_input("Email Practice", value="mago_magoz@libero.it")
    password = st.text_input("Password", type="password")
    pair = st.selectbox("Coppia", ["EURUSD", "GBPUSD", "USDJPY"])
    rsi_buy = st.slider("RSI Buy Level", 20, 40, 30)
    rsi_sell = st.slider("RSI Sell Level", 60, 80, 70)
    
    if st.button("🔗 CONNETTI PRACTICE", use_container_width=True):
        try:
            Iq = IQ_Option(email, password)
            check, reason = Iq.connect()
            if check:
                st.session_state['iq'] = Iq
                st.session_state['connected'] = True
                st.session_state['email'] = email
                st.session_state['pair'] = pair
                st.success("✅ CONNESSO!")
                st.balloons()
                st.session_state['signal_history'] = []
            else:
                st.error(f"❌ {reason}")
        except Exception as e:
            st.error(f"❌ {e}")

# **POPUP ALERT CENTRALE COMPLETO**
if st.session_state.get('connected', False) and 'df' in st.session_state:
    df = st.session_state['df']
    
    # Controlla NUOVI segnali
    buy_signals = df[df['BUY_SIGNAL'] == True]
    sell_signals = df[df['SELL_SIGNAL'] == True]
    
    if not buy_signals.empty:
        latest_buy = buy_signals.iloc[-1]
        st.markdown(f"""
        <div style='position: fixed; top: 25%; left: 50%; transform: translate(-50%, -50%);
        background: linear-gradient(45deg, #00ff88, #00cc66); padding: 30px; border-radius: 25px;
        border: 5px solid #00ff00; z-index: 1000; font-size: 28px; font-weight: bold;
        box-shadow: 0 20px 50px rgba(0,255,0,0.7); text-align: center; color: black; 
        min-width: 400px;'>
            <div style='font-size: 36px; margin-bottom: 15px;'>🚀 **SEGNALE BUY**</div>
            <div><b>💰 Prezzo Entrata:</b> <span style='color: #00ff00; font-size: 32px;'>{latest_buy['close']:.5f}</span></div>
            <div><b>📊 RSI:</b> <span style='color: #ff00ff;'>{latest_buy['RSI']:.1f}</span></div>
            <div><b>🔥 MACD:</b> <span style='color: #ff8800;'>{latest_buy['MACD']:.5f}</span></div>
            <div style='font-size: 34px; color: #00ff00; margin-top: 15px;'>**HIGHER 1 MINUTO ORA!**</div>
        </div>
        """, unsafe_allow_html=True)
    
    elif not sell_signals.empty:
        latest_sell = sell_signals.iloc[-1]
        st.markdown(f"""
        <div style='position: fixed; top: 25%; left: 50%; transform: translate(-50%, -50%);
        background: linear-gradient(45deg, #ff4444, #cc0000); padding: 30px; border-radius: 25px;
        border: 5px solid #ff0000; z-index: 1000; font-size: 28px; font-weight: bold;
        box-shadow: 0 20px 50px rgba(255,0,0,0.7); text-align: center; color: white; 
        min-width: 400px;'>
            <div style='font-size: 36px; margin-bottom: 15px;'>🔻 **SEGNALE SELL**</div>
            <div><b>💰 Prezzo Entrata:</b> <span style='color: #ffaaaa; font-size: 32px;'>{latest_sell['close']:.5f}</span></div>
            <div><b>📊 RSI:</b> <span style='color: #ffaa00;'>{latest_sell['RSI']:.1f}</span></div>
            <div><b>🔥 MACD:</b> <span style='color: #ff5500;'>{latest_sell['MACD']:.5f}</span></div>
            <div style='font-size: 34px; color: #ffaaaa; margin-top: 15px;'>**LOWER 1 MINUTO ORA!**</div>
        </div>
        """, unsafe_allow_html=True)
    
    # **NUOVO BUY → TELEGRAM**
    new_buys = df[df['BUY_SIGNAL'] == True].tail(1)
    if not new_buys.empty:
        latest = new_buys.iloc[-1]
        send_telegram_signal("🟢 BUY", pair, latest['close'], latest['RSI'], latest['MACD'])
    
    # **NUOVO SELL → TELEGRAM**  
    new_sells = df[df['SELL_SIGNAL'] == True].tail(1)
    if not new_sells.empty:
        latest = new_sells.iloc[-1]
        send_telegram_signal("🔴 SELL", pair, latest['close'], latest['RSI'], latest['MACD'])

# MAIN LOGIC
if st.session_state.get('connected', False):
# **BARRA 60s CHE SCORRE VERSO 0 (tempo reale)**

# Calcola progresso REALE (da 60s a 0s)
seconds_left = 60 - (time.time() % 60)
progress = seconds_left / 60.0

st.markdown(f"""
<div style='background: linear-gradient(90deg, #333 0%, #333 100%); 
            height: 25px; border-radius: 15px; overflow: hidden; 
            border: 3px solid #00ff88; box-shadow: inset 0 2px 4px rgba(0,0,0,0.3);'>
    <div style='background: linear-gradient(90deg, #00ff88, #00cc66, #00ff88); 
                height: 100%; width: {progress*100:.1f}%; 
                animation: none; transition: width 0.1s linear; 
                box-shadow: 0 0 20px rgba(0,255,136,0.7);'>
    </div>
</div>
<div style='text-align: center; color: #00ff88; font-weight: bold; font-size: 20px; 
           text-shadow: 0 0 10px rgba(0,255,136,0.5); margin-top: 5px;'>
    ⏱️ {int(seconds_left)} SECONDI al prossimo scan
</div>
""", unsafe_allow_html=True)

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
        with st.spinner("🔍 Scanning tutte le valute..."):
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
                        signal = "🟢 BUY"
                    elif latest_rsi > 70 and not macd_bullish:
                        signal = "🔴 SELL"
                    else:
                        signal = "⚪ WAIT"
                    
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
    st.subheader("🔍 SCANNER MULTI-VALUTE (Aggiornato 60s)")
    if st.session_state.get('scanner_data'):
        scanner_df = pd.DataFrame(st.session_state['scanner_data']).T
        scanner_df = scanner_df[['signal', 'price', 'rsi']].round(5)
        st.dataframe(scanner_df, use_container_width=True, height=400)
    
    # **GRAFICO DEDICATO** (solo la coppia scelta)
    st.subheader(f"📊 DETTAGLIO {pair}")
    # [qui il tuo grafico candele dettagliato per 'pair' selezionato]
    
    # Barra progresso scanner
    if st.session_state.get('scanner_last_update'):
        time_since = time.time() - st.session_state['scanner_last_update']
        progress = max(0, 60 - time_since) / 60.0
        st.markdown(f"""
        <div style='background: #333; height: 20px; border-radius: 10px; overflow: hidden;'>
            <div style='background: linear-gradient(90deg, #00ff88, #00cc66); 
                        height: 100%; width: {progress*100}%; transition: width 1s linear;'>
            </div>
        </div>
        <div style='text-align: center; color: #00ff88; font-size: 14px;'>
            Prossimo scan: {int(progress*60)}s
        </div>
        """, unsafe_allow_html=True)

    # **LIVE STATUS SEMPLICE** (solo titolo - sopra grafico)
    #st.markdown("""
    #<div style='background: linear-gradient(45deg, #1e3c72, #2a5298); 
               #color: white; padding: 20px; border-radius: 15px; text-align: center; 
               #margin: 20px 0; box-shadow: 0 10px 30px rgba(0,0,0,0.3);'>
        #<h2 style='margin: 0; font-size: 28px;'>📈 LIVE TRADING STATUS</h2>
    #</div>
    #""", unsafe_allow_html=True)
    
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

    # GRAFICO (sotto live status - larghezza piena)
    st.subheader("📊 GRAFICO REALTIME")
    try:
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
        
        # SALVA NUOVI SEGNALI NELLA CRONOLOGIA
        new_buys = df[df['BUY_SIGNAL'] == True].tail(1)
        new_sells = df[df['SELL_SIGNAL'] == True].tail(1)
            
        if not new_buys.empty:
            signal = {
                'time': new_buys.index[-1].strftime('%H:%M:%S'),
                'type': '🟢 BUY',
                'price': f"{new_buys['close'].iloc[-1]:.5f}",
                'rsi': f"{new_buys['RSI'].iloc[-1]:.1f}",
                'macd': f"{new_buys['MACD'].iloc[-1]:.5f}"
            }
            if signal not in st.session_state['signal_history']:
                st.session_state['signal_history'].insert(0, signal)
                if len(st.session_state['signal_history']) > 20:
                    st.session_state['signal_history'].pop()
            
        if not new_sells.empty:
            signal = {
                'time': new_sells.index[-1].strftime('%H:%M:%S'),
                'type': '🔴 SELL',
                'price': f"{new_sells['close'].iloc[-1]:.5f}",
                'rsi': f"{new_sells['RSI'].iloc[-1]:.1f}",
                'macd': f"{new_sells['MACD'].iloc[-1]:.5f}"
        }
            if signal not in st.session_state['signal_history']:
                st.session_state['signal_history'].insert(0, signal)
                if len(st.session_state['signal_history']) > 20:
                    st.session_state['signal_history'].pop()
            
    except Exception as e:
        st.error(f"Dati: {e}")
    
    # GRAFICO
    # **GRAFICO CAND ELE GIAPPONESI ULTIMA ORA + RIGHE VERTICALI OGNI MINUTO**
    
    # Filtra ultima ora (60 candele 1m)
    df_last_hour = df.tail(60).copy()
    
    # Crea grafico con 4 subplot (candele + 3 indicatori)
    fig = make_subplots(
        rows=4, cols=1,
        subplot_titles=('💹 CANDELE 1m (ULTIMA ORA)', '📊 RSI', '🔥 MACD', '💰 PREZZO'),
        row_heights=[0.5, 0.175, 0.175, 0.15],
        vertical_spacing=0.05,
        shared_xaxes=True  # ✅ STESSO TEMPO per tutti!
    )
    
    # **CANDELE GIAPPONESI**
    fig.add_trace(
        go.Candlestick(
            x=df_last_hour.index,
            open=df_last_hour['open'],
            high=df_last_hour['max'],
            low=df_last_hour['min'],
            close=df_last_hour['close'],
            name="Candele",
            increasing_line_color='#00ff88', 
            decreasing_line_color='#ff4444'
        ),
        row=1, col=1
    )
    
    # **RSI**
    fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['RSI'], 
                            name='RSI', line=dict(color='purple', width=2)), row=2, col=1)
    fig.add_hline(y=rsi_buy, line_dash="solid", line_color="#00ff00", line_width=3, row=2, col=1)
    fig.add_hline(y=rsi_sell, line_dash="solid", line_color="#ff0000", line_width=3, row=2, col=1)
    
    # **MACD** 
    fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['MACD'], 
                            name='MACD', line=dict(color='orange', width=2)), row=3, col=1)
    fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['MACD_signal'], 
                            name='Signal', line=dict(color='red', width=2)), row=3, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color="gray", row=3, col=1)
    
    # **PREZZO CLOSE** (linea per facile lettura)
    fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['close'], 
                            name='Prezzo', line=dict(color='#00ff88', width=2)), row=4, col=1)
    
    # **RIGHE VERTICALI OGNI MINUTO** (linee tratteggiate grigie)
    for i in range(0, len(df_last_hour), 1):  # Ogni candela = 1 minuto
        fig.add_vline(x=df_last_hour.index[i], line_dash="dot", 
                      line_color="gray", opacity=0.3, row=1, col=1)
        fig.add_vline(x=df_last_hour.index[i], line_dash="dot", 
                      line_color="gray", opacity=0.3, row=2, col=1)
        fig.add_vline(x=df_last_hour.index[i], line_dash="dot", 
                      line_color="gray", opacity=0.3, row=3, col=1)
        fig.add_vline(x=df_last_hour.index[i], line_dash="dot", 
                      line_color="gray", opacity=0.3, row=4, col=1)
    
    # Layout ottimizzato
    fig.update_layout(
        height=900,
        showlegend=False,
        title=f"🎯 {pair} - ULTIMA ORA (1m) - SINCRONIZZATO",
        xaxis_rangeslider_visible=False,
        margin=dict(t=100, b=50)
    )
    
    st.plotly_chart(fig, use_container_width=True)
        
    # **CRONOLOGIA SEGNALI IN FONDO**
    st.markdown("---")
    st.subheader("📋 CRONOLOGIA SEGNALI (ultimi 20)")
    
    if 'signal_history' in st.session_state and st.session_state['signal_history']:
        signals_df = pd.DataFrame(st.session_state['signal_history'])
        st.dataframe(signals_df, use_container_width=True, height=300)
    else:
        st.info("⏳ Nessun segnale ancora generato")
