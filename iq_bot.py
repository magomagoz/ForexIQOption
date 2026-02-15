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

# **CONFIG TELEGRAM** 
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

def send_telegram_signal(signal_type, pair, price, rsi, macd):
    """Invia notifica Telegram completa"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    message = f"""
🚀 *SENTINEL AI - SEGNALE* 🚀

*{signal_type} - {pair.upper()}*
💰 *Prezzo Entrata:* `{price:.5f}`
📊 *RSI:* `{rsi:.1f}`
🔥 *MACD:* `{macd:.5f}`
⏰ *Ora:* {timestamp}
⚠️ *MANUALE - Entra Ora!*
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

# Logo
try:
    logo = Image.open("banner.png")
    st.image(logo, use_column_width=True, caption="IQ Signals PRO")
except:
    st.image("https://via.placeholder.com/800x100/0066cc/white?text=SENTINEL+AI", use_column_width=True)
    
# **SIDEBAR con tasto dinamico CONNETTI/ESCI**
with st.sidebar:
    st.header("⚙️ **TRADING IQ OPTION**")
    
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
                st.error(f"❌ Errore: {str(e)}")
   
    else:
        st.success(f"🟢 Connesso")
        
        st.header("📊 **ANALIZZA LA VALUTA**")
        st.session_state['pair'] = st.selectbox(
            "Coppia", 
            ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"], 
            index=0
        )

        if st.button("🔴 **DISCONNETTI**", type="secondary", use_container_width=True):
            try:
                st.session_state['iq'].close()
            except:
                pass
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("👋 Disconnesso!")
            st.rerun()
    
    # **SESSIONI MERCATO FOREX**
    if st.session_state.get('connected', False):
        st.markdown("---")
        st.header("🌍 **SESSIONI MERCATO**")
        
        now_cet = datetime.now()
        ora_cet = now_cet.time()
        
        sessioni = {
            "🇦🇺 SYDNEY": {"inizio": time(23,0), "fine": time(8,0)},
            "🇯🇵 TOKYO": {"inizio": time(1,0), "fine": time(10,0)}, 
            "🇬🇧 LONDRA": {"inizio": time(9,0), "fine": time(18,0)},
            "🇺🇸 NEW YORK": {"inizio": time(14,0), "fine": time(23,0)}
        }
        
        for nome, orari in sessioni.items():
            inizio, fine = orari["inizio"], orari["fine"]
            
            if inizio < fine:
                aperto = inizio <= ora_cet <= fine
            else:
                aperto = ora_cet >= inizio or ora_cet <= fine
            
            if aperto:
                colore = "🟢 APERTO"
                badge = "background: linear-gradient(45deg, #00ff88, #00cc66); color: black;"
            else:
                colore = "🔴 CHIUSO"
                badge = "background: #333; color: #aaa;"
            
            st.markdown(f"""
            <div style='padding: 12px; margin: 5px 0; border-radius: 12px; 
                        {badge} text-align: center; font-weight: bold; font-size: 16px;'>
                {nome} | {colore} | {ora_cet.strftime('%H:%M')}
            </div>
            """, unsafe_allow_html=True)
        
        # SOVRAPPOSIZIONI
        sovrapposizioni = []
        if time(9,0) <= ora_cet <= time(10,0): sovrapposizioni.append("🌍 Tokyo-Londra")
        if time(14,0) <= ora_cet <= time(18,0): sovrapposizioni.append("🚀 Londra-NY")
        
        if sovrapposizioni:
            st.markdown(f"""
            <div style='padding: 10px; margin: 10px 0; background: linear-gradient(45deg, #ffaa00, #ff8800); 
                        color: black; border-radius: 12px; text-align: center; font-weight: bold;'>
                ⚡ SOVRAPPOSIZIONE: {' + '.join(sovrapposizioni)} (MAX VOLUME!)
            </div>
            """, unsafe_allow_html=True)
       
        st.markdown("---")
        
        if st.button("🚀 **TEST SEGNALE TELEGRAM**", key="test_signal"):
            send_telegram_signal("BUY", "EURUSD", 1.08542, 28.4, 0.00015)
            st.session_state['scanner_alerts'] = [
                {'pair': 'EURUSD', 'type': '🟢 COMPRA', 'price': '1.08542', 'rsi': '28.4', 'macd': '0.00015'}
            ]
            st.success("✅ TEST TELEGRAM OK!")
            st.balloons()
            st.rerun()

        if st.button("🗑️ **RESET COMPLETO**", key="clear_all"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("✅ RESET COMPLETO!")
            st.rerun()

ALL_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"]

# INIZIALIZZAZIONE SESSION STATE
if st.session_state.get('connected', False):
    init_keys = [
        'scanner', 'scanner_data', 'scanner_last_update', 'scanner_alerts',
        'rsi_buy', 'rsi_sell', 'signal_history'
    ]
    
    for key in init_keys:
        if key not in st.session_state:
            if key == 'scanner': st.session_state[key] = False
            elif key == 'scanner_data': st.session_state[key] = {}
            elif key == 'scanner_last_update': st.session_state[key] = 0
            elif key == 'scanner_alerts': st.session_state[key] = []
            elif key == 'rsi_buy': st.session_state[key] = 35  # Ottimizzato per Forex
            elif key == 'rsi_sell': st.session_state[key] = 65
            elif key == 'signal_history': st.session_state[key] = []

    Iq = st.session_state['iq']

    # BALANCE LIVE (SOLO VISUALIZZAZIONE)
    try:
        Iq.change_balance("PRACTICE")
        balance = float(Iq.get_balance())
        col1, col2 = st.columns(2)
        col1.metric("💰 Balance Practice", f"€{balance:.2f}")
        col2.metric("👀 Modalità", "🚫 **SOLO SEGNALI**")
    except Exception as e:
        st.error(f"❌ Errore balance: {str(e)}")

    st.markdown("---")

    # CONTROLLI SCANNER (SOLO SEGNALI)
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.scanner = st.toggle("🔍 **Attiva Scanner Segnali**", value=st.session_state.scanner)
    with col2:
        st.info("🤖 **Trade Auto DISABILITATO** - Solo Segnali!")

    col1, col2, col3 = st.columns(3)
    with col1: 
        st.session_state.rsi_buy = st.number_input("🟢 RSI Buy", value=st.session_state.rsi_buy, min_value=20, max_value=45)
    with col2: 
        st.session_state.rsi_sell = st.number_input("🔴 RSI Sell", value=st.session_state.rsi_sell, min_value=55, max_value=80)
    with col3: 
        st.info("💵 **Importo manuale su IQ**")

    # ✅ SCANNER SEGNALI (NO TRADING AUTOMATICO)
    if st.session_state.scanner:
        last_scan = datetime.fromtimestamp(st.session_state.scanner_last_update).strftime("%H:%M:%S") if st.session_state.scanner_last_update else "Mai"
        st.markdown(f"🕐 **Ultimo scan**: {last_scan}")
        
        current_time = time_module.time()
        if current_time - st.session_state.scanner_last_update > 25:  # Scan ogni 25s
            placeholder = st.empty()
            with placeholder.container():
                st.spinner("🔍 Scanning 10 coppie Forex...")

            st.session_state.scanner_data = {}
            st.session_state.scanner_alerts = []
            signals_this_scan = 0
    
            for pair in ALL_PAIRS:
                try:
                    candles = Iq.get_candles(pair, 60, 50, time_module.time())
                    if not candles or len(candles) < 30:
                        raise ValueError("Dati insufficienti")
    
                    df = pd.DataFrame(candles)
                    df['from'] = pd.to_datetime(df['from'], unit='s')
                    df.set_index('from', inplace=True)
    
                    df['RSI'] = ta.rsi(df['close'], length=14)
                    macd = ta.macd(df['close'])
                    df['MACD'] = macd['MACD_12_26_9']
                    df['MACD_signal'] = macd['MACDs_12_26_9']
    
                    latest_rsi = float(df['RSI'].iloc[-1])
                    current_price = float(df['close'].iloc[-1])
                    
                    # 🎯 CONFERMA MACD CROSS (più affidabile)
                    macd_current = float(df['MACD'].iloc[-1])
                    macd_signal_current = float(df['MACD_signal'].iloc[-1])
                    macd_current_prev = float(df['MACD'].iloc[-2])
                    macd_signal_prev = float(df['MACD_signal'].iloc[-2])

                    macd_bullish_cross = (macd_current > macd_signal_current) and (macd_current_prev <= macd_signal_prev)
                    macd_bearish_cross = (macd_current < macd_signal_current) and (macd_current_prev >= macd_signal_prev)
                    
                    signal = "⚪ ATTESA"
                    
                    # ✅ SEGNALE BUY (SOLO NOTIFICA)
                    if latest_rsi < st.session_state.rsi_buy and macd_bullish_cross:
                        signal_info = {
                            'time': datetime.now().strftime("%H:%M:%S"),
                            'pair': pair,
                            'type': '🟢 COMPRA',
                            'price': f"{current_price:.5f}",
                            'rsi': f"{latest_rsi:.1f}",
                            'macd': f"{macd_current:.5f}"
                        }
                        st.session_state.scanner_alerts.append(signal_info)
                        st.session_state.signal_history.append(signal_info)
                        signals_this_scan += 1
                        signal = "🟢🚨 SEGNALE COMPRA"
                        # 📱 INVIA TELEGRAM
                        send_telegram_signal("BUY", pair, current_price, latest_rsi, macd_current)
                        
                    # ✅ SEGNALE SELL (SOLO NOTIFICA)
                    elif latest_rsi > st.session_state.rsi_sell and macd_bearish_cross:
                        signal_info = {
                            'time': datetime.now().strftime("%H:%M:%S"),
                            'pair': pair,
                            'type': '🔴 VENDI',
                            'price': f"{current_price:.5f}",
                            'rsi': f"{latest_rsi:.1f}",
                            'macd': f"{macd_current:.5f}"
                        }
                        st.session_state.scanner_alerts.append(signal_info)
                        st.session_state.signal_history.append(signal_info)
                        signals_this_scan += 1
                        signal = "🔴🚨 SEGNALE VENDI"
                        # 📱 INVIA TELEGRAM
                        send_telegram_signal("SELL", pair, current_price, latest_rsi, macd_current)
                    
                    st.session_state.scanner_data[pair] = {
                        'price': f"{current_price:.5f}",
                        'rsi': f"{latest_rsi:.1f}",
                        'signal': signal
                    }
    
                except Exception as e:
                    st.session_state.scanner_data[pair] = {
                        'price': '❌', 'rsi': '❌', 'signal': 'ERROR'
                    }
    
            st.session_state.scanner_last_update = current_time
            if signals_this_scan > 0:
                placeholder.success(f"✅ Scan completato! {signals_this_scan} SEGNALI TELEGRAM INVIATI!")
            else:
                placeholder.success("✅ Scan completato! Nessun segnale")
            st.rerun()
        else:
            next_scan = 25 - (current_time - st.session_state.scanner_last_update)
            st.info(f"⏳ Scanner attivo - prossimo scan tra {next_scan:.0f}s")
    
    st.markdown("---")
    
    # TABELLA SCANNER OTTIMIZZATA
    st.subheader("🔍 **SCANNER FOREX LIVE**")
    if st.session_state.scanner:
        scanner_df = pd.DataFrame(st.session_state.scanner_data).T
        scanner_df.reset_index(inplace=True)
        scanner_df.rename(columns={'index': 'PAIR'}, inplace=True)
        scanner_df = scanner_df[['PAIR', 'price', 'rsi', 'signal']]
        
        # 🎨 COLORI DINAMICI
        def color_signal(val):
            if '🟢🚨' in str(val): return 'background-color: #00ff88; color: black; font-weight: bold'
            elif '🔴🚨' in str(val): return 'background-color: #ff4444; color: white; font-weight: bold'
            elif '⚪' in str(val): return 'background-color: #f0f0f0'
            else: return ''
        
        scanner_df.rename(columns={
            'PAIR': '💱 COPPIA',
            'price': '💰 PREZZO', 
            'rsi': '📊 RSI',
            'signal': '🚦 SEGNALE'
        }, inplace=True)
        
        st.dataframe(scanner_df.style.applymap(color_signal, subset=['🚦 SEGNALE']), 
                    use_container_width=True, height=400, hide_index=True)
    
    # 🔥 ALERT POPUP PRIORITARI
    if st.session_state.get('scanner_alerts', []):
        st.markdown("---")
        st.subheader("🚨 **SEGNALI ATTIVI**")
        for alert in st.session_state.scanner_alerts[-3:]:  # Solo ultimi 3
            col1, col2 = st.columns([3,1])
            with col1:
                color = "#00ff88" if "COMPRA" in alert['type'] else "#ff4444"
                st.markdown(f"""
                <div style='background: linear-gradient(45deg, {color}, {color}); 
                padding: 25px; border-radius: 20px; border: 4px solid #ffffff; 
                text-align: center; font-size: 24px; font-weight: bold; color: black; box-shadow: 0 10px 30px rgba(0,0,0,0.3);'>
                    🚀 **{alert['type']} {alert['pair'].upper()}**
                    <div style='font-size: 28px; margin-top: 10px;'>
                        💰 {alert['price']} | 📊 RSI: {alert['rsi']}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                if st.button("👁️ VISTO", key=f"alert_{alert['pair']}_{int(time_module.time())}"):
                    st.session_state.scanner_alerts = [a for a in st.session_state.scanner_alerts if a['pair'] != alert['pair']]
                    st.rerun()

# GRAFICO CENTRALE REALTIME
if st.session_state.get('connected', False):
    Iq = st.session_state['iq']
    pair = st.session_state.get('pair', 'EURUSD')
    rsi_buy = st.session_state.get('rsi_buy', 35)
    rsi_sell = st.session_state.get('rsi_sell', 65)
    
    st.subheader(f"📊 GRAFICO REALTIME - {pair.upper()}")
    
    try:
        candles = Iq.get_candles(pair, 60, 150, time_module.time())
        df = pd.DataFrame(candles)
        df['from'] = pd.to_datetime(df['from'], unit='s')
        df.set_index('from', inplace=True)
        
        # INDICATORI TECNICI
        df['RSI'] = ta.rsi(df['close'], length=14)
        bbands = ta.bbands(df['close'], length=20, std=2.0)
        
        bb_cols = [col for col in bbands.columns if 'BB' in col]
        if len(bb_cols) >= 3:
            df['BBU'] = bbands[bb_cols[0]]
            df['BBM'] = bbands[bb_cols[1]] 
            df['BBL'] = bbands[bb_cols[2]]
        
        macd = ta.macd(df['close'])
        df['MACD'] = macd['MACD_12_26_9']
        df['MACD_signal'] = macd['MACDs_12_26_9']
        
        st.session_state['df'] = df
        
        # GRAFICO PROFESSIONALE
        df_last_hour = df.tail(60).copy()
        fig = make_subplots(
            rows=3, cols=1,
            subplot_titles=(f'💹 {pair.upper()} CON BOLLINGER', '📈 RSI (Livelli Segnali)', '📉 MACD CROSS'),
            row_heights=[0.5, 0.25, 0.25],
            vertical_spacing=0.05,
            shared_xaxes=True
        )
        
        # 🕯️ CANDELE
        fig.add_trace(go.Candlestick(
            x=df_last_hour.index, open=df_last_hour['open'], 
            high=df_last_hour['max'], low=df_last_hour['min'], 
            close=df_last_hour['close'], 
            increasing_line_color='#00ff88', decreasing_line_color='#ff4444'), 
            row=1, col=1)

        # 🎯 BOLLINGER BANDS
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['BBU'], 
                               line=dict(color='#00ccff', width=1.5), name='BBU', opacity=0.7), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['BBM'], 
                               line=dict(color='#ffaa00', width=2), name='BBM'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['BBL'], 
                               line=dict(color='#00ccff', width=1.5), fill='tonexty',
                               fillcolor='rgba(0, 204, 255, 0.15)', showlegend=False), row=1, col=1)
        
        # 📊 RSI CON LIVELLI SEGNALE
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['RSI'], 
                               line=dict(color='purple', width=2)), row=2, col=1)
        fig.add_hline(y=rsi_buy, line_dash="solid", line_color="#00ff00", line_width=3, 
                     annotation_text=f"BUY {rsi_buy}", row=2, col=1)
        fig.add_hline(y=rsi_sell, line_dash="solid", line_color="#ff0000", line_width=3, 
                     annotation_text=f"SELL {rsi_sell}", row=2, col=1)
        fig.add_hline(y=50, line_dash="dot", line_color="gray", row=2, col=1)
        
        # 🔥 MACD CON CROSS
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['MACD'], 
                               line=dict(color='orange', width=2.5), name='MACD'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['MACD_signal'], 
                               line=dict(color='red', width=2), name='Signal'), row=3, col=1)
        fig.add_hline(y=0, line_dash="solid", line_color="white", line_width=1, row=3, col=1)
        
        fig.update_layout(height=1000, showlegend=True, 
                         title=f"🎯 {pair.upper()} - SCANNER SEGNALI ATTIVO",
                         xaxis_rangeslider_visible=False, margin=dict(t=120))
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"❌ Grafico {pair}: {e}")

    # 📋 CRONOLOGIA SEGNALI (ULTIMI 50)
    st.markdown("---")
    st.subheader("📋 **STORICO SEGNALI** (Ultimi 50)")
    
    if st.session_state.get('signal_history', []):
        signals_df = pd.DataFrame(st.session_state['signal_history'][-50:])
        if not signals_df.empty:
            signals_df.columns = ['Ora', 'Valuta', 'Azione', 'Prezzo', 'RSI', 'MACD']
            st.dataframe(signals_df, use_container_width=True, height=400, hide_index=True)
    else:
        st.info("⏳ Attendi i primi segnali... Scanner attivo!")
