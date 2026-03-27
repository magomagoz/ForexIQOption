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
import websocket
from datetime import datetime, time, timedelta

# Importazione MT5 sicura
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

# --- 1. CONFIGURAZIONI, TELEGRAM E DERIV ---
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "IL_TUO_TOKEN_QUI")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "IL_TUO_CHAT_ID_QUI")
DERIV_TOKEN = st.secrets.get("DERIV_TOKEN", "") 
DERIV_APP_ID = "71759" 

ALL_PAIRS = ["EURUSD", "AUDUSD", "USDCAD", "USDCHF", "USDJPY"]
icons = {"EURUSD": "🇪🇺🇺🇸", "AUDUSD": "🇦🇺🇺🇸", "USDCAD": "🇺🇸🇨🇦", "USDCHF": "🇺🇸🇨🇭", "USDJPY": "🇺🇸🇯🇵"}

fuso_roma = pytz.timezone('Europe/Rome')
now_roma = datetime.now(fuso_roma)
giorno_settimana = now_roma.weekday() 
is_weekend_reale = giorno_settimana >= 5  
now_cet = now_roma.time()
ora_attuale = now_roma.hour

def to_deriv_symbol(pair):
    # Se passiamo già un simbolo R_, non lo modifichiamo
    if pair.startswith("R_"): return pair 
    
    # Controlla l'interruttore manuale della dashboard (se non c'è, usa il calendario)
    is_otc = st.session_state.get('weekend_mode', is_weekend_reale)
    
    if is_otc:
        if pair == "EURUSD": return "R_50"
        if pair == "USDJPY": return "R_75"
        if pair == "AUDUSD": return "R_100"
        return "R_50" 
    return f"frx{pair}"

# Funzione resa 100% sicura: restituisce SEMPRE due valori (dati, sorgente)
def get_candles(pair, timeframe_sec, count):
    try:
        ws = websocket.create_connection(f"wss://ws.binaryws.com/websockets/v3?app_id={DERIV_APP_ID}", timeout=5)
        req = {
            "ticks_history": to_deriv_symbol(pair),
            "end": "latest",
            "count": count,
            "style": "candles",
            "granularity": timeframe_sec
        }
        ws.send(json.dumps(req))
        res = json.loads(ws.recv())
        ws.close()
        
        if 'candles' in res:
            candles = []
            for c in res['candles']:
                dt = datetime.fromtimestamp(c['epoch'], fuso_roma)
                candles.append({
                    'time': dt.strftime("%H:%M:%S"), 
                    'open': c['open'], 'max': c['high'],
                    'min': c['low'], 'close': c['close']
                })
            return candles, "DERIV.COM 🔵"
        return None, "Dati non disponibili"
    except Exception as e: 
        return None, f"Errore: {str(e)}"

def get_deriv_balance(token):
    try:
        ws = websocket.create_connection(f"wss://ws.binaryws.com/websockets/v3?app_id={DERIV_APP_ID}", timeout=10)
        ws.send(json.dumps({"authorize": token}))
        res = json.loads(ws.recv())
        if "error" in res:
            ws.close()
            return None
        ws.send(json.dumps({"balance": 1}))
        res_bal = json.loads(ws.recv())
        ws.close()
        return res_bal['balance']['balance']
    except:
        return None

def check_consecutive_candles(df, count=3):
    if len(df) < count: return False
    last_candles = df.tail(count)
    all_green = all(last_candles['close'] > last_candles['open'])
    all_red = all(last_candles['close'] < last_candles['open'])
    return all_green or all_red

def genera_trade_id():
    return f"ID-{int(datetime.now().timestamp()) % 1000000}"

def get_market_status():
    fuso_roma = pytz.timezone('Europe/Rome')
    now_time = datetime.now(fuso_roma).time()
    
    # Definiamo i range
    tokyo = (time(0,0), time(9,0))
    londra = (time(9,0), time(18,0))
    new_york = (time(14,0), time(23,0))
    
    if is_weekend_reale: 
        return "⚠️ **WEEKEND OTC**"
    
    # Controllo Overlap (Alta Volatilità)
    if (londra[0] <= now_time <= londra[1]) and (new_york[0] <= now_time <= new_york[1]):
        return "🔥 **OVERLAP EU+USA**\n\nAlta Volatilità"
    
    # Sessioni Singole
    if londra[0] <= now_time <= londra[1]: 
        return "🇪🇺 **SESSIONE LONDRA**"
    if new_york[0] <= now_time <= new_york[1]: 
        return "🇺🇸 **SESSIONE NEW YORK**"
    if tokyo[0] <= now_time <= tokyo[1]: 
        return "🐌 **SESSIONE ASIATICA (TOKYO+SIDNEY)**"
    
    # Se non è nessuna delle precedenti (es. tra le 23:00 e le 00:00)
    return "💤 **MERCATI CHIUSI**"

def draw_market_map_inverted(trading_autorizzato):
    fig = go.Figure()
    tz_roma = pytz.timezone('Europe/Rome')
    now_roma = datetime.now(tz_roma)
    x_pos = float(now_roma.hour + (now_roma.minute / 60.0))

    try: bg_image = Image.open("mondo.png")
    except: 
        try: bg_image = Image.open("banner2.png")
        except: bg_image = None

    if bg_image:
        fig.add_layout_image(dict(source=bg_image, xref="x", yref="y", x=24, y=4.5, sizex=24, sizey=4.5, sizing="stretch", opacity=1.0, layer="below"))

    color_laser = "#FFD700" if trading_autorizzato else "#0F3ADA"
    fig.add_shape(type="line", x0=x_pos, x1=x_pos, y0=0, y1=4.5, line=dict(color=color_laser, width=3))
    fig.update_layout(xaxis=dict(range=[24, 0], showgrid=False, visible=False, fixedrange=True), yaxis=dict(range=[0, 4.5], showgrid=False, visible=False, fixedrange=True), template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=0, b=0), height=350)
    return fig

def get_daily_economic_alerts():
    """Restituisce avvisi basati sulle finestre di rilascio dati macro standard"""
    now = datetime.now(fuso_roma)
    ora_min = now.strftime("%H:%M")
    
    alerts = []
    
    # Esempi di orari standard per news ad alto impatto (Red Flags)
    # In un'evoluzione futura, qui leggeremo un file JSON o un'API
    news_events = [
        {"ora": "14:30", "evento": "🇺🇸 Non-Farm Payrolls / CPI (USA)", "impatto": "ALTO"},
        {"ora": "16:00", "evento": "🇺🇸 Indici ISM / Fiducia Consumatori", "impatto": "MEDIO"},
        {"ora": "20:00", "evento": "🇺🇸 FOMC / Decisioni Tassi FED", "impatto": "CRITICO"}
    ]
    
    for event in news_events:
        # Se l'evento è previsto per oggi
        alerts.append(f"⚠️ **Ore {event['ora']}**: {event['evento']} - Impatto: {event['impatto']}")
    
    return alerts

def send_morning_report():
    history = load_journal()
    if not history:
        return "Buongiorno! ☕️ Nessun trade registrato ieri."

    df = pd.DataFrame(history)
    # Convertiamo la colonna tempo per filtrare i dati di "ieri"
    df['time'] = pd.to_datetime(df['time'])
    ieri = (datetime.now(fuso_roma) - timedelta(days=1)).date()
    df_ieri = df[df['time'].dt.date == ieri]

    if df_ieri.empty:
        msg = f"☀️ **MORNING REPORT ({ieri})**\n\nIeri non sono stati eseguiti trade. Lo scanner era spento o i parametri troppo stretti."
    else:
        wins = df_ieri['result'].astype(str).str.contains("WIN").sum()
        losses = df_ieri['result'].astype(str).str.contains("LOSS").sum()
        pnl = df_ieri['pnl_numeric'].sum()
        wr = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        
        msg = (
            f"☀️ **MORNING REPORT ({ieri})**\n\n"
            f"📊 **Performance di Ieri:**\n"
            f"✅ Win: {wins} | ❌ Loss: {losses}\n"
            f"🏁 Win Rate: {wr:.1f}%\n"
            f"💰 P&L Totale: {pnl:.2f}€\n\n"
            f"📅 **News Critiche di Oggi:**\n"
        )
        
        # Aggiungiamo le news della funzione precedente
        news = get_daily_economic_alerts()
        for n in news:
            msg += f"{n}\n"
            
    msg += "\n🚀 *Sistema pronto. Avviare lo scanner dalla dashboard?*"
    invia_telegram(msg)

def invia_telegram(messaggio):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": messaggio, "parse_mode": "Markdown"}, timeout=5)
    except: pass

def send_telegram_signal(signal_type, pair, price, rsi, trade_id, stake, tipo_mercato): 
    timestamp = datetime.now(fuso_roma).strftime("%H:%M:%S")
    
    # Aggiungi questo piccolo dizionario di mappatura per il messaggio
    mapping_nomi = {"EURUSD": "V50", "USDJPY": "V75", "AUDUSD": "V100"}
    nome_reale = mapping_nomi.get(pair, pair)

    message = (
        f"🚀 *NUOVO TRADE*\n🔔 *Segnale:* {signal_type}\n🆔 ID: `{trade_id}`\n"
        f"💱 Asset: {pair}\n" 
        f"🌍 Market: {tipo_mercato}\n💵 Stake: `{stake:.0f} €` \n" 
        f"💰 Prezzo: `{price:.5f}`\n📈 RSI: `{rsi:.1f}`\n⏰ Ora: {timestamp}"
    )
    invia_telegram(message)

JOURNAL_FILE = "trading_journal.json"

def load_journal():
    if os.path.exists(JOURNAL_FILE):
        try:
            with open(JOURNAL_FILE, "r") as f: return json.load(f)
        except: return []
    return []

def save_journal(history):
    with open(JOURNAL_FILE, "w") as f: json.dump(history, f)

def style_pnl(val):
    try:
        num_val = float(str(val).replace('€', '').replace(' ', '').strip())
        if num_val > 0: return 'color: #32cd32; font-weight: bold;'
        elif num_val < 0: return 'color: #ff4b4b; font-weight: bold;'
    except: pass
    return 'color: white;' 

def style_result(val):
    val_str = str(val)
    if "✅" in val_str or "WIN" in val_str: return 'color: #32cd32; font-weight: bold;'
    elif "❌" in val_str or "LOSS" in val_str: return 'color: #ff4b4b; font-weight: bold;'
    elif "⏳" in val_str: return 'color: #bf8801; font-style: bold;'
    return ''

def play_trade_sound(sound_type="buy"):
    sounds = {"buy": "https://actions.google.com/sounds/v1/alarms/beep_short.ogg", "win": "https://actions.google.com/sounds/v1/cartoon/clink_vibrant.ogg"}
    placeholder = st.empty()
    try:
        with placeholder: st.audio(sounds.get(sound_type, sounds["buy"]), autoplay=True)
        time_module.sleep(2.0)
    except: pass
    placeholder.empty()

def get_mini_chart_data(symbol, tf_id):
    """Scarica dati assicurandosi di accedere correttamente al modulo mt5"""
    if not MT5_AVAILABLE: return None
    import MetaTrader5 as m5
    if not m5.initialize(): return None
    try:
        rates = m5.copy_rates_from_pos(symbol, tf_id, 0, 50)
        if rates is None or len(rates) == 0: return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df
    except: return None

# --- 2. SETUP STREAMLIT E SESSIONE ---
st.set_page_config(page_title="Sentinel AI", page_icon="🚀", layout="wide")
st.markdown("""<style>[data-testid="stAppViewContainer"] * { transition: none !important; } div[data-testid="stVerticalBlock"] { opacity: 1 !important; }</style>""", unsafe_allow_html=True)

try: st.image(Image.open("banner.png"), use_column_width=True)
except: st.image("https://via.placeholder.com/800x100/ff4b4b/white?text=SENTINEL+AI", use_column_width=True)

if 'connected' not in st.session_state: st.session_state.connected = False
if 'connection_source' not in st.session_state: st.session_state.connection_source = "Nessuna"
if 'active_trades' not in st.session_state: st.session_state.active_trades = {}
if 'signal_history' not in st.session_state: st.session_state.signal_history = load_journal()
if 'local_balance' not in st.session_state: st.session_state.local_balance = 10000.0
if 'scanner_on' not in st.session_state: st.session_state.scanner_on = False
if 'weekend_mode' not in st.session_state: st.session_state.weekend_mode = is_weekend_reale 
if 'session_pnl' not in st.session_state: st.session_state.session_pnl = 0.0
if 'last_trade_time' not in st.session_state: st.session_state.last_trade_time = 0
if 'cooldown_minutes' not in st.session_state: st.session_state.cooldown_minutes = 5
if 'report_sent' not in st.session_state: st.session_state.report_sent = False

# Trigger per il Morning Report (viene eseguito la prima volta che apri la dashboard tra le 08:30 e le 09:30)
ora_attuale_report = now_roma.time()
if time(8, 30) <= ora_attuale_report <= time(9, 30) and not st.session_state.report_sent:
    send_morning_report()
    st.session_state.report_sent = True

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("⚙️ AI TRADING")
    
    if not st.session_state.connected:
        if st.button("🔌 CONNETTI SISTEMA", use_container_width=True, type="primary"):
            with st.spinner("Ricerca connessione disponibile..."):
                # FIX: Testiamo R_50 che è sempre aperto 24/7/365
                test_data, source = get_candles("R_50", 60, 1) 
                if test_data:
                    st.session_state.connected = True
                    st.session_state.connection_source = source
                    st.rerun()
                else: st.error("Nessuna sorgente dati disponibile.")
    else:
        st.success(f"Connesso a: **DERIV.COM 🔵**")
        if st.button("🔴 DISCONNETTI", use_container_width=True):
            st.session_state.connected = False
            st.session_state.scanner_on = False
            st.rerun()

        st.divider()
        st.subheader("👁️ SCANSIONE FOREX")
        label = "🛑 STOP SCANNER" if st.session_state.scanner_on else "🚀 **AVVIA SCANNER**"
        if st.button(label, use_container_width=True, type="primary"):
            st.session_state.scanner_on = not st.session_state.scanner_on
            st.rerun()
            
        if st.session_state.scanner_on:
            st.caption(f"🔄 Scanner attivo...  \nUltimo check: {now_roma.time().strftime('%H:%M:%S')}")

        #st.divider()
        #st.subheader("🛡️ PROTEZIONE ACCOUNT")
        #stop_loss_limit = st.number_input("Stop Loss Sessione (€)", value=400.0, step=10.0)
        #take_profit_limit = st.number_input("Take Profit Sessione (€)", value=1000.0, step=10.0)
        
        #if st.session_state.scanner_on:
            # Controllo automatico: se la perdita supera il limite, spegne tutto
            #if st.session_state.session_pnl <= -stop_loss_limit:
                #st.session_state.scanner_on = False
                #invia_telegram(f"⚠️ **STOP LOSS RAGGIUNTO!**\nPerdita: {st.session_state.session_pnl:.2f}€\nScanner disattivato per sicurezza.")
                #st.error("STOP LOSS RAGGIUNTO. Scanner spento.")
            
            #if st.session_state.session_pnl >= take_profit_limit:
                #st.session_state.scanner_on = False
                #invia_telegram(f"💰 **TAKE PROFIT RAGGIUNTO!**\nProfitto: {st.session_state.session_pnl:.2f}€\nOttima sessione!")
                #st.success("TAKE PROFIT RAGGIUNTO. Scanner spento.")
        

        
        st.divider()
        st.subheader("🌍 TIPO DI MERCATO")

        # Verifica se siamo in orario Overlap (14:30 - 17:30)
        ora_attuale_time = now_roma.time()
        is_overlap_time = time(14, 30) <= ora_attuale_time <= time(17, 30) and not st.session_state.weekend_mode

        if st.session_state.weekend_mode:
            st.success("🚨 **OTC (Sab-Dom)**")
            use_bb, use_rsi = True, True
            bb_period, bb_std = 20, 2.20
            custom_rsi_buy, custom_rsi_sell = 20, 80
        
        elif is_overlap_time:
            # --- PARAMETRI AUTOMATICI OVERLAP ---
            st.warning("⚠️ **LIVE OVERLAP ATTIVA (Lun-Ven)**\n\nParametri di sicurezza inseriti automaticamente.")
            st.info("📏 BB: 20 / 2.50\n📉 RSI: 15 / 85")
            use_bb, use_rsi = True, True
            bb_period, bb_std = 20, 2.50
            custom_rsi_buy, custom_rsi_sell = 15, 85
        
        else:
            st.success("🟢 **LIVE (Lun-Ven)**")
            use_bb, use_rsi = True, True
            bb_period = 20
            custom_rsi_buy, custom_rsi_sell = 20, 80
            bb_std = st.selectbox("📏 Deviazione BB", [2.20, 2.30, 2.35, 2.40, 2.50], index=1)

        st.divider()
        st.subheader("🏛️ SESSIONI DI MERCATO")
        for city, (start, end) in {"🇬🇧 LONDRA:": (time(9,0), time(18,0)), "🇺🇸 NEW YORK:": (time(14,0), time(23,0)), "🇦🇺 SYDNEY:": (time(0,0), time(8,0)), "🇯🇵 TOKYO:": (time(0,0), time(9,0))}.items():
            status = "Open 🟢" if not is_weekend_reale and start <= now_cet <= end else "Closed 🔴"
            st.write(f"{city} {status}")
            
        #st.info(get_market_status())
        # Nella sidebar
        status_testo = get_market_status()
        st.info(status_testo if status_testo else "Recupero informazioni mercato...")

        #st.markdown("---")
        #st.subheader("💸 PROTEZIONE OVERLAP LONDRA-NY")
        # Il toggle rimane per fermare tutto manualmente se non ti fidi della volatilità
        #pausa_overlap = st.toggle("🛑 **Stop Totale Overlap**", value=False, help="Spegne lo scanner dalle 14:30 alle 17:30")
        
        # Logica di autorizzazione trading
        #trading_autorizzato = True
        #if is_overlap_time and pausa_manuale_overlap:
            #trading_autorizzato = False

        st.divider()
        st.subheader("🛠️ PARAMETRI TRADING")
        st.session_state.stake = st.number_input("💶 INVESTIMENTO (€)", value=100.0)
        timeframe = st.selectbox("⏱️ TIMEFRAME (s)", [60, 120], index=0)

        st.divider()
        st.subheader("🖥️ TEST DASHBOARD")
        
        if st.button("🔔 **TEST AUDIO & TELEGRAM**", use_container_width=True):
            play_trade_sound("buy")
            invia_telegram("✅ **SENTINEL AI: SYSTEM CHECK**\nBot online e pronto 🚀")
            st.toast("Test completato!", icon="📲")

        if st.button("🗑️ **PULISCI SEGNALI**", use_container_width=True):
            st.session_state.signal_history = []
            st.session_state.session_pnl = 0.0  # <--- AGGIUNGI QUESTA RIGA
            st.session_state.local_balance = 10000.0 # <--- RESETTA IL BILANCIO VIRTUALE
            save_journal([]) 
            st.success("Memoria pulita e PNL resettato!")
            time_module.sleep(1)
            st.rerun()

        stress_test = st.toggle("🚀 **STRESS MODE**", value=False)
        if stress_test:
            st.warning("⚠️ **Modalità TEST:**\n\nno BB - RSI (45/55)")
            use_bb, use_rsi = False, True
            custom_rsi_buy, custom_rsi_sell = 45, 55
     
        st.divider()
        st.header("💾 GESTIONE SEGNALI")
        if st.session_state.signal_history:
            df_export = pd.DataFrame(st.session_state.signal_history)
            csv_data = df_export.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 ESPORTA STORICO (CSV)", data=csv_data, file_name=f"sentinel_history_{now_roma.time().strftime('%d%m%Y_%H%M')}.csv", mime="text/csv", use_container_width=True)
        else:
            st.button("📥 ESPORTA STORICO (CSV)", disabled=True, use_container_width=True)

        uploaded_file = st.file_uploader("📤 IMPORTA DATI", type=["csv"], label_visibility="collapsed")
        if uploaded_file is not None:
            if st.button("🔄 CARICA DATI", use_container_width=True, type="secondary"):
                try:
                    df_import = pd.read_csv(uploaded_file)
                    st.session_state.signal_history.extend(df_import.to_dict('records'))
                    df_pulito = pd.DataFrame(st.session_state.signal_history).drop_duplicates(subset=['time', 'pair'], keep='last')
                    st.session_state.signal_history = df_pulito.to_dict('records')
                    save_journal(st.session_state.signal_history) 
                    st.success("✅ Storico caricato con successo!")
                    time_module.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"⚠️ Errore nel file: {e}")

        st.divider()

# --- 4. MAIN DASHBOARD ---
if st.session_state.connected:
    ora_attuale_time = now_roma.time()
    
    # 🌙 Definizione Orario Notturno (00:00 - 07:00)
    is_night_session = time(0, 0) <= ora_attuale_time < time(7, 0)

    # Applica i set di valute in base a orario e giorno
    if st.session_state.weekend_mode:
        CURRENT_PAIRS = ["EURUSD", "USDJPY", "AUDUSD"] # Mappati su V50, V75, V100
    else:
        if is_night_session:
            # NOTTE: Solo le valute attive in Asia/Oceania per evitare derive senza volumi
            CURRENT_PAIRS = ["AUDUSD", "USDJPY"]
        else:
            # GIORNO LIVE: Le 4 valute super liquide standard
            CURRENT_PAIRS = ["EURUSD", "AUDUSD", "USDCHF", "USDCAD"]
        
    window_1 = (time(0, 0), time(12, 0))
    window_2 = (time(12, 0), time(23, 0))
    # Il trading è sempre autorizzato di notte ora che abbiamo filtrato le valute sicure
    is_trading_time = (window_1[0] <= now_cet <= window_1[1]) or (window_2[0] <= now_cet <= window_2[1]) or is_night_session
    trading_autorizzato = is_trading_time or stress_test

    # VERIFICA DELLA PAUSA OVERLAP
    in_pausa_overlap = False
    if not st.session_state.weekend_mode and st.session_state.get('pause_overlap', True):
        if time(14, 30) <= ora_attuale_time <= time(17, 30):
            trading_autorizzato = False
            in_pausa_overlap = True

    # --- Nella Main Dashboard, subito dopo il banner ---
    #if st.session_state.scanner_on:
        #daily_news = get_daily_economic_alerts()
        #if daily_news:
            #with st.expander("📅 NOTIZIE ECONOMICHE DEL GIORNO", expanded=True):
                #for alert in daily_news:
                    #st.write(alert)
                #st.caption("Consiglio: Spegnere lo scanner 15 minuti prima e riaccendere 15 minuti dopo questi orari.")

    st.divider()
    st.subheader("🌍 Live Market Flow 24h")
    
    if st.session_state.weekend_mode or is_weekend_reale:
        try: st.image(Image.open("banner2.png"), use_column_width=True, caption="MODALITÀ WEEKEND ATTIVA 🔴 MERCATI CHIUSI")
        except: st.warning("Immagine banner2.png non trovata.")
    else:
        st.plotly_chart(draw_market_map_inverted(trading_autorizzato), use_container_width=True)

    if st.session_state.scanner_on:
        if st.session_state.weekend_mode:
            st.success("SCANNER OTC ATTIVO", icon="🎯")
        else:
            if in_pausa_overlap:
                st.warning("🛑 PAUSA OVERLAP ATTIVA: Scanner in attesa. Riprenderà da solo alle 17:30.")
            elif not trading_autorizzato:
                st.warning("🛡️ PROTEZIONE ATTIVA: Mercato fuori orario. Scanner in pausa.")
            elif is_night_session:
                # NUOVO AVVISO NOTTURNO
                st.info("🌙 **MODALITÀ NOTTURNA (00:00 - 07:00)**\n\nScanner limitato a JPY e AUD per sicurezza.")
            else:
                st.success("SISTEMA LIVE IN SCANSIONE ATTIVA 🔥", icon="📡")
        
        st.divider()
        st.subheader("🕵️ Coppie di valute osservate")
        cols = st.columns(5)
        for i, pair in enumerate(CURRENT_PAIRS):
            with cols[i % 5]: st.code(f"{icons.get(pair, '🔍')} {pair}")

        for pair in CURRENT_PAIRS:
            try:
                candles, source = get_candles(pair, timeframe, 100) 
                if not candles or len(candles) < 20: continue
                
                df = pd.DataFrame(candles)

                if st.session_state.weekend_mode and not stress_test:
                    r_buy, r_sell, b_period, b_std = 20, 80, 20, 2.20
                elif stress_test:
                    r_buy, r_sell, b_period, b_std = 45, 55, 20, 2.20
                else:
                    # Mercato LIVE
                    r_buy, r_sell, b_period, b_std = custom_rsi_buy, custom_rsi_sell, bb_period, bb_std

                df['RSI'] = ta.rsi(df['close'], length=7)
                bb = ta.bbands(df['close'], length=b_period, std=b_std)

                if bb is None or bb.empty: continue

                                # Prezzo attuale per registrare l'ingresso a mercato
                price = df['close'].iloc[-1] 
                
                # Indicatori basati sull'ultima candela CHIUSA (evita il repainting!)
                curr_rsi = df['RSI'].iloc[-2]
                curr_bb_low = float(bb.filter(like='BBL').iloc[-2].iloc[0])
                curr_bb_up = float(bb.filter(like='BBU').iloc[-2].iloc[0])
                chiusura_prec = df['close'].iloc[-2]
                
                cond_rsi_buy = (curr_rsi < r_buy) if use_rsi else True
                cond_bb_buy = (chiusura_prec <= curr_bb_low) if use_bb else True
                cond_rsi_sell = (curr_rsi > r_sell) if use_rsi else True
                cond_bb_sell = (chiusura_prec >= curr_bb_up) if use_bb else True
                
                # Escludi l'ultima candela in corso dal conteggio delle consecutive
                is_consecutive = check_consecutive_candles(df.iloc[:-1], count=3)

                is_buy = (cond_rsi_buy and cond_bb_buy) and (use_rsi or use_bb) and not is_consecutive
                is_sell = (cond_rsi_sell and cond_bb_sell) and (use_rsi or use_bb) and not is_consecutive

                # --- PROTEZIONI ANTI-RAFFICA ---
                current_time = time_module.time()
                trade_attivi_ora = len(st.session_state.active_trades)
                minuti_passati = (current_time - st.session_state.last_trade_time) / 60

                if (is_buy or is_sell) and pair not in st.session_state.active_trades:
                    
                    # FILTRO 1: Massimo 2 trade aperti insieme
                    if trade_attivi_ora >= 2:
                        continue 

                    # FILTRO 2: Almeno 5 minuti tra un'apertura e l'altra
                    if minuti_passati < st.session_state.cooldown_minutes:
                        continue

                    # SE PASSA I FILTRI, PROCEDI
                    direction = "BUY" if is_buy else "SELL"
                    t_id = genera_trade_id()
                    tipo_mercato = "OTC" if st.session_state.weekend_mode else "LIVE"
                    
                    # AGGIORNA IL MOMENTO DELL'ULTIMO TRADE
                    st.session_state.last_trade_time = current_time
                
                    st.session_state.active_trades[pair] = {
                        'id': t_id, 'entry_price': float(price), 'entry_time': current_time, 
                        'direction': direction, 'stake_num': float(st.session_state.stake)
                    }
                    
                    # REGISTRAZIONE NEL JOURNAL
                    st.session_state.signal_history.append({
                        'id': t_id, 'time': datetime.now(fuso_roma).strftime("%Y-%m-%d %H:%M:%S"),
                        'pair': pair, 'dir': direction, 'price': float(price), 
                        'rsi_val': f"{curr_rsi:.1f}",
                        'stake': f"{st.session_state.stake:.0f}€",                         
                        'params_bb': f"{b_period}/{b_std}" if use_bb else "OFF", 
                        'params_rsi': f"{r_buy}/{r_sell}", 
                        'mercato': tipo_mercato, 'result': "⏳ In corso...",
                        'check_120s': "-", 'pnl_numeric': 0.0
                    })

                    save_journal(st.session_state.signal_history)
                    send_telegram_signal(direction, pair, price, curr_rsi, t_id, st.session_state.stake, tipo_mercato)
                    play_trade_sound("buy")

            except Exception as e:
                continue
    
    # --- 5. ANALISI TECNICA GRAFICA ---
    st.divider()
    st.subheader("📈 Analisi Tecnica Principale")
    pair_display = st.selectbox("Seleziona asset per grafico", CURRENT_PAIRS)
    
    df_final = pd.DataFrame()
    
    try:
        candles_ta, src_ta = get_candles(pair_display, timeframe, 160)
            
        if candles_ta:
            st.caption(f"Sorgente dati attuale: **{src_ta}**")
            df_raw = pd.DataFrame(candles_ta)

            df_raw['RSI'] = ta.rsi(df_raw['close'], length=7)

            # Impostazione Base per il Grafico (Indipendente dallo scanner)
            if st.session_state.weekend_mode and not stress_test:
                r_buy_graf, r_sell_graf, b_period_graf, b_std_graf = 20, 80, 20, 2.20
            elif stress_test:
                r_buy_graf, r_sell_graf, b_period_graf, b_std_graf = 45, 55, 20, 2.20
            else:
                # Usa i parametri dinamici della sidebar
                r_buy_graf, r_sell_graf, b_period_graf, b_std_graf = custom_rsi_buy, custom_rsi_sell, bb_period, bb_std

            bb_ta = ta.bbands(df_raw['close'], length=b_period_graf, std=b_std_graf)

            if bb_ta is not None and not bb_ta.empty:
                bb_ta.columns = ['BBL', 'BBM', 'BBU', 'BBB', 'BBP'] 
                df_final = pd.concat([df_raw, bb_ta[['BBL', 'BBM', 'BBU']]], axis=1).tail(100)

                # --- FIX SICUREZZA: Inizializza le colonne come vuote (NaN) ---
                df_final['buy_sig'] = float('nan')
                df_final['sell_sig'] = float('nan')
                df_final['is_consecutive'] = False

                # Calcolo candele consecutive
                is_green = df_final['close'] > df_final['open']
                is_red = df_final['close'] < df_final['open']
                df_final['is_consecutive'] = (is_green.rolling(3).sum() == 3) | (is_red.rolling(3).sum() == 3)

                # Calcolo segnali con lambda (più robusto)
                df_final['buy_sig'] = df_final.apply(lambda x: (x['close'] * 0.9998) if (
                    ((x['RSI'] < r_buy_graf) if use_rsi else True) and 
                    ((x['close'] <= x['BBL']) if use_bb else True) and
                    not x['is_consecutive']
                ) else float('nan'), axis=1)
                
                df_final['sell_sig'] = df_final.apply(lambda x: (x['close'] * 1.0002) if (
                    ((x['RSI'] > r_sell_graf) if use_rsi else True) and 
                    ((x['close'] >= x['BBU']) if use_bb else True) and
                    not x['is_consecutive']
                ) else float('nan'), axis=1)

                #st.write(df_final.columns.tolist())
                
                asse_x = df_final['time']
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.5, 0.25], vertical_spacing=0.07, subplot_titles=("📊 Prezzo & Volatilità", "📉 Oscillatore RSI"))
                fig.add_trace(go.Candlestick(x=asse_x, open=df_final['open'], high=df_final['max'], low=df_final['min'], close=df_final['close'], name="Prezzo"), row=1, col=1)
                fig.add_trace(go.Scatter(x=asse_x, y=df_final['BBU'], line=dict(color='rgba(0,71,171,0.4)', width=1), name="BBU"), row=1, col=1)
                fig.add_trace(go.Scatter(x=asse_x, y=df_final['BBM'], line=dict(color='rgba(170,170,170,0.3)', width=1), name="BBM"), row=1, col=1)
                fig.add_trace(go.Scatter(x=asse_x, y=df_final['BBL'], line=dict(color='rgba(0,71,171,0.4)', width=1), fill='tonexty', fillcolor='rgba(100, 100, 255, 0.05)', name="BBL"), row=1, col=1)
                fig.add_trace(go.Scatter(x=asse_x, y=df_final['RSI'], line=dict(color='#AB63FA'), name="RSI"), row=2, col=1)
                fig.add_hline(y=r_buy_graf, line_color="green", row=2, col=1, line_dash="dash")
                fig.add_hline(y=r_sell_graf, line_color="red", row=2, col=1, line_dash="dash")
                fig.update_layout(xaxis_rangeslider_visible=False, hovermode="x unified", template="plotly_dark", height=600)
                fig.update_xaxes(type='category', tickangle=45, nticks=20, showgrid=True, gridcolor='rgba(130,130,130,0.08)', showspikes=True, spikemode='across', spikecolor="black", spikethickness=1, spikedash="solid")
                fig.add_trace(go.Scatter(x=asse_x, y=df_final['buy_sig'], mode='markers', marker=dict(symbol='triangle-up', size=15, color='#00ff88', line=dict(width=1, color='white')), name="Entry BUY"), row=1, col=1)
                fig.add_trace(go.Scatter(x=asse_x, y=df_final['sell_sig'], mode='markers', marker=dict(symbol='triangle-down', size=15, color='#ff3333', line=dict(width=1, color='white')), name="Entry SELL"), row=1, col=1)
                st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Errore generazione grafico: {e}")

    st.write("---")
    st.subheader(f"📊 Analisi Performance ({timeframe}s)")
    n_buy, n_sell = df_final['buy_sig'].notnull().sum(), df_final['sell_sig'].notnull().sum()
    totale_segnali = n_buy + n_sell

    # --- FIX 2: ETICHETTA BOTTONE DINAMICA ---
    if st.button(f"🔍 **VERIFICA ESITO ({timeframe}s)**", use_container_width=True, type="primary"):
        wins_buy, wins_sell = 0, 0
        for i in range(len(df_final) - 1):
            if pd.notnull(df_final['buy_sig'].iloc[i]) and df_final['close'].iloc[i+1] > df_final['close'].iloc[i]: wins_buy += 1
            if pd.notnull(df_final['sell_sig'].iloc[i]) and df_final['close'].iloc[i+1] < df_final['close'].iloc[i]: wins_sell += 1

        tot_vinti = wins_buy + wins_sell
        tot_persi = totale_segnali - tot_vinti
        accuracy = (tot_vinti / totale_segnali * 100) if totale_segnali > 0 else 0
        bilancio_netto = (tot_vinti * (st.session_state.stake * 0.90)) - (tot_persi * st.session_state.stake)

        c1, c2, c3 = st.columns(3)
        c1.metric("🟢 BUY VINCENTI", f"{wins_buy} / {n_buy}")
        c2.metric("🔴 SELL VINCENTI", f"{wins_sell} / {n_sell}")
        c3.metric("🎯 ACCURACY", f"{accuracy:.1f}%")
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
        st.info("Regola i parametri e verifica il profitto")
    
    # --- 6. VERIFICA ESITI TRADE CON DERIV ---
    current_ts = time_module.time() 
    trades_pendenti = list(st.session_state.active_trades.items())

    for pair, trade in trades_pendenti:
        attesa_reale = max(timeframe, 120) 
        scadenza = trade['entry_time'] + attesa_reale + 2 # 2 secondi di buffer

        if current_ts >= scadenza:
            try:
                res, _ = get_candles(pair, timeframe, 6)
                if res and len(res) >= 4:
                    entry_price = trade['entry_price']
                    dir_trade, t_id = trade['direction'], trade['id']
                    
                    # Calcolo prezzi di uscita
                    exit_60 = res[-3]['close'] if timeframe == 60 else res[-2]['close']
                    exit_120 = res[-2]['close']
                    
                    # Calcolo esiti
                    win_60 = (exit_60 > entry_price) if dir_trade == "BUY" else (exit_60 < entry_price)
                    win_120 = (exit_120 > entry_price) if dir_trade == "BUY" else (exit_120 < entry_price)
                    
                    # Definiamo le variabili mancanti per il tuo messaggio Telegram
                    win = win_60 if timeframe == 60 else win_120 
                    res_status = "WIN" if win else "LOSS"
                    icona_esito = "✅" if win else "❌"
                    profit = (trade['stake_num'] * 0.90) if (res_status == "WIN") else -trade['stake_num']

                    # AGGIORNAMENTO STORICO
                    for s in st.session_state.signal_history:
                        if s.get('id') == t_id and s.get('result') == "⏳ In corso...":
                            s['result'] = f"{'✅' if win_60 else '❌'} {res_status}"
                            s['check_120s'] = f"{'✅' if win_120 else '❌'} {'WIN' if win_120 else 'LOSS'}"
                            s['pnl_numeric'] = float(profit)
                            
                            # Definiamo rsi_ingresso prendendolo dallo storico salvato
                            rsi_ingresso = s.get('rsi_val', 'N/D')
                            
                            # Aggiorniamo il PNL di sessione
                            st.session_state.session_pnl += profit

                            save_journal(st.session_state.signal_history)

                            # Creiamo la stringa formattata per l'esito a 120s
                            esito_120s = f"{'✅' if win_120 else '❌'} {'WIN' if win_120 else 'LOSS'}"
                            
                            mapping_nomi = {"EURUSD": "V50", "USDJPY": "V75", "AUDUSD": "V100"}
                            nome_reale = mapping_nomi.get(pair, pair)
                            tipo_mercato = "OTC" if st.session_state.weekend_mode else "LIVE"
                            
                            msg = (f"🏁 *ESITO* {'💰' if win else '💀'} {res_status}\n"
                                   f"🆔 ID: `{t_id}`\n"
                                   f"💱 Asset: {pair}\n"
                                   f"🌍 Market: {tipo_mercato}\n"
                                   f"📈 RSI Ingresso: `{rsi_ingresso}`\n"
                                   f"📉 Esito 60s: {icona_esito} {res_status}\n"
                                   f"💵 P&L 60s: `{profit:.2f}€`\n"
                                   f"📉 Esito 120s: {esito_120s}\n"
                                   f"📅 P&L Sessione 60s: `{st.session_state.session_pnl:.2f}€` ")
                            invia_telegram(msg)

                            if res_status == "WIN": play_trade_sound("win")
                            
                            # Pulizia e Refresh
                            if pair in st.session_state.active_trades:
                                del st.session_state.active_trades[pair]
                            #st.rerun()
            except Exception as e:
                continue
                    
    st.divider()

    # --- 7. TABELLA JOURNAL E FILTRI DINAMICI ---
    st.subheader("📋 Trading Journal & Performance Hub")

    if st.session_state.signal_history:
        df_journal = pd.DataFrame(st.session_state.signal_history)
        # Assicura che TUTTE le colonne critiche esistano sempre nel DataFrame
        colonne_critiche = ['result', 'check_120s', 'rsi_val', 'pnl_numeric']
        for col in colonne_critiche:
            if col not in df_journal.columns:
                # Imposta 0.0 per il PNL numerico, "-" per le stringhe
                df_journal[col] = 0.0 if col == 'pnl_numeric' else "-"
    else:
        # DataFrame vuoto con tutte le colonne necessarie
        df_journal = pd.DataFrame(columns=['id', 'time', 'pair', 'dir', 'price', 'rsi_val', 'stake', 'params_bb', 'params_rsi', 'mercato', 'result', 'check_120s', 'pnl_numeric'])

    df_journal['pnl_numeric'] = pd.to_numeric(df_journal.get('pnl_numeric', 0.0), errors='coerce').fillna(0.0)

    # Inizializza 'remaining' a 0 per evitare l'errore alla riga 710
    remaining = 0.0 

    # --- MONITOR COOLDOWN ---
    if st.session_state.scanner_on:
        current_time = time_module.time()
        elapsed = (current_time - st.session_state.last_trade_time) / 60
        remaining = max(0.0, st.session_state.cooldown_minutes - elapsed)
        
    if remaining > 0:
        st.warning(f"⏳ Pausa Sicurezza: {remaining:.1f} min")
    else:
        st.success("✅ Sistema pronto per segnali")

    if st.session_state.scanner_on:
        st.caption(f"🔄 Scanner attivo... Ultimo check: {now_roma.time().strftime('%H:%M:%S')}")

    st.markdown("<hr style='border:1px dashed #555; margin: 10px 0; opacity: 0.5;'>", unsafe_allow_html=True)

    f1, f2, f3, f4 = st.columns(4)
    with f1: filtro_mercato = st.selectbox("🌍 Mercato:", ["TUTTI", "OTC", "LIVE"], index=0)
    with f2: filtro_coppia = st.selectbox("💱 Coppia di valute:", ["TUTTE"] + ALL_PAIRS, index=0)
    with f3: time_start = st.time_input("🟢 Orario Inizio:", value=time(0, 0))
    with f4: time_end = st.time_input("🛑 Orario Fine:", value=time(23, 59))
    st.markdown('<hr style="border: none; border-top: 2px dashed #555; margin: 15px 0; opacity: 0.4;">', unsafe_allow_html=True)

    df_filtered = df_journal.copy()
    if not df_filtered.empty:
        if filtro_mercato != "TUTTI": df_filtered = df_filtered[df_filtered['mercato'].astype(str).str.contains(filtro_mercato, na=False)]
        if filtro_coppia != "TUTTE": df_filtered = df_filtered[df_filtered['pair'] == filtro_coppia]
        try:
            orari_df = pd.to_datetime(df_filtered['time']).dt.time
            df_filtered = df_filtered[(orari_df >= time_start) & (orari_df <= time_end)]
        except Exception: pass 

    total_trades = len(df_filtered)
    
    best_pairs_str, best_pairs_str_120 = "-", "-"
    wins, losses, wins_120, losses_120 = 0, 0, 0, 0
    total_pnl_60, total_pnl_120 = 0.0, 0.0
    
    if total_trades > 0:
        # Conta i WIN/LOSS basandosi sulle stringhe salvate
        wins = df_filtered['result'].astype(str).str.contains("WIN").sum()
        losses = df_filtered['result'].astype(str).str.contains("LOSS").sum()
        wins_120 = df_filtered['check_120s'].astype(str).str.contains("✅").sum()
        losses_120 = df_filtered['check_120s'].astype(str).str.contains("❌").sum()
        
        # PNL Reale 60s
        total_pnl_60 = df_filtered['pnl_numeric'].sum()
        
        stake_rif = float(st.session_state.stake)
        # PNL Totale 120s (Payout 90%)
        total_pnl_120 = (wins_120 * (stake_rif * 0.90)) - (losses_120 * stake_rif)

        # Calcolo Profitto Asset 60s
        profit_by_pair = df_filtered.groupby('pair')['pnl_numeric'].sum()
        
        # CREIAMO IL PNL PER SINGOLO ASSET A 120s
        def calc_pnl_120(row):
            val = str(row['check_120s'])
            if "✅" in val: return stake_rif * 0.90
            if "❌" in val: return -stake_rif
            return 0.0
            
        df_filtered['pnl_120_tmp'] = df_filtered.apply(calc_pnl_120, axis=1)
        profit_by_pair_120 = df_filtered.groupby('pair')['pnl_120_tmp'].sum()
        
        # Estrapolazione Top Asset (Aggiunto controllo > 0 per evitare di premiare asset in perdita)
        best_pairs_str = ", ".join(profit_by_pair[profit_by_pair == profit_by_pair.max()].index.tolist()) if not profit_by_pair.empty and profit_by_pair.max() > 0 else "-"
        best_pairs_str_120 = ", ".join(profit_by_pair_120[profit_by_pair_120 == profit_by_pair_120.max()].index.tolist()) if not profit_by_pair_120.empty and profit_by_pair_120.max() > 0 else "-"

    win_rate_60 = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0.0
    win_rate_120 = (wins_120 / (wins_120 + losses_120) * 100) if (wins_120 + losses_120) > 0 else 0.0
    
    # --- RIGA 1: Metriche 60s ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🎯 W/L 60s", f"{wins}W - {losses}L")
    c2.metric("💰 P&L 60s", f"{total_pnl_60:.2f} €")
    c3.metric("🏁 Win Rate 60s", f"{win_rate_60:.1f}%")
    c4.metric("🏆 Top Asset 60s", best_pairs_str)

    st.markdown("<hr style='border:1px dashed #555; margin: 10px 0; opacity: 0.5;'>", unsafe_allow_html=True)

    # --- RIGA 2: Metriche 120s ---
    d1, d2, d3, d4 = st.columns(4) # Importante chiamarle in modo diverso (es. d1, d2...)
    d1.metric("🎯 W/L 120s", f"{wins_120}W - {losses_120}L")
    d2.metric("💰 P&L 120s", f"{total_pnl_120:.2f} €")
    d3.metric("🏁 Win Rate 120s", f"{win_rate_120:.1f}%")
    d4.metric("🏆 Top Asset 120s", best_pairs_str_120)

   
    if not df_filtered.empty:
        rename_map = {'id': '🆔 ID', 'time': '⏰ DATA', 'pair': '💱 VALUTE', 'dir': '🚀 TIPO', 'price': '💰 PRICE', 'rsi_val': '📈 RSI IN', 'stake': '💶 STAKE', 'params_bb': '↔️ BB', 'params_rsi': '📉 RSI', 'mercato': '🌍 MARKET', 'result': '🎯 60s', 'check_120s': '⏱️ 120s', 'pnl_numeric': '📈 P&L'}

        # Lista colonne aggiornata con rsi_val
        cols_to_use = ['id', 'time', 'pair', 'dir', 'price', 'rsi_val', 'stake', 'params_bb', 'params_rsi', 'mercato', 'result', 'check_120s', 'pnl_numeric']
        
        df_display = df_filtered.iloc[::-1].copy()[[c for c in cols_to_use if c in df_filtered.columns]].rename(columns=rename_map)
        
        df_display['📈 P&L'] = df_display['📈 P&L'].apply(lambda x: f"{x:.1f}€" if x % 1 != 0 else f"{x:.0f}€")
        try:
            colonne_esito = [c for c in ['🔍 60s', '⏱️ 75s', '⏱️ 120s'] if c in df_display.columns]
            st.dataframe(df_display.style.applymap(style_result, subset=colonne_esito).applymap(style_pnl, subset=['📈 P&L']), use_container_width=True, hide_index=True)
        except Exception:
            st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("⏳ Avvia lo Scanner e attendi il primo segnale...")
    
    # --- 8. TRI CHART MONITOR (R_50, R_75, R_100) ---
    if st.session_state.weekend_mode:
        st.markdown("---")
        st.subheader("🖥️ Monitor Asset Globali (OTC)")
        m_cols = st.columns(3)
        
        # FIX: Usiamo le coppie fittizie, così get_candles capisce in automatico che deve scaricare R_50, R_75 e R_100
        indices = [("Volatility 50", "EURUSD"), ("Volatility 75", "USDJPY"), ("Volatility 100", "AUDUSD")]
        
        for i, (name, pair) in enumerate(indices):
            with m_cols[i]:
                st.caption(f"📈 {name}")
                # Usiamo i WebSocket di Deriv invece di MT5
                candles, _ = get_candles(pair, 60, 40)
                if candles:
                    df = pd.DataFrame(candles)
                    fig = go.Figure(data=[go.Candlestick(x=df['time'], open=df['open'], high=df['max'], low=df['min'], close=df['close'])])
                    fig.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0), xaxis_rangeslider_visible=False, template="plotly_dark")
                    st.plotly_chart(fig, use_container_width=True, key=f"mini_{pair}")
                else:
                    st.warning("In attesa di dati...")
    
    if st.session_state.scanner_on:
        time_module.sleep(5) 
        st.rerun()
