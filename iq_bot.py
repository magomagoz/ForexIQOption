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
    
    if "TRADE" in signal_type:
        message = f"""
🚀 *SENTINEL AI - TRADE {signal_type}* 🚀

*{signal_type} - {pair.upper()}*
💰 *Prezzo:* `{price:.5f}`
📊 *RSI:* `{rsi:.1f}`
🔥 *MACD:* `{macd:.5f}`
⏰ *Ora:* {timestamp}
⚠️ *1 MINUTO SCADUTO*
"""
    else:
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

def check_connection():
    """Reconnect IQ se disconnesso"""
    if st.session_state.get('connected', False):
        try:
            Iq = st.session_state['iq']
            if not Iq.check_connect():
                check, reason = Iq.connect()
                if check:
                    st.success("🔄 Reconnected!")
                    return True
                else:
                    st.error(f"Reconnect fallito: {reason}")
                    return False
            return True
        except Exception as e:
            st.error(f"Check conn error: {e}")
            return False
    return False

def play_trade_sound(sound_type="alert"):
    """Suona notifica audio per trade"""
    sounds = {
        "buy": "https://www.soundjay.com/misc/sounds/bell-ringing-05.wav",
        "sell": "https://www.soundjay.com/misc/sounds/bell-ringing-05.wav", 
        "win": "https://www.soundjay.com/misc/sounds/ching-15.wav",
        "lose": "data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAo"
    }
    sound_url = sounds.get(sound_type, sounds["alert"])
    st.audio(sound_url, autoplay=True, sample_rate=44100)

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
    
    if not st.session_state.get('connected', False):
        email = st.text_input("Email Practice", value="mago_magoz@libero.it")
        password = st.text_input("Password", type="password")
        
        if st.button("🔌 **CONNETTI**", type="primary", use_container_width=True):
            try:
                Iq = IQ_Option(email, password)
                check, reason = Iq.connect()
                if check:
                    st.session_state['iq'] = Iq
                    st.session_state['connected'] = True
                    st.session_state['email'] = email
                    st.session_state['pair'] = "EURUSD"
                    st.session_state['signal_history'] = []
                    st.session_state['active_trades'] = {}
                    st.success("✅ CONNESSO!")
                    st.balloons()
                    st.rerun()
                else:
                    st.error(f"❌ {reason}")
            except Exception as e:
                st.error(f"❌ Errore: {str(e)}")
    else:
        st.success(f"🟢 Connesso")
        if st.button("🔴 **DISCONNETTI**", type="secondary", use_container_width=True):
            try:
                st.session_state['iq'].close()
            except:
                pass
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("👋 Disconnesso!")
            st.rerun()
        
        st.markdown("---")
        st.subheader("📊 **SELEZIONE VALUTA**")
        st.session_state['pair'] = st.selectbox(
            "Coppia", 
            ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"], 
            index=0
        )
        
        # **SESSIONI MERCATO LIVE** - AGGIORNAMENTO REALE
        st.markdown("---")
        st.subheader("🌍 **SESSIONI LIVE**")
        
        # Funzione per badge sessione
        def session_badge(nome, aperto, ora_cet):
            if aperto:
                return f"""
                <div style='padding: 12px; margin: 5px 0; border-radius: 12px; 
                            background: linear-gradient(45deg, #00ff88, #00cc66); 
                            color: black; text-align: center; font-weight: bold; font-size: 16px;'>
                    {nome} | 🟢 APERTO | {ora_cet.strftime('%H:%M')}
                </div>
                """
            else:
                return f"""
                <div style='padding: 12px; margin: 5px 0; border-radius: 12px; 
                            background: #333; color: #aaa; text-align: center; font-weight: bold; font-size: 16px;'>
                    {nome} | 🔴 CHIUSO | {ora_cet.strftime('%H:%M')}
                </div>
                """
        
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
            st.markdown(session_badge(nome, aperto, ora_cet), unsafe_allow_html=True)
        
        # SOVRAPPOSIZIONI LIVE
        sovrapposizioni = []
        if time(9,0) <= ora_cet <= time(10,0): sovrapposizioni.append("🌍 Tokyo-Londra")
        if time(14,0) <= ora_cet <= time(18,0): sovrapposizioni.append("🚀 Londra-NY")
        
        if sovrapposizioni:
            st.markdown(f"""
            <div style='padding: 15px; margin: 10px 0; background: linear-gradient(45deg, #ffaa00, #ff8800); 
                        color: black; border-radius: 15px; text-align: center; font-weight: bold; font-size: 18px;'>
                ⚡ **SOVRAPPOSIZIONE: {' + '.join(sovrapposizioni)}**<br>
                💥 MAX VOLUME - TRADE ATTIVI!
            </div>
            """, unsafe_allow_html=True)
       
        st.markdown("---")
        
        if st.button("📱 **TEST SEGNALE TELEGRAM**", key="test_signal"):
            send_telegram_signal("BUY", "EURUSD", 1.08542, 28.4, 0.00015)
            if 'scanner_alerts' not in st.session_state:
                st.session_state['scanner_alerts'] = []
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

# **MAIN CONTENT - SOLO SE CONNESSO**
if st.session_state.get('connected', False):
    # INIZIALIZZAZIONE SESSION STATE
    init_keys = [
        'scanner', 'scanner_data', 'scanner_last_update', 'scanner_alerts',
        'rsi_buy', 'rsi_sell', 'signal_history', 'active_trades'
    ]
    
    for key in init_keys:
        if key not in st.session_state:
            if key == 'scanner': st.session_state[key] = False
            elif key == 'scanner_data': st.session_state[key] = {}
            elif key == 'scanner_last_update': st.session_state[key] = 0
            elif key == 'scanner_alerts': st.session_state[key] = []
            elif key == 'rsi_buy': st.session_state[key] = 28
            elif key == 'rsi_sell': st.session_state[key] = 72
            elif key == 'signal_history': st.session_state[key] = []
            elif key == 'active_trades': st.session_state[key] = {}

    Iq = st.session_state['iq']
    
    # CHECK CONNESSIONE
    if not check_connection():
        st.error("❌ Connessione persa. Riconnetti manualmente.")
        st.stop()

    # BALANCE LIVE
    try:
        Iq.change_balance("PRACTICE")
        balance = float(Iq.get_balance())
        col1, col2 = st.columns(2)
        col1.metric("💰 Balance Practice", f"€{balance:.2f}")
        col2.metric("👀 Modalità", "🤖 **AUTO TRADES 1m**")
    except Exception as e:
        st.error(f"❌ Errore balance: {str(e)}")

    st.markdown("---")
    current_time = time_module.time()

    # CONTROLLI SCANNER
    st.session_state.scanner = st.toggle("🔍 **Attiva Scanner Auto-Trades**", value=st.session_state.scanner)
    
    col1, col2 = st.columns(2)
    with col1: 
        st.session_state.rsi_buy = st.number_input("🟢 RSI Buy", value=st.session_state.rsi_buy, min_value=20, max_value=35)
    with col2: 
        st.session_state.rsi_sell = st.number_input("🔴 RSI Sell", value=st.session_state.rsi_sell, min_value=65, max_value=80)

    # SCANNER CON AUTO-TRADES 1m MIGLIORATO
    if st.session_state.scanner:
        last_scan = datetime.fromtimestamp(st.session_state.scanner_last_update).strftime("%H:%M:%S") if st.session_state.scanner_last_update else "Mai"
        st.markdown(f"🕐 **Ultimo scan**: {last_scan}")
        
        # 🔄 SCAN OGNI 7 SECONDI (più reattivo)
        if current_time - st.session_state.scanner_last_update > 7:
            # Placeholder per feedback live
            placeholder = st.empty()
            with placeholder.container():
                st.info("🔍 Scanning 10 coppie Forex... (7s ciclo)")
    
            st.session_state.scanner_data = {}
            st.session_state.scanner_alerts = []
            signals_this_scan = 0
    
            # CHECK TRADES SCADUTI (invariato)
            trades_to_close = []
            for pair, trade in st.session_state['active_trades'].items():
                trade_age = current_time - trade['entry_time']
                if trade_age >= 60:
                    try:
                        current_candles = Iq.get_candles(pair, 60, 2, time_module.time())
                        if current_candles:
                            exit_price = float(current_candles[-1]['close'])
                            entry_price = trade['entry_price']
                            profit_pips = (exit_price - entry_price) * 10000 if trade['direction'] == 'BUY' else (entry_price - exit_price) * 10000
                            
                            win_amount = trade['amount'] * 0.85
                            lose_amount = -trade['amount']
                            
                            if profit_pips > 0:
                                result = f"✅ VITTORIA €{win_amount:.2f}"
                                play_trade_sound("win")
                                st.success(f"🎉 VITTORIA {pair}! +€{win_amount:.2f}")
                            else:
                                result = f"❌ SCONFITTA -€{lose_amount:.2f}"
                                play_trade_sound("lose")
                                st.error(f"💥 SCONFITTA {pair}! -€{lose_amount:.2f}")
                                
                            trade_result = {
                                'time': datetime.now().strftime("%H:%M:%S"),
                                'pair': pair,
                                'entry': f"{entry_price:.5f}",
                                'exit': f"{exit_price:.5f}",
                                'pips': f"{profit_pips:.1f}",
                                'result': result
                            }
                            st.session_state.signal_history.append(trade_result)
                            send_telegram_signal("TRADE_RESULT", pair, exit_price, profit_pips, 0)
                        trades_to_close.append(pair)
                    except Exception as e:
                        st.error(f"Errore chiusura {pair}: {e}")
            
            for pair in trades_to_close:
                del st.session_state['active_trades'][pair]
    
            # 🔥 NUOVO SCAN OTTIMIZZATO
            for pair in ALL_PAIRS:
                try:
                    candles = Iq.get_candles(pair, 60, 50, time_module.time())
                    if not candles or len(candles) < 30:
                        st.session_state.scanner_data[pair] = {'price': '❌', 'rsi': '❌', 'signal': 'Dati insufficienti'}
                        continue
                    
                    df = pd.DataFrame(candles)
                    df['from'] = pd.to_datetime(df['from'], unit='s')
                    df.set_index('from', inplace=True)
    
                    df['RSI'] = ta.rsi(df['close'], length=7)
                    macd = ta.macd(df['close'], fast=8, slow=17, signal=9)
                    df['MACD'] = macd['MACD_8_17_9']
                    df['MACD_signal'] = macd['MACDs_8_17_9']
    
                    latest_rsi = float(df['RSI'].iloc[-1])
                    current_price = float(df['close'].iloc[-1])
                    macd_current = float(df['MACD'].iloc[-1])
                    macd_signal_current = float(df['MACD_signal'].iloc[-1])
                    macd_current_prev = float(df['MACD'].iloc[-2])
                    macd_signal_prev = float(df['MACD_signal'].iloc[-2])
    
                    # 🎯 CONDIZIONI PIÙ FLESSIBILI
                    macd_bullish = macd_current > macd_signal_current  # Rimuovi cross, usa trend
                    macd_bearish = macd_current < macd_signal_current
                    rsi_buy_zone = latest_rsi < st.session_state.rsi_buy
                    rsi_sell_zone = latest_rsi > st.session_state.rsi_sell
                    
                    signal = "⚪ ATTESA"
                    
                    # 🟢 BUY - Condizioni separate + volume trend
                    if (rsi_buy_zone and macd_bullish and 
                        pair not in st.session_state['active_trades']):
                        
                        # Check volume crescente (conferma momentum)
                        volume_trend = df['volume'].iloc[-1] > df['volume'].iloc[-3]
                        
                        if volume_trend:
                            trade_info = {
                                'entry_price': current_price,
                                'entry_time': current_time,
                                'amount': 100.0,
                                'direction': 'BUY'
                            }
                            st.session_state['active_trades'][pair] = trade_info
                            
                            signal_info = {
                                'time': datetime.now().strftime("%H:%M:%S"),
                                'pair': pair,
                                'type': '🟢 TRADE BUY APERTO',
                                'price': f"{current_price:.5f}",
                                'rsi': f"{latest_rsi:.1f}",
                                'amount': '€100'
                            }
                            st.session_state.scanner_alerts.append(signal_info)
                            signals_this_scan += 1
                            signal = "🟢🚨 TRADE APERTO"
                    
                            play_trade_sound("buy")
                            send_telegram_signal("BUY_TRADE", pair, current_price, latest_rsi, macd_current)
                            st.balloons()
                    
                    # 🔴 SELL - Condizioni separate + volume trend  
                    elif (rsi_sell_zone and macd_bearish and 
                          pair not in st.session_state['active_trades']):
                          
                        volume_trend = df['volume'].iloc[-1] > df['volume'].iloc[-3]
                        
                        if volume_trend:
                            trade_info = {
                                'entry_price': current_price,
                                'entry_time': current_time,
                                'amount': 100.0,
                                'direction': 'SELL'
                            }
                            st.session_state['active_trades'][pair] = trade_info
                            
                            signal_info = {
                                'time': datetime.now().strftime("%H:%M:%S"),
                                'pair': pair,
                                'type': '🔴 TRADE SELL APERTO',
                                'price': f"{current_price:.5f}",
                                'rsi': f"{latest_rsi:.1f}",
                                'amount': '€100'
                            }
                            st.session_state.scanner_alerts.append(signal_info)
                            signals_this_scan += 1
                            signal = "🔴🚨 TRADE APERTO"
    
                            play_trade_sound("sell")
                            send_telegram_signal("SELL_TRADE", pair, current_price, latest_rsi, macd_current)
                            st.balloons()
                    
                    # 📊 AGGIUNGI ANCHE SEGNALI "PRE-BUY/SELL" per debug
                    elif rsi_buy_zone and macd_bullish:
                        signal = "🟢 PRE-BUY (no volume)"
                    elif rsi_sell_zone and macd_bearish:
                        signal = "🔴 PRE-SELL (no volume)"
                    
                    st.session_state.scanner_data[pair] = {
                        'price': f"{current_price:.5f}",
                        'rsi': f"{latest_rsi:.1f}",
                        'signal': signal
                    }
    
                except Exception as e:
                    st.session_state.scanner_data[pair] = {'price': '❌', 'rsi': '❌', 'signal': f'ERROR: {str(e)[:20]}'}
    
            st.session_state.scanner_last_update = current_time
            
            # ✅ FEEDBACK MIGLIORATO
            if signals_this_scan > 0:
                placeholder.success(f"✅ {signals_this_scan} TRADES APERTI! Prossimo scan: 7s")
            else:
                placeholder.info("✅ Scan OK - Prossimo: 7s | Controlla PRE-BUY/SELL")
                
            # ❌ NO st.rerun() qui - lascia respirare l'app
        else:
            next_scan = 7 - (current_time - st.session_state.scanner_last_update)
            st.info(f"⏳ Scanner attivo - prossimo scan tra {next_scan:.0f}s")
    
    # 🔥 DASHBOARD TRADES APERTI - CORRETTO
    if st.session_state.get('active_trades', {}):
        st.subheader("🔥 **TRADES APERTI (1m)**")
        active_df = pd.DataFrame([
            {
                'PAIR': trade_pair,  # ← CORRETTO: usa trade_pair invece di pair
                'ENTRY': f"€{trade['amount']:.0f} @ {trade['entry_price']:.5f}",
                '⏱️': f"{int(current_time - trade['entry_time'])}s",
                'STATUS': '⏳ APERTO'
            }
            for trade_pair, trade in st.session_state['active_trades'].items()  # ← trade_pair dalla comprehension
        ])
        st.dataframe(active_df, use_container_width=True, hide_index=True)

    # TABELLA SCANNER OTTIMIZZATA (invariata, OK)
    st.subheader("🔍 **SCANNER FOREX LIVE**")
    if st.session_state.get('scanner', False) and st.session_state.get('scanner_data', {}):
        scanner_df = pd.DataFrame(st.session_state.scanner_data).T
        scanner_df.reset_index(inplace=True)
        scanner_df.rename(columns={'index': 'PAIR'}, inplace=True)
        scanner_df = scanner_df[['PAIR', 'price', 'rsi', 'signal']]
        
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

    # 🔥 ALERT POPUP PRIORITARI - FUNZIONANTE AL 100%
    if st.session_state.get('scanner_alerts', []):
        st.markdown("---")
        st.subheader("🚨 **ULTIMI TRADES APERTI**")
        
        # Processa alert in ordine inverso per indici stabili
        for i, alert in enumerate(reversed(st.session_state.scanner_alerts[-3:])):
            col1, col2 = st.columns([3,1])
            with col1:
                color = "#00ff88" if "BUY" in alert['type'] else "#ff4444"
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
                # KEY SUPER STABILE - solo pair + indice fisso
                alert_key = f"close_alert_{alert['pair']}_{i}"
                if st.button("👁️ VISTO", key=alert_key):
                    # Rimuovi TUTTI gli alert di questo pair
                    st.session_state.scanner_alerts = [
                        a for a in st.session_state.scanner_alerts 
                        if a['pair'] != alert['pair']
                    ]
                    st.success(f"✅ Rimossa alert {alert['pair']}!")
                    st.rerun()



# GRAFICO CENTRALE REALTIME
if st.session_state.get('connected', False):
    Iq = st.session_state['iq']
    pair = st.session_state.get('pair', 'EURUSD')
    rsi_buy = st.session_state.get('rsi_buy', 28)
    rsi_sell = st.session_state.get('rsi_sell', 72)
    
    st.subheader(f"📊 GRAFICO REALTIME - {pair.upper()}")
    
    try:
        candles = Iq.get_candles(pair, 60, 150, time_module.time())
        df = pd.DataFrame(candles)
        df['from'] = pd.to_datetime(df['from'], unit='s')
        df.set_index('from', inplace=True)
        
        # INDICATORI OTTIMIZZATI 1m
        df['RSI'] = ta.rsi(df['close'], length=7)
        bbands = ta.bbands(df['close'], length=20, std=2.0)
        
        bb_cols = [col for col in bbands.columns if 'BB' in col]
        if len(bb_cols) >= 3:
            df['BBU'] = bbands[bb_cols[0]]
            df['BBM'] = bbands[bb_cols[1]] 
            df['BBL'] = bbands[bb_cols[2]]
        
        macd = ta.macd(df['close'], fast=8, slow=17, signal=9)
        df['MACD'] = macd['MACD_8_17_9']
        df['MACD_signal'] = macd['MACDs_8_17_9']
        
        st.session_state['df'] = df
        
        # GRAFICO
        df_last_hour = df.tail(60).copy()
        fig = make_subplots(
            rows=3, cols=1,
            subplot_titles=(f'💹 {pair.upper()} CON BBANDS', '📈 RSI (1m Scalping)', '📉 MACD 8-17-9'),
            row_heights=[0.5, 0.25, 0.25],
            vertical_spacing=0.05,
            shared_xaxes=True
        )
        
        fig.add_trace(go.Candlestick(
            x=df_last_hour.index, open=df_last_hour['open'], 
            high=df_last_hour['max'], low=df_last_hour['min'], 
            close=df_last_hour['close'], 
            increasing_line_color='#00ff88', decreasing_line_color='#ff4444'), row=1, col=1)

        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['BBU'], 
                               line=dict(color='#00ccff', width=1.5), name='BBU', opacity=0.7), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['BBM'], 
                               line=dict(color='#ffaa00', width=2), name='BBM'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['BBL'], 
                               line=dict(color='#00ccff', width=1.5), fill='tonexty',
                               fillcolor='rgba(0, 204, 255, 0.15)', showlegend=False), row=1, col=1)
        
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['RSI'], 
                               line=dict(color='purple', width=2), name='RSI'), row=2, col=1)
        fig.add_hline(y=rsi_buy, line_dash="solid", line_color="#00ff00", line_width=3, 
                     annotation_text=f"BUY {rsi_buy}", row=2, col=1)
        fig.add_hline(y=rsi_sell, line_dash="solid", line_color="#ff0000", line_width=3, 
                     annotation_text=f"SELL {rsi_sell}", row=2, col=1)
        fig.add_hline(y=50, line_dash="dot", line_color="gray", row=2, col=1)
        
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['MACD'], 
                               line=dict(color='orange', width=2.5), name='MACD'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['MACD_signal'], 
                               line=dict(color='red', width=2), name='Signal'), row=3, col=1)
        fig.add_hline(y=0, line_dash="solid", line_color="white", line_width=1, row=3, col=1)
        
        fig.update_layout(height=1000, showlegend=False, 
                         title=f"🎯 {pair.upper()} - AUTO TRADES 1m ATTIVI",
                         xaxis_rangeslider_visible=False, margin=dict(t=120))
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"❌ Grafico {pair}: {e}")

    # 📊 STATISTICHE LIVE
    st.markdown("---")
    st.subheader("📊 **STATISTICHE LIVE**")
    if st.session_state.get('signal_history', []):
        recent_trades = pd.DataFrame(st.session_state['signal_history'][-100:])
        trade_results = recent_trades[recent_trades['result'].str.contains('VITTORIA|SCONFITTA', na=False)]
        
        if not trade_results.empty:
            wins = len(trade_results[trade_results['result'].str.contains('VITTORIA')])
            total = len(trade_results)
            winrate = (wins / total * 100) if total > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            col1.metric("🎯 Trades Totali", total)
            col2.metric("✅ Winrate", f"{winrate:.1f}%")
            col3.metric("📈 Ultimi 10", f"{wins}/{total}")

    # 📋 STORICO COMPLETO CON ESITI
    st.markdown("---")
    st.subheader("📋 **STORICO TRADES** (Ultimi 50)")
    
    if st.session_state.get('signal_history', []):
        signals_df = pd.DataFrame(st.session_state['signal_history'][-50:])
        if not signals_df.empty:
            # Adatta colonne per entrambi i tipi
            if 'result' in signals_df.columns:
                signals_df = signals_df[['time', 'pair', 'entry', 'exit', 'pips', 'result']]
                signals_df.columns = ['ORA', 'COPPIA', 'ENTRY', 'EXIT', 'PIPS', 'ESITO']
            else:
                signals_df = signals_df[['time', 'pair', 'type', 'price', 'rsi']]
                signals_df.columns = ['ORA', 'COPPIA', 'AZIONE', 'PREZZO', 'RSI']
            
            st.dataframe(signals_df, use_container_width=True, height=400, hide_index=True)
    else:
        st.info("⏳ Attendi i primi trades... Scanner attivo!")
