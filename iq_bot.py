import streamlit as st
import pandas as pd
import pandas_ta as ta
import time as time_module
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from iqoptionapi.stable_api import IQ_Option
from PIL import Image
import base64
import requests
from datetime import datetime, time

# **CONFIG TELEGRAM** (metti nella sidebar)
TELEGRAM_TOKEN = "8235666467:AAGCsvEhlrzl7bH537bJTjsSwQ3P3PMRW10"  # Il tuo token
TELEGRAM_CHAT_ID = "7191509088"         # Il tuo Chat ID

def send_telegram_signal(signal_type, pair, price, rsi, macd):
    """Invia notifica Telegram completa"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    message = f"""
🚀 *SENTINEL AI* 🚀

*{signal_type} - {pair.upper()}*
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
    
    # **SESSIONI MERCATO FOREX** (SENZA import nella sidebar)
    if st.session_state.get('connected', False):
        st.markdown("---")
        st.header("🌍 **SESSIONI MERCATO**")
        
        # Orari sessioni FOREX (CET = UTC+1)
        now_cet = datetime.now()
        ora_cet = now_cet.time()

        # **SCANNER e BARRA** (usa time_module)
        current_time = time_module.time()  # ✅ Invece di time.time()
        
        # Sessioni con orari CET (Italia)
        sessioni = {
            "🦘 SYDNEY": {"inizio": time(23,0), "fine": time(8,0)},
            "🇯🇵 TOKYO": {"inizio": time(1,0), "fine": time(10,0)}, 
            "🇬🇧 LONDRA": {"inizio": time(9,0), "fine": time(18,0)},
            "🇺🇸 NEW YORK": {"inizio": time(14,0), "fine": time(23,0)}
        }
        
        for nome, orari in sessioni.items():
            inizio, fine = orari["inizio"], orari["fine"]
            
            # Logica APERTO/CHIUSO (considera notti)
            if inizio < fine:
                aperto = inizio <= ora_cet <= fine
            else:  # Sessioni che attraversano mezzanotte
                aperto = ora_cet >= inizio or ora_cet <= fine
            
            # Colori e status
            if aperto:
                colore = "🟢 **APERTO**"
                badge = "background: linear-gradient(45deg, #00ff88, #00cc66); color: black;"
            else:
                colore = "🔴 **CHIUSO**"
                badge = "background: #333; color: #aaa;"
            
            st.markdown(f"""
            <div style='padding: 12px; margin: 5px 0; border-radius: 12px; 
                        {badge} text-align: center; font-weight: bold; font-size: 16px;'>
                {nome} | {colore} | {ora_cet.strftime('%H:%M')}
            </div>
            """, unsafe_allow_html=True)
        
        # **SOVRAPPOSIZIONI** (massimo volume)
        sovrapposizioni = []
        if time(9,0) <= ora_cet <= time(10,0): sovrapposizioni.append("🌍 Tokyo-Londra")
        if time(14,0) <= ora_cet <= time(18,0): sovrapposizioni.append("🚀 Londra-NY")
        
        if sovrapposizioni:
            st.markdown(f"""
            <div style='padding: 10px; margin: 10px 0; background: linear-gradient(45deg, #ffaa00, #ff8800); 
                        color: black; border-radius: 12px; text-align: center; font-weight: bold;'>
                ⚡ **SOVRAPPOSIZIONE: {' + '.join(sovrapposizioni)}** (MAX VOLUME!)
            </div>
            """, unsafe_allow_html=True)
       
        # **TEST COMPLETO (Popup + Telegram)** - FONDO sidebar
        with st.sidebar:
            st.markdown("---")
            #st.markdown("### 🧪 **TEST & DEBUG**")
            
            if st.button("🚀 **TEST COMPLETO**", 
                         key="test_full", help="Simula alert + Telegram"):
                
                # 1. SIMULA 2 ALERT POPUP
                test_alerts = [
                    {'pair': 'EURUSD', 'type': '🟢 BUY', 'price': '1.08542', 'rsi': '28.4'},
                    {'pair': 'GBPUSD', 'type': '🔴 SELL', 'price': '1.26580', 'rsi': '72.1'}
                ]
                st.session_state['scanner_alerts'] = test_alerts
                
                # 2. INVIA 2 MESSAGGI TELEGRAM
                send_telegram_signal("🟢 COMPRA", "EURUSD", 1.08542, 28.4, 0.00015)
                send_telegram_signal("🔴 VENDI", "GBPUSD", 1.26580, 72.1, -0.00023)
                
                st.success("✅ **TEST COMPLETO OK!**\n🔔 ALERT\n📱 MESSAGGIO TELEGRAM!")
                st.balloons()
                st.rerun()
            
            # Bonus: pulisci
            if st.button("🗑️ **PULISCI ALERT**", key="clear_all"):
                st.session_state['scanner_alerts'] = []
                st.success("✅ Tutto pulito!")
                st.rerun()

# **SCANNER MULTI-VALUTE ogni 60s + GRAFICO SINGOLO separato**
ALL_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"]

# **SCANNER BACKGROUND CON POPUP ALERT**
if st.session_state.get('connected', False):
    if 'scanner_data' not in st.session_state:
        st.session_state['scanner_data'] = {}
        st.session_state['scanner_last_update'] = 0
        st.session_state['scanner_alerts'] = []  # ✅ Nuovi alert scanner
    
    current_time = time_module.time()
    if current_time - st.session_state['scanner_last_update'] > 60:
        spinner_placeholder = st.empty()
        with spinner_placeholder.container():
            st.spinner("🔍 Scanning globale...")
        
        Iq = st.session_state['iq']
        st.session_state['scanner_data'] = {}
        st.session_state['scanner_alerts'] = []  # ✅ Reset alert
        
        for pair in ALL_PAIRS:
            try:
                candles = Iq.get_candles(pair, 60, 50, time_module.time())
                df = pd.DataFrame(candles)
                df['from'] = pd.to_datetime(df['from'], unit='s')
                df.set_index('from', inplace=True)
                
                df['RSI'] = ta.rsi(df['close'], length=14)
                macd = ta.macd(df['close'])
                df['MACD'] = macd['MACD_12_26_9']
                df['MACD_signal'] = macd['MACDs_12_26_9']
                
                latest_rsi = df['RSI'].iloc[-1]
                macd_bullish = df['MACD'].iloc[-1] > df['MACD_signal'].iloc[-1]
                
                signal = "⚪ ATTESA"
                if latest_rsi < 30 and macd_bullish:
                    signal = "🟢 COMPRA"
                    st.session_state['scanner_alerts'].append({
                        'pair': pair, 'type': '🟢 COMPRA', 'price': f"{df['close'].iloc[-1]:.5f}",
                        'rsi': f"{latest_rsi:.1f}"
                    })
                elif latest_rsi > 70 and not macd_bullish:
                    signal = "🔴 VENDI"
                    st.session_state['scanner_alerts'].append({
                        'pair': pair, 'type': '🔴 VENDI', 'price': f"{df['close'].iloc[-1]:.5f}",
                        'rsi': f"{latest_rsi:.1f}"
                    })
                
                st.session_state['scanner_data'][pair] = {
                    'price': f"{df['close'].iloc[-1]:.5f}",
                    'rsi': f"{latest_rsi:.1f}",
                    'signal': signal
                }
                
            except:
                st.session_state['scanner_data'][pair] = {'price': '❌', 'rsi': '❌', 'signal': 'ERROR'}
        
        st.session_state['scanner_last_update'] = current_time
        spinner_placeholder.success("✅ Scanner aggiornato!")

    # **MOSTRA TABELLA SCANNER SENZA INDICE NUMERICO**
    st.subheader("🔍 **SCANNER 10 VALUTE**")
    if st.session_state.get('scanner_data'):
        scanner_df = pd.DataFrame(st.session_state['scanner_data']).T
        scanner_df.reset_index(inplace=True)
        scanner_df.rename(columns={'index': 'PAIR'}, inplace=True)
        scanner_df = scanner_df[['PAIR', 'price', 'rsi', 'signal']]
        st.dataframe(scanner_df, use_container_width=True, height=400, hide_index=True)  # ✅ hide_index=True
        
    Iq = st.session_state['iq']

 # **POPUP ALERT SCANNER** (dopo st.dataframe(scanner_df))
if st.session_state.get('scanner_alerts'):
    for alert in st.session_state['scanner_alerts']:
        col1, col2 = st.columns([3,1])
        with col1:
            if alert['type'] == '🟢 COMPRA':
                st.markdown(f"""
                <div style='background: linear-gradient(45deg, #00ff88, #00cc66); 
                padding: 25px; border-radius: 20px; border: 4px solid #00ff00; 
                text-align: center; font-size: 24px; font-weight: bold; color: black;'>
                    🚀 **{alert['type']} {alert['pair'].upper()}**
                    <div style='font-size: 28px; margin-top: 10px;'>
                        💰 {alert['price']} | 📊 RSI: {alert['rsi']}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:  # SELL
                if alert['type'] == '🔴 VENDI':
                    st.markdown(f"""
                    <div style='background: linear-gradient(45deg, #ff4444, #cc0000); 
                    padding: 25px; border-radius: 20px; border: 4px solid #ff0000; 
                    text-align: center; font-size: 24px; font-weight: bold; color: white;'>
                        🔻 **{alert['type']} {alert['pair'].upper()}**
                        <div style='font-size: 28px; margin-top: 10px;'>
                            💰 {alert['price']} | 📊 RSI: {alert['rsi']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        
        with col2:
            if st.button("✅ OK", key=f"alert_{alert['pair']}_{len(st.session_state.get('scanner_alerts',[]))}"):  # ✅ AGGIUNGI :
                # Rimuovi alert specifico
                st.session_state['scanner_alerts'] = [a for a in st.session_state['scanner_alerts'] 
                                                   if a['pair'] != alert['pair']]
                st.rerun()
                
    st.markdown("---")
    st.subheader("📈 LIVE STATUS")
    if st.session_state.get('connected', False) and 'df' in st.session_state:
        df = st.session_state['df'].iloc[-1] if len(st.session_state['df']) > 0 else None
        
    if df is not None:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("💰 PREZZO", f"{df['close']:.5f}", delta=None)
        with col2:
            st.metric("📊 RSI", f"{df['RSI']:.1f}", delta=None)
        with col3:
            st.metric("🔥 MACD", f"{df['MACD']:.5f}", delta=None)
        with col4:
            trend = "🟢 CRESCITA" if df['MACD'] > df['MACD_signal'] else "🔴 CALO"
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
        candles = Iq.get_candles(pair, 60, 150, time_module.time())
        df = pd.DataFrame(candles)
        df['from'] = pd.to_datetime(df['from'], unit='s')
        df.set_index('from', inplace=True)
        
        # INDICATORI + BOLLINGER
        df['RSI'] = ta.rsi(df['close'], length=14)
        
        # ✅ BANDE BOLLINGER - NOMI FLESSIBILI (NO ERRORE)
        bbands = ta.bbands(df['close'], length=20, std=2.0)
        
        # Trova colonne Bollinger automaticamente
        bb_cols = [col for col in bbands.columns if 'BB' in col]
        if len(bb_cols) >= 3:
            df['BBU'] = bbands[bb_cols[0]]  # Prima colonna BB = Upper
            df['BBM'] = bbands[bb_cols[1]]  # Seconda = Middle  
            df['BBL'] = bbands[bb_cols[2]]  # Terza = Lower
        else:
            # Fallback manuale
            df['BBU'] = df['close'].rolling(20).mean() + (df['close'].rolling(20).std() * 2)
            df['BBM'] = df['close'].rolling(20).mean()
            df['BBL'] = df['close'].rolling(20).mean() - (df['close'].rolling(20).std() * 2)
        
        macd = ta.macd(df['close'])
        df['MACD'] = macd['MACD_12_26_9']
        df['MACD_signal'] = macd['MACDs_12_26_9']
        
        # SEGNALI (invariati)
        df['prev_MACD'] = df['MACD'].shift(1)
        df['prev_signal'] = df['MACD_signal'].shift(1)
        
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
            subplot_titles=(f'💹 TREND PREZZO CON BB', 'INDICATORE RSI', 'INDICATORE MACD'),
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

        # ✅ BANDE BOLLINGER CORRETTE
        fig.add_trace(go.Scatter(
            x=df_last_hour.index, y=df_last_hour['BBU'], 
            line=dict(color='#00ccff', width=1.5), name='BBU', opacity=0.7), row=1, col=1
        )
        fig.add_trace(go.Scatter(
            x=df_last_hour.index, y=df_last_hour['BBM'], 
            line=dict(color='#ffaa00', width=2), name='BBM'), row=1, col=1
        )
        fig.add_trace(go.Scatter(
            x=df_last_hour.index, y=df_last_hour['BBL'], 
            line=dict(color='#00ccff', width=1.5), fill='tonexty',
            fillcolor='rgba(0, 204, 255, 0.15)',  # ✅ Celestino tra BBL-BBM
            showlegend=False), row=1, col=1
        )
            
        # Legenda Bollinger
        #fig.add_annotation(x=0.02, y=0.98, xref="paper", yref="paper", showarrow=False, font=dict(size=12), bgcolor="rgba(0,204,255,0.2)", bordercolor="#00ccff")
        
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
        
        fig.update_layout(height=900, showlegend=False, title=f"🎯 {pair.upper()} - ULTIMA ORA", 
                         xaxis_rangeslider_visible=False, margin=dict(t=100))
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"❌ Dati {pair}: {e}")

    # **CHECK ESITI dopo 1 minuto - CORRETTO**
    if 'signal_history' in st.session_state:
        current_time = time_module.time()
        for i, signal in enumerate(st.session_state['signal_history']):
            if signal['outcome'] == '⏳ ATTESA ESITO':
                # ✅ USA time_module.time() invece di datetime
                signal_timestamp = datetime.strptime(signal['time'], '%H:%M:%S').timestamp()
                time_diff = current_time - signal_timestamp
                
                if time_diff >= 60:  # 1 minuto passato
                    try:
                        Iq = st.session_state['iq']
                        candles = Iq.get_candles(signal['pair'], 60, 2, time_module.time())
                        latest_price = pd.DataFrame(candles)['close'].iloc[-1]
                        entry_price = float(signal['price_entry'])
                        
                        # CALCOLA ESITO
                        if signal['type'] == '🟢 BUY':
                            outcome = "✅ VINTO" if latest_price > entry_price else "❌ PERSO"
                        else:  # SELL
                            outcome = "✅ VINTO" if latest_price < entry_price else "❌ PERSO"
                        
                        st.session_state['signal_history'][i]['outcome'] = outcome
                        st.session_state['signal_history'][i]['price_exit'] = f"{latest_price:.5f}"
                        
                    except:
                        st.session_state['signal_history'][i]['outcome'] = '❓ ERRORE'
 
    # **CRONOLOGIA SEGNALI IN FONDO - NUMERAZIONE DA 1**
    st.markdown("---")
    st.subheader("📋 CRONOLOGIA SEGNALI")
    
    if 'signal_history' in st.session_state and st.session_state['signal_history']:
        signals_df = pd.DataFrame(st.session_state['signal_history'])
        # ORDINA colonne
        cols = ['Ora', 'Valuta', 'Azione', 'Prezzo di entrata', 'RSI', 'MACD', 'Esito']
        signals_df = signals_df[cols]
        
        # ✅ RESET INDEX DA 1 (non da 0)
        signals_df.reset_index(drop=True, inplace=True)
        signals_df.index += 1  # Inizia da 1 invece di 0
        
        st.dataframe(signals_df, use_container_width=True, height=350, hide_index=False)
    else:
        st.info("⏳ Nessun segnale generato")
