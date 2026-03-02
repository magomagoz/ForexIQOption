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


# --- CORE LOGIC: MOTORE SEGNALI E CHIUSURA AUTOMATICA ---
if st.session_state.connected:
    Iq = st.session_state.iq
    curr_t = time_module.time()

    # 1. LOGICA DI CHIUSURA (Controlla i trade scaduti ogni ciclo)
    for pair_to_check in list(st.session_state.active_trades.keys()):
        trade = st.session_state.active_trades[pair_to_check]
        # Se sono passati 60 secondi dall'entrata
        if curr_t - trade['entry_time'] >= 60:
            try:
                # Recupera l'ultimo prezzo per determinare l'esito
                candles_check = Iq.get_candles(pair_to_check, 60, 1, curr_t)
                current_price = candles_check[0]['close']
                entry_price = trade['entry_price']
                direction = trade['direction']
                
                # Calcolo Vittoria/Sconfitta
                win = (direction == "BUY" and current_price > entry_price) or \
                      (direction == "SELL" and current_price < entry_price)
                
                result_text = "✅ VITTORIA" if win else "❌ SCONFITTA"
                play_trade_sound("win" if win else "lose")
                
                # Aggiorna il record nello storico segnali
                for h in reversed(st.session_state.signal_history):
                    if h['pair'] == pair_to_check and h['result'] == '⏳ IN CORSO':
                        h['result'] = result_text
                        break
                
                # Rimuovi dai trade attivi
                del st.session_state.active_trades[pair_to_check]
                st.toast(f"Chiuso {pair_to_check}: {result_text}", icon="🏁")
            except: 
                pass

    # 2. INTERFACCIA PARAMETRI
    col1, col2, col3 = st.columns(3)
    with col1: rsi_buy = st.number_input("🟢 RSI Buy (Sotto)", value=45, key="rsi_val_b")
    with col2: rsi_sell = st.number_input("🔴 RSI Sell (Sopra)", value=55, key="rsi_val_s")
    with col3: mode = st.radio("Filtro MACD", ["Standard", "Solo Incroci"], index=0, horizontal=True)

    st.session_state.scanner = st.toggle("🔍 ATTIVA SCANNER AUTOMATICO", value=True)

    # 3. LOGICA DI APERTURA (Scanner ogni 5 secondi)
    if st.session_state.scanner:
        if curr_t - st.session_state.get('scanner_last_update', 0) > 5:
            for p_name in ALL_PAIRS:
                try:
                    # Ottieni candele a 1 minuto
                    raw_candles = Iq.get_candles(p_name, 60, 40, curr_t)
                    df_logic = pd.DataFrame(raw_candles)
                    
                    # Calcolo indicatori
                    df_logic['RSI'] = ta.rsi(df_logic['close'], length=7)
                    macd_res = ta.macd(df_logic['close'], fast=8, slow=17, signal=9)
                    
                    val_rsi = df_logic['RSI'].iloc[-1]
                    val_macd = macd_res['MACD_8_17_9'].iloc[-1]
                    val_sig = macd_res['MACDs_8_17_9'].iloc[-1]
                    price_now = df_logic['close'].iloc[-1]

                    # Condizioni Trigger
                    buy_trigger = val_rsi < rsi_buy and val_macd > val_sig
                    sell_trigger = val_rsi > rsi_sell and val_macd < val_sig

                    if (buy_trigger or sell_trigger) and p_name not in st.session_state.active_trades:
                        direction = "BUY" if buy_trigger else "SELL"
                        
                        # Registra il trade
                        st.session_state.active_trades[p_name] = {
                            'entry_price': price_now, 
                            'entry_time': curr_t, 
                            'direction': direction
                        }
                        
                        # Invia Alert
                        st.session_state.scanner_alerts.append({
                            'pair': p_name, 'type': direction, 'price': price_now, 'rsi': f"{val_rsi:.1f}"
                        })
                        send_telegram_signal(direction, p_name, price_now, round(val_rsi, 1), val_macd)
                        play_trade_sound("buy" if direction == "BUY" else "sell")

                        # Salva nello storico
                        st.session_state.signal_history.append({
                            'time': datetime.now().strftime("%H:%M:%S"),
                            'pair': p_name, 'type': direction, 'price': price_now, 
                            'rsi': f"{val_rsi:.1f}", 'result': '⏳ IN CORSO'
                        })
                except: 
                    continue
            st.session_state.scanner_last_update = curr_t

    # --- VISUALIZZAZIONE DASHBOARD ---
    if st.session_state.active_trades:
        st.subheader("🔥 **TRADES APERTI (1m)**")
        active_df = pd.DataFrame([
            {
                'COPPIA': pair, 
                'DIREZIONE': trade['direction'], 
                'ENTRATA': f"{trade['entry_price']:.5f}",
                '⏱️ SCADENZA': f"{max(0, 60 - int(time_module.time() - trade['entry_time']))}s",
                'STATUS': '⏳ LIVE'
            } for pair, trade in st.session_state.active_trades.items()
        ])
        st.dataframe(active_df, use_container_width=True, hide_index=True)

    # GRAFICO REALTIME
    target_pair = st.session_state.get('pair', 'EURUSD')
    st.subheader(f"📊 MONITORAGGIO: {target_pair}")
    try:
        plot_candles = Iq.get_candles(target_pair, 60, 100, time_module.time())
        df_plot = pd.DataFrame(plot_candles)
        df_plot['from'] = pd.to_datetime(df_plot['from'], unit='s')
        df_plot.set_index('from', inplace=True)
        df_plot['RSI'] = ta.rsi(df_plot['close'], length=7)
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['open'], high=df_plot['max'], low=df_plot['min'], close=df_plot['close'], name="Prezzo"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['RSI'], name="RSI", line=dict(color='purple')), row=2, col=1)
        fig.add_hline(y=rsi_buy, line_color="green", line_dash="dash", row=2, col=1)
        fig.add_hline(y=rsi_sell, line_color="red", line_dash="dash", row=2, col=1)
        fig.update_layout(height=600, showlegend=False, xaxis_rangeslider_visible=False, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
    except: 
        st.info("Sincronizzazione grafico in corso...")

    # STATISTICHE E STORICO
    st.markdown("---")
    col_a, col_b = st.columns([1, 2])
    
    if st.session_state.signal_history:
        df_h = pd.DataFrame(st.session_state.signal_history)
        with col_a:
            st.subheader("🎯 ** PERFORMANCE**")
            # Filtra solo quelli conclusi
            finiti = df_h[df_h['result'].isin(['✅ VITTORIA', '❌ SCONFITTA'])]
            if not finiti.empty:
                vittorie = len(finiti[finiti['result'] == '✅ VITTORIA'])
                wr = (vittorie / len(finiti)) * 100
                st.metric("Winrate", f"{wr:.1f}%", f"{vittorie}W - {len(finiti)-vittorie}L")
            else:
                st.write("In attesa dei primi esiti...")

        with col_b:
            st.subheader("📋 **STORICO RECENTE**")
            st.dataframe(df_h.tail(15)[['time', 'pair', 'type', 'price', 'result']], use_container_width=True, hide_index=True)

    # AUTO REFRESH (10 secondi)
    if time_module.time() - st.session_state.get('last_refresh', 0) > 10:
        st.session_state.last_refresh = time_module.time()
        st.rerun()
