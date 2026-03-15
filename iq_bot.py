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

def reset_manual_prices():
    st.session_state.manual_prices = {"EURGBP": 0.0, "USDCHF": 0.0, "AUDUSD": 0.0, "EURUSD": 0.0}
    st.rerun()

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

# --- LOGICA RILEVAMENTO AUTOMATICO OTC ---
fuso_roma = pytz.timezone('Europe/Rome')
now_roma = datetime.now(pytz.timezone('Europe/Rome'))
giorno_settimana = now_roma.weekday() # 0 = Lunedì ... 5 = Sabato, 6 = Domenica
is_weekend_reale = giorno_settimana >= 5  # True se Sabato (5) o Domenica (6)
now_cet = now_roma.time()
ora_attuale = now_roma.hour

# Il mercato reale chiude Venerdì alle 23:00 e riapre Domenica alle 23:00.
# Quindi è OTC se è Sabato (5) o se è Domenica (6) prima delle 23:00.
if giorno_settimana == 5 or giorno_settimana == 6:
    st.session_state.weekend_mode = True  # OTC AUTO-ATTIVATO
else:
    st.session_state.weekend_mode = False # MERCATO LIVE AUTO-ATTIVATO


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
        st.subheader("🤖 **MERCATO LIVE/OTC**")
        
        # Il bot comunica cosa ha rilevato
        if st.session_state.weekend_mode:
            st.error("🚨 **MERCATO OTC RILEVATO**")
            st.info("🎯 **Sniper Mode Attivo**\n\nMonitoraggio: 4 Valute\n\nRSI 15/85 | BB 20/2.65")
            # Setta automaticamente i parametri fissi per l'OTC
            use_bb, use_rsi = True, True
            bb_period, bb_std = 20, 2.65
            custom_rsi_buy, custom_rsi_sell = 15, 85
        else:
            st.success("🟢 **MERCATO LIVE RILEVATO**")
            st.info("📊 **Standard Mode Attiva**\nMonitoraggio: 10 Valute")
            
            # Lascia a te la scelta dei parametri dal Lun al Ven
            col_t1, col_t2 = st.columns(2)
            use_bb = col_t1.toggle("BB", value=True)
            use_rsi = col_t2.toggle("RSI", value=True)
            
            c_bb1, c_bb2 = st.columns(2)
            bb_period = c_bb1.number_input("Periodo BB", 20)
            bb_std = c_bb2.number_input("Dev BB", 1.80)
            
            c_rsi1, c_rsi2 = st.columns(2)
            custom_rsi_buy = c_rsi1.number_input("RSI Buy", 30)
            custom_rsi_sell = c_rsi2.number_input("RSI Sell", 70)
  
        st.divider()
        # SCANNER SEMPRE DISPONIBILE (Ora si adatta in automatico!)
        st.subheader("👁️ CONTROLLO SCANNER")
        label = "🛑 STOP SCANNER" if st.session_state.scanner_on else "🚀 AVVIA SCANNER"
        if st.button(label, use_container_width=True, type="primary"):
            st.session_state.scanner_on = not st.session_state.scanner_on
            st.rerun()

        # --- LOGICA SIDEBAR OTC ---
        if st.session_state.weekend_mode:
            st.divider()
            st.subheader("🎯 PREZZO MANUALE (OVERRIDE)")
                            
            st.info("Inserisci il prezzo dal Broker:")
            
            if 'manual_prices' not in st.session_state:
                st.session_state.manual_prices = {"EURGBP": 0.0, "USDCHF": 0.0, "AUDUSD": 0.0, "EURUSD": 0.0}
            
            # Crea i 4 campi input
            for pair in ["EURGBP", "USDCHF", "AUDUSD", "EURUSD"]:
                st.session_state.manual_prices[pair] = st.number_input(
                    f"Prezzo {pair}", 
                    value=st.session_state.manual_prices.get(pair, 0.0), 
                    format="%.5f",
                    key=f"input_{pair}" # Aggiungiamo una key univoca per sicurezza
                )

            # Tasto di Reset Chirugico
            if st.button("🧹 RESET PREZZI", use_container_width=True):
                reset_manual_prices()
        
        st.divider()
        st.header("🌍 SESSIONI DI MERCATO")
        
        # Se è weekend o se la modalità weekend è attiva, forziamo tutto su Rosso 🔴
        for city in ["🇬🇧 LONDRA:", "🇺🇸 NEW YORK:", "🇦🇺 SYDNEY:", "🇯🇵 TOKYO:"]:
            if is_weekend_reale or st.session_state.weekend_mode:
                st.write(f"{city} Closed 🔴")
            else:
                for city, (start, end) in {"🇬🇧 LONDRA:": (time(9,0), time(18,0)), "🇺🇸 NEW YORK:": (time(14,0), time(23,0)), "🇦🇺 SYDNEY:": (time(0,0), time(8,0)), "🇯🇵 TOKYO:": (time(0,0), time(9,0))}.items():
                    status = "Open 🟢" if start <= now_roma <= end else "Closed 🔴"
                st.write(f"{city} {status}")
            
                st.info(get_market_status())
                                    
        st.divider()
        st.subheader("🛠️ PARAMETRI TRADING")
        
        st.metric(f"💰 SALDO {st.session_state.account_type}", f"{st.session_state.local_balance:.2f} €")    
        st.session_state.stake = st.number_input("💶 INVESTIMENTO (€)", value=100.0)
        timeframe = st.selectbox("⏱️ TIMEFRAME OPERATIVO (s)", [60, 300], index=0)
                
        st.divider()
        st.header("🔧 STRUMENTI TEST")
        stress_test = st.toggle("🚀 **STRESS MODE**", value=False)
        if stress_test:
            st.warning("⚠️ **Modalità TEST:**  \nno BB - RSI (45/55)")
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
    # FILTRO CHIRURGICO: Cambia asset in base alla modalità
    if st.session_state.weekend_mode:
        # Le 4 coppie più stabili e prevedibili per RSI 20/80 e BB 2.5
        ALL_PAIRS = ["EURGBP", "USDCHF", "AUDUSD", "EURUSD"]
        #st.info("🎯 **Focus Sniper:** Monitoraggio limitato alle 4 coppie chirurgiche.")
    else:
        # Lista completa per il mercato live standard
        ALL_PAIRS = ["EURGBP", "USDCHF", "USDJPY", "EURUSD", "GBPUSD", "AUDUSD", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"]

    # Icone per la visualizzazione (rimangono invariate)
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
        st.plotly_chart(draw_market_map_inverted(h_float, trading_autorizzato), use_container_width=True)
        
    if st.session_state.scanner_on:
        # Messaggio dinamico in base alla modalità
        if st.session_state.weekend_mode:
            st.success("🕵️ SCANNER OTC ATTIVO su 🇪🇺🇬🇧-🇺🇸🇨🇭-🇦🇺🇺🇸-🇪🇺🇺🇸 ", icon="🎯")
        else:
            if not trading_autorizzato:
                st.warning("🛡️ PROTEZIONE Orario: Scanner in pausa.")
            else:
                st.success("SISTEMA IN SCANSIONE LIVE 🔥", icon="📡")
        
        # Sostituisci la chiamata a get_oanda_candles con questa logica:
        for pair in ALL_PAIRS:
            try:
                # Se siamo in weekend e hai inserito un prezzo manuale per questa coppia
                if st.session_state.weekend_mode and pair in st.session_state.get('manual_prices', {}) and st.session_state.manual_prices[pair] > 0:
                    price = st.session_state.manual_prices[pair]
                    # Carichiamo lo storico per mantenere calcoli validi (BB/RSI)
                    candles = get_oanda_candles(pair, 60, 100, "")
                    if candles:
                        # Sovrascriviamo l'ultimo prezzo con quello reale del tuo broker
                        candles[-1]['close'] = price
                else:
                    # Funzionamento standard
                    candles = get_oanda_candles(pair, 60, 100, st.session_state.get("oanda_token", ""))
                    if not candles: continue
                    price = candles[-1]['close']
                    
                df = pd.DataFrame(candles)
                df['RSI'] = ta.rsi(df['close'], length=7)
                price, curr_rsi = df['close'].iloc[-1], df['RSI'].iloc[-1]

                # --- ASSEGNAZIONE PARAMETRI (Sniper vs Manuale) ---
                if st.session_state.weekend_mode:
                    # Parametri SNIPER fissi per il weekend
                    r_buy, r_sell = 20, 80
                    b_per, b_std = 20, 2.5
                    m_fast, m_slow, m_sig = 12, 26, 9
                else:
                    # Parametri LIVE scelti da te nella sidebar
                    r_buy, r_sell = (45, 55) if stress_test else (custom_rsi_buy, custom_rsi_sell)
                    b_per, b_std = (20, 1.8) if stress_test else (bb_period, bb_std)
   
                # Calcolo indicatori comuni
                bb = ta.bbands(df['close'], length=b_per, std=b_std)
                curr_bb_low = bb.filter(like='BBL').iloc[-1]
                curr_bb_up = bb.filter(like='BBU').iloc[-1]
                
                # Logica Segnali
                cond_rsi_buy = curr_rsi < r_buy
                cond_bb_buy = price <= curr_bb_low
                
                cond_rsi_sell = curr_rsi > r_sell
                cond_bb_sell = price >= curr_bb_up

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
        # LOGICA COERENTE CON L'OVERRIDE
        if st.session_state.weekend_mode and pair_display in st.session_state.get('manual_prices', {}) and st.session_state.manual_prices[pair_display] > 0:
            candles_ta = get_oanda_candles(pair_display, timeframe, 160, token)
            if candles_ta:
                candles_ta[-1]['close'] = st.session_state.manual_prices[pair_display]
        else:
            candles_ta = get_oanda_candles(pair_display, timeframe, 160, token)
            
        if candles_ta:
            df_raw = pd.DataFrame(candles_ta)
            
            df_raw['RSI'] = ta.rsi(df_raw['close'], length=7)
            bb_ta = ta.bbands(df_raw['close'], length=bb_period, std=bb_std)
            bb_ta.columns = ['BBL', 'BBM', 'BBU', 'BBB', 'BBP'] 
                        
            df_final = pd.concat([df_raw, bb_ta[['BBL', 'BBM', 'BBU']]], axis=1).tail(100)

            df_final['buy_sig'] = df_final.apply(lambda x: x['close'] if (
                ((x['RSI'] < custom_rsi_buy) if use_rsi else True) and 
                ((x['close'] <= x['BBL']) if use_bb else True) 
            ) else None, axis=1)
            
            df_final['sell_sig'] = df_final.apply(lambda x: x['close'] if (
                ((x['RSI'] > custom_rsi_sell) if use_rsi else True) and 
                ((x['close'] >= x['BBU']) if use_bb else True)
            ) else None, axis=1)
         
            asse_x = df_final['time']
            
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                row_heights=[0.5, 0.25], 
                                vertical_spacing=0.07, 
                                subplot_titles=("📊 Prezzo & Volatilità", "📉 Oscillatore RSI"))
            
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
                st.info("**Regola i parametri e verifica il profitto**")
        
    except Exception as e:
            st.error(f"Errore grafico: {e}")

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
    else:
        st.info("⏳ In attesa di dati per calcolare le performance...")
        
    # --- LOGICA DI REFRESH AUTOMATICO ---
    
    # 1. Messaggio discreto di stato dello scanner
    st.caption(f"🔄 Scanner in esecuzione... Ultimo check: {now_roma.time().strftime('%H:%M:%S')}")
    
    # --- 8. REFRESH LOOP ---
    if st.session_state.scanner_on:
        time_module.sleep(3) 
        st.rerun()
