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
    if not TELEGRAM_TOKEN: return
    timestamp = datetime.now().strftime("%H:%M:%S")
    message = f"🚀 *SENTINEL AI*\n*{signal_type} - {pair}*\n💰 *Prezzo:* `{price}`\n📊 *RSI:* `{rsi}`\n🔥 *MACD:* `{macd:.5f}`\n⏰ Ora: {timestamp}\n⚠️ *Entra Ora!*"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=5)
    except: pass

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
        "lose": "https://www.soundjay.com/misc/sounds/ching-15.wav"
    }
    sound_url = sounds.get(sound_type, sounds["alert"])
    st.audio(sound_url, autoplay=True, sample_rate=44100)
    #st.audio(sounds.get(sound_type, sounds["buy"]), autoplay=True)

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
        
        if st.button("🔌 **CONNETTI**", use_container_width=True):
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
        if st.button("🔴 **DISCONNETTI**", type="primary", use_container_width=True):
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
        'rsi_buy', 'rsi_sell', 'signal_history', 'active_trades', 'last_refresh'
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
            ALL_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"]
            
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
                        
                        # Dove definisci il trade
                        st.session_state.active_trades[pair] = {
                            'entry_price': price,
                            'entry_time': curr_t,
                            'direction': direction,
                            'amount': 100.0  # <--- Aggiungi un valore di default o una variabile
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
    
    # 🔥 DASHBOARD TRADES APERTI - CORRETTO
    if st.session_state.get('active_trades', {}):
        st.subheader("🔥 **TRADES APERTI (1m)**")
        active_df = pd.DataFrame([
            {
                'PAIR': trade_pair,
                'ENTRY': f"{trade['direction']} @ {trade['entry_price']:.5f}", # Rimosso 'amount'
                '⏱️': f"{int(current_time - trade['entry_time'])}s",
                'STATUS': '⏳ APERTO'
            }
            for trade_pair, trade in st.session_state['active_trades'].items()
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

    # 🔄 REFRESH SElettivo ogni 30s per sidebar + scanner
    if st.session_state.get('connected', False):
        time_since_last_refresh = time_module.time() - st.session_state.get('last_refresh', 0)
        if time_since_last_refresh > 30:  # 30s refresh
            st.session_state['last_refresh'] = time_module.time()
            st.rerun()  # Refresh sidebar + tutto

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
