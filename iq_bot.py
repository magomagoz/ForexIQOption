import streamlit as st
import pandas as pd
import pandas_ta as ta
import pytz
import time as time_module
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from PIL import Image
import requests
import json
import os
from datetime import datetime, time, timedelta

# --- 1. CONFIGURAZIONI E TELEGRAM ---
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "IL_TUO_TOKEN_QUI")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "IL_TUO_CHAT_ID_QUI")

def get_oanda_candles(pair, timeframe_sec, count, api_token):
    symbol = f"{pair}=X"
    interval = "1m" if timeframe_sec <= 60 else "5m"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range=1d"
    
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=7)
        data = response.json()
        result = data['chart']['result'][0]
        stamps = result['timestamp']
        quote = result['indicators']['quote'][0]
        
        candles = []
        # Prendiamo gli ultimi 'count' valori reali
        for i in range(len(stamps)):
            if quote['close'][i] is not None:
                dt = datetime.fromtimestamp(stamps[i], pytz.timezone('Europe/Rome'))
                candles.append({
                    'time': dt.strftime("%H:%M"), 
                    'open': quote['open'][i], 'max': quote['high'][i],
                    'min': quote['low'][i], 'close': quote['close'][i]
                })
        return candles[-count:] # Restituisce solo il numero richiesto
    except:
        return None

def genera_trade_id():
    return f"TRD-{int(datetime.now().timestamp()) % 1000000}"

def invia_telegram(messaggio):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": messaggio, "parse_mode": "Markdown"}, timeout=5)
    except Exception as e:
        print(f"Errore Telegram: {e}")

def send_telegram_signal(signal_type, pair, price, rsi, trade_id):
    timestamp = datetime.now().strftime("%H:%M:%S")
    message = (
        f"🚀 *NUOVA OPERAZIONE*\n"
        f"🔔 *Segnale:* {signal_type}\n"
        f"🆔 ID: `{trade_id}`\n"
        f"📊 Asset: {pair}\n"
        f"💰 Prezzo: `{price:.5f}`\n"
        f"📊 RSI: `{rsi:.1f}`\n"
        f"⏰ Ora: {timestamp}"
    )
    invia_telegram(message)

def registra_trade(trade_id, pair, direction, risultato, profitto):
    file_path = "daily_report.json"
    data = []
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            data = json.load(f)
    data.append({
        "id": trade_id, "pair": pair, "direction": direction,
        "risultato": risultato, "profitto": profitto,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })
    with open(file_path, "w") as f:
        json.dump(data, f)

def genera_report_finale():
    file_path = "daily_report.json"
    if not os.path.exists(file_path): return
    with open(file_path, "r") as f:
        trades = json.load(f)
    total = len(trades)
    wins = len([t for t in trades if t['risultato'] == "WIN"])
    loss = total - wins
    profitto_totale = sum([t['profitto'] for t in trades])
    accuracy = (wins / total * 100) if total > 0 else 0
    report = (
        f"📊 *REPORT GIORNALIERO SENTINEL AI*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📈 Totale Trade: {total}\n"
        f"✅ Win: {wins} | ❌ Loss: {loss}\n"
        f"🎯 Accuracy: {accuracy:.1f}%\n"
        f"💰 Profitto Netto: *{profitto_totale:.2f}€*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏁 Sessione terminata. Sistema in standby."
    )
    invia_telegram(report)
    os.remove(file_path)

JOURNAL_FILE = "trading_journal.json"

def load_journal():
    if os.path.exists(JOURNAL_FILE):
        try:
            with open(JOURNAL_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def save_journal(history):
    with open(JOURNAL_FILE, "w") as f:
        json.dump(history, f)

def play_trade_sound(sound_type="buy"):
    sounds = {
        "buy": "https://actions.google.com/sounds/v1/alarms/beep_short.ogg",
        "win": "https://actions.google.com/sounds/v1/cartoon/clink_vibrant.ogg"
    }
    placeholder = st.empty()
    try:
        with placeholder:
            st.audio(sounds.get(sound_type, sounds["buy"]), autoplay=True)
        time_module.sleep(2.0)
    except:
        pass
    placeholder.empty()

def get_market_status():
    fuso_roma = pytz.timezone('Europe/Rome')
    now_roma = datetime.now(fuso_roma)
    now_time = now_roma.time()

    londra = (time(9,0), time(18,0))
    new_york = (time(14,0), time(23,0))
    
    is_londra = londra[0] <= now_time <= londra[1]
    is_ny = new_york[0] <= now_time <= new_york[1]
    
    if is_londra and is_ny:
        return "🔥 SOVRAPPOSIZIONE (EU/USA)\n\nAlta Volatilità"
    elif is_londra:
        return "🇪🇺 SESSIONE LONDRA"
    elif is_ny:
        return "🇺🇸 SESSIONE NEW YORK"
    else:
        return "💤 MERCATO LENTO"

def draw_market_map_inverted(current_hour_float, trading_autorizzato):
    fig = go.Figure()
    try:
        bg_image = Image.open("mondo.png")
    except:
        bg_image = "https://via.placeholder.com/1200x400/220044/white?text=MAPPA+SESSIONI"

    fig.add_layout_image(dict(
        source=bg_image, xref="x", yref="y", x=24, y=4.5,
        sizex=24, sizey=4.5, sizing="stretch", opacity=1.0, layer="below"
    ))

    ritardo_ore = -5 / 60
    x_pos = (current_hour_float - ritardo_ore) % 24
    color_laser = "#0F3ADA" if not trading_autorizzato else "#FFD700"

    fig.add_shape(
        type="line", x0=x_pos, x1=x_pos, y0=0, y1=4.5, 
        line=dict(color=color_laser, width=2)
    )

    fig.update_layout(
        xaxis=dict(range=[24, 0], showgrid=False, visible=False, fixedrange=True),
        yaxis=dict(range=[0, 4.5], showgrid=False, visible=False, fixedrange=True),
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=0, b=0), height=350
    )
    return fig

# --- 2. SETUP STREAMLIT E SESSIONE ---
st.set_page_config(page_title="Sentinel AI", page_icon="🚀", layout="wide")

try:
    logo = Image.open("banner.png")
    st.image(logo, use_column_width=True, caption="Yahoo Finance Signals PRO")
except:
    st.image("https://via.placeholder.com/800x100/0066cc/white?text=SENTINEL+AI", use_column_width=True)

# INIZIALIZZAZIONI SICURE
if 'connected' not in st.session_state: st.session_state.connected = False
if 'account_type' not in st.session_state: st.session_state.account_type = "TEST (YAHOO)"
if 'active_trades' not in st.session_state: st.session_state.active_trades = {}
if 'signal_history' not in st.session_state: st.session_state.signal_history = load_journal()
if 'local_balance' not in st.session_state: st.session_state.local_balance = 10000.0
if 'scanner_on' not in st.session_state: st.session_state.scanner_on = False
if 'weekend_mode' not in st.session_state: st.session_state.weekend_mode = False 
if 'custom_macd_fast' not in st.session_state: st.session_state.custom_macd_fast = 12
if 'custom_macd_slow' not in st.session_state: st.session_state.custom_macd_slow = 26
if 'custom_macd_sig' not in st.session_state: st.session_state.custom_macd_sig = 9

giorno_settimana = datetime.now(pytz.timezone('Europe/Rome')).weekday()
is_weekend_reale = giorno_settimana >= 5  # True se Sabato (5) o Domenica (6)

# --- 3. SIDEBAR (VERSIONE CHIRURGICA) ---
with st.sidebar:
    st.title("⚙️ YAHOO TRADING")
    
    if not st.session_state.connected:
        st.subheader("🔑 Accesso Rapido")
        st.info("Connettiti per i dati real-time.")
        if st.button("🔌 CONNETTI SISTEMA", use_container_width=True, type="primary"):
            with st.spinner("Sincronizzazione..."):
                test_data = get_oanda_candles("EURUSD", 60, 1, "YAHOO")
                if test_data:
                    st.session_state.connected = True
                    st.session_state.oanda_token = "YAHOO_MODE" 
                    st.rerun()
    else:
        if st.button("🔴 DISCONNETTI", use_container_width=True):
            st.session_state.connected = False
            st.session_state.scanner_on = False
            st.rerun()

        st.divider()
        # --- MODALITÀ OPERATIVA UNICA ---
        st.subheader("♟️ IL 6° GIORNO (OTC)")
        st.session_state.weekend_mode = st.toggle("🧠🍹 ATTIVA SABATO MAGICO", value=st.session_state.weekend_mode)
        
        # SCANNER SEMPRE DISPONIBILE
        label = "🛑 STOP SCANNER" if st.session_state.scanner_on else "🚀 AVVIA SCANNER"
        if st.button(label, use_container_width=True, type="primary"):
            st.session_state.scanner_on = not st.session_state.scanner_on
            st.rerun()

        # --- SETUP INDICATORI DINAMICO ---
        if st.session_state.weekend_mode:
            st.success("🎯 **Sniper Mode Attiva**\n\nParametri: RSI (20/80) | BB (20, 2.5)")
            use_bb, use_rsi, use_macd = True, True, False
            bb_period, bb_std = 20, 2.50
            custom_rsi_buy, custom_rsi_sell = 20, 80
            custom_macd_fast, custom_macd_slow, custom_macd_sig = 12, 26, 9
        else:
            st.info("📊 **Standard Mode Attiva**")
            col_t1, col_t2, col_t3 = st.columns(3)
            use_bb = col_t1.toggle("BB", value=True)
            use_rsi = col_t2.toggle("RSI", value=True)
            use_macd = col_t3.toggle("MACD", value=False)
            
            c_bb1, c_bb2 = st.columns(2)
            bb_period = c_bb1.number_input("Periodo BB", 20)
            bb_std = c_bb2.number_input("Dev BB", 1.80)
            
            c_rsi1, c_rsi2 = st.columns(2)
            custom_rsi_buy = c_rsi1.number_input("RSI Buy", 30)
            custom_rsi_sell = c_rsi2.number_input("RSI Sell", 70)
            
            custom_macd_fast, custom_macd_slow, custom_macd_sig = 12, 26, 9
        
        now_roma = datetime.now(pytz.timezone('Europe/Rome'))
        now_cet = now_roma.time()

        st.divider()
        st.header("🌍 SESSIONI DI MERCATO")
        
        # Se è weekend o se la modalità weekend è attiva, forziamo tutto su Rosso 🔴
        for city in ["🇬🇧 LONDRA:", "🇺🇸 NEW YORK:", "🇦🇺 SYDNEY:", "🇯🇵 TOKYO:"]:
            if is_weekend_reale or st.session_state.weekend_mode:
                st.write(f"{city} Closed 🔴")
            else:
                for city, (start, end) in {"🇬🇧 LONDRA:": (time(9,0), time(18,0)), "🇺🇸 NEW YORK:": (time(14,0), time(23,0)), "🇦🇺 SYDNEY:": (time(0,0), time(8,0)), "🇯🇵 TOKYO:": (time(0,0), time(9,0))}.items():
                    status = "Open 🟢" if start <= now_cet <= end else "Closed 🔴"
                st.write(f"{city} {status}")
            
                st.info(get_market_status())
                                    
        st.divider()
        st.subheader("🛠️ PARAMETRI TRADING")
        
        st.metric(f"💰 SALDO {st.session_state.account_type}", f"{st.session_state.local_balance:.2f} €")    
        st.session_state.stake = st.number_input("💰 INVESTIMENTO (€)", value=100.0)
        timeframe = st.selectbox("⏱️ TIMEFRAME OPERATIVO (s)", [60, 300], index=0)
                
        st.divider()
        st.header("🔧 STRUMENTI TEST")
        stress_test = st.toggle("🚀 **STRESS MODE**", value=False)
        if stress_test:
            st.warning("⚠️ **Modalità TEST:**  \nno BB - RSI (45/55) - no MACD")
        else:
            st.success("🟢 **Modalità REALE:**  \nvedi gli indicatori scelti sopra")
            
        st.divider()
        if st.button("🔔 **TEST AUDIO & TELEGRAM**", use_container_width=True):
            play_trade_sound("buy")
            invia_telegram("✅ **SENTINEL AI: SYSTEM CHECK**\nBot online e sincronizzato con Yahoo Finance. 🚀")
            st.toast("Test completato!", icon="📲")
        
        st.divider()
        if st.button("🗑️ **PULISCI SEGNALI**", use_container_width=True):
            st.session_state.signal_history = []
            save_journal([]) 
            st.rerun()
        st.divider()

# --- 4. MAIN DASHBOARD ---
if st.session_state.connected:
    ALL_PAIRS = ["EURGBP", "USDCHF", "USDJPY", "EURUSD", "GBPUSD", "AUDUSD", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"]
    icons = {"EURGBP": "🇪🇺🇬🇧", "USDCHF": "🇺🇸🇨🇭", "USDJPY": "🇺🇸🇯🇵","EURUSD": "🇪🇺🇺🇸", "GBPUSD": "🇬🇧🇺🇸", "AUDUSD": "🇦🇺🇺🇸", "USDCAD": "🇺🇸🇨🇦", "NZDUSD": "🇳🇿🇺🇸", "EURJPY": "🇪🇺🇯🇵", "GBPJPY": "🇬🇧🇯🇵"}

    fuso_roma = pytz.timezone('Europe/Rome')
    now_roma = datetime.now(fuso_roma)
    now_time = now_roma.time()
    h_float = now_roma.hour + (now_roma.minute / 60)

    window_1 = (time(9, 0), time(12, 0))
    window_2 = (time(14, 0), time(18, 0))
    is_trading_time = (window_1[0] <= now_time <= window_1[1]) or (window_2[0] <= now_time <= window_2[1])
    trading_autorizzato = is_trading_time or stress_test

    if now_time >= time(18, 30) and not st.session_state.get('report_sent', False):
        genera_report_finale()
        st.session_state.report_sent = True
    
    st.subheader("🌍 Live Market Flow 24h")
    
    if st.session_state.weekend_mode or is_weekend_reale:
        try:
            # Carica banner2.png se siamo in modalità weekend
            img_weekend = Image.open("banner2.png")
            st.image(img_weekend, use_column_width=True, caption="MODALITÀ WEEKEND ATTIVA 🔴 MERCATI CHIUSI")
        except:
            st.warning("Immagine banner2.png non trovata. Carica il file nella cartella del progetto.")
    else:
        # Mostra il grafico Plotly originale "draw_market_map_inverted"
        #st.plotly_chart(draw_market_map_inverted(h_float, trading_autorizzato), use_container_width=True)
        st.plotly_chart(draw_market_map_inverted(h_float, trading_autorizzato), use_container_width=True, config={'displayModeBar': False})
        
    if st.session_state.scanner_on:
        # Messaggio dinamico in base alla modalità
        if st.session_state.weekend_mode:
            st.success("🕵️ SCANNER SNIPER OTC ATTIVO su tutte le coppie", icon="🎯")
        else:
            if not trading_autorizzato:
                st.warning("🛡️ PROTEZIONE Orario: Scanner in pausa.")
            else:
                st.success("SISTEMA IN SCANSIONE LIVE 🔥", icon="📡")

        # --- LOOP DI SCANSIONE UNIVERSALE ---
        for pair in ALL_PAIRS:
            try:
                token = st.session_state.get("oanda_token", "")
                # Usiamo il timeframe scelto o 60s per lo stress test
                current_tf = 60 if stress_test else timeframe
                candles = get_oanda_candles(pair, current_tf, 100, token)
                
                if not candles or len(candles) < 30: continue
                    
                df = pd.DataFrame(candles)
                df['RSI'] = ta.rsi(df['close'], length=7)
                price, curr_rsi = df['close'].iloc[-1], df['RSI'].iloc[-1]

                # --- ASSEGNAZIONE PARAMETRI (Sniper vs Manuale) ---
                if st.session_state.weekend_mode:
                    # Parametri SNIPER fissi per il weekend
                    r_buy, r_sell = 20, 80
                    b_per, b_std = 20, 2.5
                    m_fast, m_slow, m_sig = 12, 26, 9
                    u_macd = False # Sniper non usa MACD per evitare ritardi
                else:
                    # Parametri LIVE scelti da te nella sidebar
                    r_buy, r_sell = (45, 55) if stress_test else (custom_rsi_buy, custom_rsi_sell)
                    b_per, b_std = (20, 1.8) if stress_test else (bb_period, bb_std)
                    m_fast, m_slow, m_sig = custom_macd_fast, custom_macd_slow, custom_macd_sig
                    u_macd = use_macd if not stress_test else False

                # Calcolo indicatori comuni
                bb = ta.bbands(df['close'], length=b_per, std=b_std)
                curr_bb_low = bb.filter(like='BBL').iloc[-1]
                curr_bb_up = bb.filter(like='BBU').iloc[-1]
                
                # Logica Segnali
                cond_rsi_buy = curr_rsi < r_buy
                cond_bb_buy = price <= curr_bb_low
                
                cond_rsi_sell = curr_rsi > r_sell
                cond_bb_sell = price >= curr_bb_up

                # Aggiunta MACD solo se richiesto (non in Sniper)
                if u_macd:
                    macd = ta.macd(df['close'], fast=m_fast, slow=m_slow, signal=m_sig)
                    c_macd, c_sig = macd.iloc[-1, 0], macd.iloc[-1, 2]
                    is_buy = cond_rsi_buy and cond_bb_buy and (c_macd > c_sig)
                    is_sell = cond_rsi_sell and cond_bb_sell and (c_macd < c_sig)
                else:
                    is_buy = cond_rsi_buy and cond_bb_buy
                    is_sell = cond_rsi_sell and cond_bb_sell

                # --- ESECUZIONE SEGNALE ---
                if (is_buy or is_sell) and pair not in st.session_state.active_trades:
                    direction = "BUY" if is_buy else "SELL"
                    t_id = genera_trade_id()
                    st.session_state.active_trades[pair] = {
                        'id': t_id, 'entry_price': price, 
                        'entry_time': time_module.time(), 'direction': direction
                    }
                    
                    st.session_state.signal_history.append({
                        'time': datetime.now().strftime("%H:%M:%S"),
                        'pair': pair, 
                        'dir': direction, 
                        'price': f"{price:.5f}",
                        'rsi': round(curr_rsi, 1), 
                        'tipo': "🎯 SNIPER" if st.session_state.weekend_mode else "📊 STD", # Nuova colonna
                        'result': "⏳ In corso..."
                    })
                    
                    save_journal(st.session_state.signal_history)
                    send_telegram_signal(direction, pair, price, curr_rsi, t_id)
                    play_trade_sound("buy")

            except Exception as e:
                continue
    
    # --- 5. ANALISI TECNICA GRAFICA (CORRETTA) ---
    st.divider()
    st.subheader("📈 Analisi Tecnica")
    pair_display = st.selectbox("Seleziona asset per grafico", ALL_PAIRS)
    
    try:
        token = st.session_state.get("oanda_token", "")
        candles_ta = get_oanda_candles(pair_display, timeframe, 160, token)
        if candles_ta:
            df_raw = pd.DataFrame(candles_ta)
            
            df_raw['RSI'] = ta.rsi(df_raw['close'], length=7)
            bb_ta = ta.bbands(df_raw['close'], length=bb_period, std=bb_std)
            bb_ta.columns = ['BBL', 'BBM', 'BBU', 'BBB', 'BBP'] 
            
            # Usiamo i parametri dinamici della sidebar anche qui!
            macd_ta = ta.macd(df_raw['close'], 
                              fast=custom_macd_fast, 
                              slow=custom_macd_slow, 
                              signal=custom_macd_sig)
            macd_ta.columns = ['MACD', 'HIST', 'SIGNAL']
            
            df_final = pd.concat([df_raw, bb_ta[['BBL', 'BBM', 'BBU']], macd_ta], axis=1).tail(100)

            df_final['buy_sig'] = df_final.apply(lambda x: x['close'] if (
                ((x['RSI'] < custom_rsi_buy) if use_rsi else True) and 
                ((x['close'] <= x['BBL']) if use_bb else True) and 
                ((x['MACD'] > x['SIGNAL']) if use_macd else True)
            ) else None, axis=1)
            
            df_final['sell_sig'] = df_final.apply(lambda x: x['close'] if (
                ((x['RSI'] > custom_rsi_sell) if use_rsi else True) and 
                ((x['close'] >= x['BBU']) if use_bb else True) and 
                ((x['MACD'] < x['SIGNAL']) if use_macd else True)
            ) else None, axis=1)
         
            asse_x = df_final['time']
            
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                                row_heights=[0.5, 0.25, 0.25], 
                                vertical_spacing=0.07, 
                                subplot_titles=("📊 Prezzo & Volatilità", "📉 Oscillatore RSI", "🚀 Momentum MACD"))
            
            # --- PANNELLO 1: Candele + Bollinger ---
            fig.add_trace(go.Candlestick(x=asse_x, open=df_final['open'], high=df_final['max'], 
                                         low=df_final['min'], close=df_final['close'], name="Prezzo"), row=1, col=1)
            
            fig.add_trace(go.Scatter(x=asse_x, y=df_final['BBU'], line=dict(color='rgba(0,71,171,0.4)', width=1), name="BBU"), row=1, col=1)
            fig.add_trace(go.Scatter(x=asse_x, y=df_final['BBM'], line=dict(color='rgba(170,170,170,0.3)', width=1), name="BBM"), row=1, col=1)
            fig.add_trace(go.Scatter(x=asse_x, y=df_final['BBL'], line=dict(color='rgba(0,71,171,0.4)', width=1), 
                                     fill='tonexty', fillcolor='rgba(100, 100, 255, 0.05)', name="BBL"), row=1, col=1)

            # Subplot 2: RSI con soglie dinamiche
            fig.add_trace(go.Scatter(x=asse_x, y=df_final['RSI'], line=dict(color='#AB63FA'), name="RSI"), row=2, col=1)
            line_buy = 45 if stress_test else custom_rsi_buy
            line_sell = 55 if stress_test else custom_rsi_sell
            fig.add_hline(y=line_buy, line_color="green", row=2, col=1, line_dash="dash")
            fig.add_hline(y=line_sell, line_color="red", row=2, col=1, line_dash="dash")

            # Subplot 3: MACD con logica colori corretta
            macd_colors = []
            hist_diff = df_final['HIST'].diff()
            for i in range(len(df_final)):
                val = df_final['HIST'].iloc[i]
                diff = hist_diff.iloc[i]
                if pd.isna(diff): macd_colors.append('rgba(170,170,170,0.5)')
                elif val > 0:
                    macd_colors.append('#26A69A' if diff > 0 else '#B2DFDB') # Verde acceso / opaco
                else:
                    macd_colors.append('#EF5350' if diff < 0 else '#FFCDD2') # Rosso acceso / opaco

            fig.add_trace(go.Bar(x=asse_x, y=df_final['HIST'], marker_color=macd_colors, name="Istogramma"), row=3, col=1)
            fig.add_trace(go.Scatter(x=asse_x, y=df_final['MACD'], line=dict(color='#00E5FF', width=2), name="MACD"), row=3, col=1)
            fig.add_trace(go.Scatter(x=asse_x, y=df_final['SIGNAL'], line=dict(color='#FF9100', width=2), name="Signal"), row=3, col=1)

            fig.update_layout(
                xaxis_rangeslider_visible=False,
                hovermode="x unified",
                template="plotly_dark",
                height=800
            )

            # --- AGGIUNGI QUESTO PER LE RIGHE VERTICALI E IL MIRINO ---
            
            fig.update_xaxes(
                type='category', 
                tickangle=45, 
                nticks=20, 
                
                showgrid=True, 
                gridcolor='rgba(130,130,130,0.08)', # Righe verticali fisse leggere
                
                showspikes=True, 
                spikemode='across', 
                spikecolor="black", 
                spikethickness=1, 
                spikedash="solid"
            )
          
            # Freccia BUY (posizionata leggermente sotto il minimo della candela)
            fig.add_trace(go.Scatter(
                x=asse_x, y=df_final['buy_sig'] * 0.9998, # Offset per non coprire la candela
                mode='markers', 
                marker=dict(symbol='triangle-up', size=15, color='#00ff88', line=dict(width=1, color='white')), 
                name="Entry BUY"
            ), row=1, col=1)
            
            # Freccia SELL (posizionata leggermente sopra il massimo della candela)
            fig.add_trace(go.Scatter(
                x=asse_x, y=df_final['sell_sig'] * 1.0002, # Offset per non coprire la candela
                mode='markers', 
                marker=dict(symbol='triangle-down', size=15, color='#ff3333', line=dict(width=1, color='white')), 
                name="Entry SELL"
            ), row=1, col=1)

            st.plotly_chart(fig, use_container_width=True)

            # --- DASHBOARD DISTANZA TARGET (SNIPER MODE) ---
            if st.session_state.weekend_mode:
                st.divider()
                st.subheader("🎯 **Monitoraggio Sniper OTC**")
                
                ultimo_prezzo = df_final['close'].iloc[-1]
                bbu_25 = df_final['BBU'].iloc[-1]
                bbl_25 = df_final['BBL'].iloc[-1]
                
                # Calcolo distanze
                distanza_su = bbu_25 - ultimo_prezzo
                distanza_giu = ultimo_prezzo - bbl_25
                
                # Percentuale di avvicinamento (100% = segnale imminente)
                # Calcoliamo quanto manca rispetto alla larghezza totale del canale
                canale_totale = bbu_25 - bbl_25
                perc_su = max(0, (1 - (distanza_su / (canale_totale/2))) * 100)
                perc_giu = max(0, (1 - (distanza_giu / (canale_totale/2))) * 100)

                m1, m2 = st.columns(2)
                
                with m1:
                    color_su = "red" if distanza_su < 0 else "white"
                    st.metric("DISTANZA BANDA SUPERIORE (SELL)", f"{distanza_su:.5f}", 
                              delta=f"{perc_su:.1f}% al Target", delta_color="inverse")
                if distanza_su <= 0: st.error("🔥 ZONA SELL RAGGIUNTA!")
                
                with m2:
                    st.metric("DISTANZA BANDA INFERIORE (BUY)", f"{distanza_giu:.5f}", 
                              delta=f"{perc_giu:.1f}% al Target", delta_color="normal")
                if distanza_giu <= 0: st.success("🔥 ZONA BUY RAGGIUNTA!")

                st.progress(min(max(perc_su, perc_giu) / 100, 1.0))
            
            st.write("---")
            st.subheader("📊 Analisi Performance (Backtest 60s)")
            
            # Calcoliamo i segnali attuali basati sui parametri scelti
            n_buy = df_final['buy_sig'].notnull().sum()
            n_sell = df_final['sell_sig'].notnull().sum()
            totale_segnali = n_buy + n_sell

            if st.button("🔍 VERIFICA ESITO (SCADENZA 60s)", use_container_width=True, type="primary"):
                wins_buy, wins_sell = 0, 0
                
                # Analizziamo le candele (escludiamo l'ultima perché non ha ancora l'esito a 60s)
                for i in range(len(df_final) - 1):
                    # Controllo BUY: se il prezzo della candela successiva è superiore
                    if pd.notnull(df_final['buy_sig'].iloc[i]):
                        if df_final['close'].iloc[i+1] > df_final['close'].iloc[i]:
                            wins_buy += 1
                    
                    # Controllo SELL: se il prezzo della candela successiva è inferiore
                    if pd.notnull(df_final['sell_sig'].iloc[i]):
                        if df_final['close'].iloc[i+1] < df_final['close'].iloc[i]:
                            wins_sell += 1

                # Calcoli finali
                tot_vinti = wins_buy + wins_sell
                tot_persi = totale_segnali - tot_vinti
                accuracy = (tot_vinti / totale_segnali * 100) if totale_segnali > 0 else 0
                
                # Simulazione economica (Payout medio 85%)
                investimento_totale = totale_segnali * st.session_state.stake
                profitto_lordo = (wins_buy + wins_sell) * (st.session_state.stake * 0.85)
                perdita_totale = tot_persi * st.session_state.stake
                bilancio_netto = profitto_lordo - perdita_totale

                # Visualizzazione risultati
                c1, c2, c3 = st.columns(3)
                c1.metric("🟢 BUY VINCENTI", f"{wins_buy} / {n_buy}")
                c2.metric("🔴 SELL VINCENTI", f"{wins_sell} / {n_sell}")
                c3.metric("🎯 ACCURACY", f"{accuracy:.1f}%")

                # Box riassuntivo con colore dinamico
                colore_box = "green" if bilancio_netto > 0 else "red"
                st.markdown(f"""
                <div style="padding:20px; border-radius:10px; border: 2px solid {colore_box}; background-color: rgba(0,0,0,0.1);">
                    <h3 style="margin-top:0;">💰 Risultato Economico Stimato</h3>
                    <p>Segnali Totali: <b>{totale_segnali}</b> (Vinti: <span style="color:#00ff88;">{tot_vinti}</span> | Persi: <span style="color:#ff3333;">{tot_persi}</span>)</p>
                    <h2 style="color:{colore_box}; margin-bottom:0;">Profitto Netto: {bilancio_netto:.2f} €</h2>
                    <small>Basato su investimento di {st.session_state.stake}€ e payout 85%</small>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("Regola i parametri e premi il tasto per vedere se saresti in profitto con questa configurazione.")
        
    except Exception as e:
            st.error(f"Errore grafico TA: {e}")

    # --- 6. VERIFICA ESITI TRADE ---
    now = time_module.time()
    for pair, trade in list(st.session_state.active_trades.items()):
        if now - trade['entry_time'] >= timeframe:
            try:
                res = get_oanda_candles(pair, timeframe, 1, "YAHOO")
                if not res: continue
                exit_price = res[0]['close']
                win = (exit_price > trade['entry_price']) if trade['direction'] == "BUY" else (exit_price < trade['entry_price'])
                res_status = "WIN" if win else "LOSS"
                profit = (st.session_state.stake * 0.85) if win else -st.session_state.stake
                st.session_state.local_balance += profit
                if win: play_trade_sound("win")
                colore = "✅" if win else "❌"
                invia_telegram(f"{colore} *ESITO*\nAsset: {pair}\nRisultato: {res_status}\nProfit: {profit:.2f}€")
                registra_trade(trade['id'], pair, trade['direction'], res_status, profit)
                for s in reversed(st.session_state.signal_history):
                    if s['pair'] == pair and s['result'] == "⏳ In corso...":
                        s['result'] = f"{colore} {res_status}"
                        break
                save_journal(st.session_state.signal_history)
                del st.session_state.active_trades[pair]
            except: continue
    
    # --- 7. TABELLA JOURNAL & PERFORMANCE HUB ---
    st.divider()
    
    if st.session_state.signal_history:
        df_journal = pd.DataFrame(st.session_state.signal_history)
        
        # Calcolo statistiche separate
        def calc_stats(df_sub):
            total = len(df_sub)
            wins = len(df_sub[df_sub['result'].str.contains("WIN", na=False)])
            accuracy = (wins / total * 100) if total > 0 else 0
            return total, wins, accuracy

        # Filtriamo i dati per tipo
        df_sniper = df_journal[df_journal['tipo'] == "🎯 SNIPER"]
        df_std = df_journal[df_journal['tipo'] == "📊 STD"]

        t_sniper, w_sniper, acc_sniper = calc_stats(df_sniper)
        t_std, w_std, acc_std = calc_stats(df_std)

        # Visualizzazione Statistiche
        st.subheader("📊 Performance Hub")
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown(f"**🎯 Strategia SNIPER**")
            st.metric("Win Rate", f"{acc_sniper:.1f}%", f"{w_sniper}W / {t_sniper}T")
            st.progress(acc_sniper / 100)

        with c2:
            st.markdown(f"**📊 Strategia STANDARD**")
            st.metric("Win Rate", f"{acc_std:.1f}%", f"{w_std}W / {t_std}T")
            st.progress(acc_std / 100)

        st.divider()
        
        # Visualizzazione Tabella Journal
        st.subheader("📋 Registro Operazioni")
        st.dataframe(df_journal.iloc[::-1], use_container_width=True, hide_index=True)
    else:
        st.info("⏳ In attesa di dati per calcolare le performance...")
    
    # --- LOGICA DI REFRESH AUTOMATICO ---
    
    # 1. Messaggio discreto di stato dello scanner
    st.caption(f"🔄 Scanner in esecuzione... Ultimo check: {now_roma.time().strftime('%H:%M:%S')}")
    
    # --- 8. REFRESH LOOP ---
    if st.session_state.scanner_on:
        time_module.sleep(3) 
        st.rerun()
