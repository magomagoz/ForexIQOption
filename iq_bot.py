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
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")
DERIV_TOKEN = st.secrets.get("DERIV_TOKEN", "") 
DERIV_APP_ID = "71759" 

ALL_PAIRS = ["EURUSD", "AUDUSD", "USDCAD", "USDCHF", "USDJPY", "NZDUSD", "EURGBP", "GBPUSD", "EURJPY"]

icons = {
    "EURUSD": "🇪🇺🇺🇸", "AUDUSD": "🇦🇺🇺🇸", "USDCAD": "🇺🇸🇨🇦", 
    "USDCHF": "🇺🇸🇨🇭", "USDJPY": "🇺🇸🇯🇵", "NZDUSD": "🇳🇿🇺🇸", 
    "EURGBP": "🇪🇺🇬🇧", "GBPUSD": "🇬🇧🇺🇸", "EURJPY": "🇪🇺🇯🇵"
}

fuso_roma = pytz.timezone('Europe/Rome')
now_roma = datetime.now(fuso_roma)
giorno_settimana = now_roma.weekday() 
is_weekend_reale = giorno_settimana >= 5  
now_cet = now_roma.time()
ora_attuale = now_roma.hour

def to_deriv_symbol(pair):
    if pair.startswith("R_"): return pair 
    is_otc = st.session_state.get('weekend_mode', is_weekend_reale)
    if is_otc:
        if pair == "EURUSD": return "R_50"
        if pair == "USDJPY": return "R_75"
        if pair == "AUDUSD": return "R_100"
        return "R_50" 
    return f"frx{pair}"

SQUADRA_FOREX = [
    "frxEURUSD",
    "frxGBPUSD",
    "frxUSDJPY" 
]

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
    tokyo = (time(0,0), time(9,0))
    londra = (time(9,0), time(17,30))
    new_york = (time(14,30), time(23,0))
    
    if is_weekend_reale: 
        return "⚠️ **WEEKEND OTC**"
    if (londra[0] <= now_time <= londra[1]) and (new_york[0] <= now_time <= new_york[1]):
        return "🔥 **OVERLAP EU+USA**\n\nAlta Volatilità"
    if londra[0] <= now_time <= londra[1]: 
        return "🇪🇺 **SESSIONE LONDRA**"
    if new_york[0] <= now_time <= new_york[1]: 
        return "🇺🇸 **SESSIONE NEW YORK**"
    if tokyo[0] <= now_time <= tokyo[1]: 
        return "🐌 **SESSIONE ASIATICA (TOKYO+SIDNEY)**"
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

def send_morning_report():
    history = load_journal()
    if not history:
        return "Buongiorno! ☕️ Nessun trade registrato ieri."

    df = pd.DataFrame(history)
    df['time'] = pd.to_datetime(df['time'])
    ieri = (datetime.now(fuso_roma) - timedelta(days=1)).date()
    df_ieri = df[df['time'].dt.date == ieri]

    if df_ieri.empty:
        msg = f"☀️ **MORNING REPORT ({ieri})**"
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
        )
        try:
            news = get_daily_economic_alerts()
            for n in news:
                msg += f"{n}\n"
        except: pass
            
    invia_telegram(msg)

def invia_telegram(messaggio):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": messaggio, "parse_mode": "Markdown"}, timeout=5)
    except: pass

def send_telegram_signal(signal_type, pair, price, rsi, trade_id, stake, tipo_mercato): 
    timestamp = datetime.now(fuso_roma).strftime("%H:%M:%S")
    mapping_nomi = {"EURUSD": "V50", "USDJPY": "V75", "AUDUSD": "V100"}
    nome_reale = mapping_nomi.get(pair, pair)
    
    message = (
        f"🚀 *NUOVO TRADE*\n🔔 *Segnale:* {signal_type}\n🆔 ID: `{trade_id}`\n"
        f"💱 Asset: {pair.replace('frx', '')}\n" 
        f"🌍 Market: {tipo_mercato}\n💵 Stake: `{stake:.0f} €` \n" 
        f"💰 Prezzo: `{price:.5f}`\n📈 RSI Ingresso: `{rsi:.1f}`\n⏰ Ora: {timestamp}"
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
    buy_sound = "https://actions.google.com/sounds/v1/alarms/beep_short.ogg"
    sell_sound = "https://actions.google.com/sounds/v1/water/wood_block_drop.ogg"
    win_sound = "https://actions.google.com/sounds/v1/cartoon/clink_vibrant.ogg"

    sound_url = buy_sound
    if sound_type == "sell": sound_url = sell_sound
    elif sound_type == "win": sound_url = win_sound

    placeholder = st.empty()
    try:
        with placeholder: st.audio(sound_url, autoplay=True)
        time_module.sleep(1.5)
    except: pass
    placeholder.empty()

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

st.session_state.weekend_mode = is_weekend_reale

if 'session_pnl' not in st.session_state: st.session_state.session_pnl = 0.0
if 'last_trade_time' not in st.session_state: st.session_state.last_trade_time = 0
if 'cooldown_minutes' not in st.session_state: st.session_state.cooldown_minutes = 5
if 'report_sent' not in st.session_state: st.session_state.report_sent = False
if 'new_signal_alert' not in st.session_state: st.session_state.new_signal_alert = None
if 'last_status_hour' not in st.session_state: st.session_state.last_status_hour = -1

if st.session_state.new_signal_alert:
    alert_data = st.session_state.new_signal_alert
    bg_color = "#00ff00" if alert_data['dir'] == "BUY" else "#ff0000"
    text_color = "#000000" if alert_data['dir'] == "BUY" else "#ffffff"
    arrow = "⬆️" if alert_data['dir'] == "BUY" else "⬇️"
    
    st.markdown(f"""
        <div style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background-color: {bg_color}; z-index: 9999; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;">
            <h1 style="font-size: 15vw; color: {text_color}; margin-top: 0px;">{alert_data['pair']}</h1>
            <h2 style="font-size: 12vw; color: {text_color}; margin: 20; text-transform: uppercase;">{arrow} {alert_data['dir']} {arrow}</h2>
        </div>
    """, unsafe_allow_html=True)
    
    time_module.sleep(3)
    st.session_state.new_signal_alert = None
    st.rerun()

ora_attuale_report = now_roma.time()
if time(9, 30) <= ora_attuale_report <= time(9, 30) and not st.session_state.report_sent:
    send_morning_report()
    st.session_state.report_sent = True

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("⚙️ AI BINARY TRADING")
    
    if not st.session_state.connected:
        if st.button("🔌 CONNETTI SISTEMA", use_container_width=True, type="primary"):
            with st.spinner("Ricerca connessione disponibile..."):
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
        
        st.divider()
        st.subheader("🌍 TIPO DI MERCATO")

        ora_attuale_time = now_roma.time()
        is_overlap_time = time(14, 30) <= ora_attuale_time <= time(17, 30) and not st.session_state.weekend_mode

        if st.session_state.weekend_mode:
            st.success("🚨 **OTC (Sab-Dom)**\n\nParametri Base: RSI 25-75")
            bb_period = 20
            custom_rsi_buy, custom_rsi_sell = 25, 75
        
        elif is_overlap_time:
            st.warning("⚠️ **LIVE OVERLAP (Lun-Ven)**\n\nParametri Base: RSI 20-80")
            bb_period = 20
            custom_rsi_buy, custom_rsi_sell = 20, 80
        
        else:
            st.success("🟢 **LIVE (Lun-Ven)**\n\nParametri Base: RSI 25-75")
            bb_period = 20
            custom_rsi_buy, custom_rsi_sell = 25, 75
            
        bb_std = st.selectbox("📏 Deviazione BB", [2.00, 2.10, 2.20, 2.30, 2.35, 2.40, 2.50], index=0)

        st.divider()
        st.subheader("🎛️ FILTRI ATTIVI")
        use_bb = st.toggle("Usa Bollinger Bands (BB)", value=True, help="Se disattivato, ignora le Bande di Bollinger")
        use_rsi = st.toggle("Usa RSI", value=True, help="Se disattivato, ignora l'ipercomprato/ipervenduto")
        use_ema = st.toggle("Usa Filtro Trend (EMA)", value=True, help="Evita di operare contro il trend principale")
        use_spread = st.toggle("Applica Filtro Spread", value=False, help="Richiede che il prezzo superi la banda di una % per compensare lo spread")
        pause_8_1030 = st.toggle("Applica Blocco 08:00 - 10:30", value=True, help="Blocco mattutino")
        pause_1330_1430 = st.toggle("Applica Blocco 13:30 - 14:30", value=True, help="Blocco pranzo")
        
        st.divider()
        st.subheader("🏛️ SESSIONI DI MERCATO")
        for city, (start, end) in {"🇬🇧 LONDRA:": (time(9,0), time(18,0)), "🇺🇸 NEW YORK:": (time(14,0), time(23,0)), "🇦🇺 SYDNEY:": (time(0,0), time(8,0)), "🇯🇵 TOKYO:": (time(0,0), time(9,0))}.items():
            status = "Open 🟢" if not is_weekend_reale and start <= now_cet <= end else "Closed 🔴"
            st.write(f"{city} {status}")
            
        status_testo = get_market_status()
        st.info(status_testo if status_testo else "Recupero informazioni mercato...")

        st.markdown("---")
        st.subheader("🛡️ PROTEZIONI DI SISTEMA")
        pausa_manuale_overlap = st.toggle("🛑 **Stop Overlap (Lun-Ven)**", value=True, help="Spegne lo scanner dalle 14:30 alle 17:30")
        
        trading_autorizzato = True
        motivo_blocco = ""

        # --- 1. Blocco Mattutino (Apertura Londra) ---
        ora_attuale_check = now_roma.time()
        
        is_mattino_pericoloso = time(8, 0) <= ora_attuale_check <= time(10, 30)
        if pause_8_1030 and is_mattino_pericoloso:
            trading_autorizzato = False
            motivo_blocco = "🛑 STOP MATTINA: Pausa per l'apertura della borsa di Londra."

        # --- 2. Blocco Pranzo (Alta Latenza/Crollo Volumi) ---
        is_pranzo_pericoloso = time(13, 30) <= ora_attuale_check <= time(14, 30)
        if pause_1330_1430 and is_pranzo_pericoloso:
            trading_autorizzato = False
            motivo_blocco = "🛑 STOP PRANZO: Pausa pre-apertura mercato americano."

        # --- 3. Blocco Overlap Manuale (Lun-Ven) ---
        if is_overlap_time and pausa_manuale_overlap:
            trading_autorizzato = False
            motivo_blocco = "🛑 STOP OVERLAP: Mercato altamente instabile."
            
        is_domenica = (now_roma.weekday() == 6)
        if st.session_state.weekend_mode and is_domenica and (ora_attuale_time >= time(17, 0)):
            trading_autorizzato = False
            motivo_blocco = "🛑 STOP DOMENICA SERA: Scanner bloccato per mercato OTC instabile pre-apertura."

        st.divider()
        st.subheader("🛠️ PARAMETRI TRADING")
        st.session_state.stake = st.number_input("💶 INVESTIMENTO (€)", value=100.0)
        timeframe = st.selectbox("⏱️ TIMEFRAME GRAFICO (s)", [60, 120, 180, 300], index=0)
        ema_period = st.selectbox("⏱️ Periodo EMA", [50, 100], index=0)

        st.divider()
        st.subheader("🖥️ TEST DASHBOARD")
        
        if st.button("🔔 **TEST AUDIO BUY & TELEGRAM**", use_container_width=True):
            play_trade_sound("buy")
            invia_telegram("✅ **SENTINEL AI: SYSTEM CHECK**\nBot online e sincronizzato con Deriv 🚀")
            st.toast("Test completato!", icon="📲")
            
        if st.button("🔔 **TEST AUDIO SELL**", use_container_width=True):
            play_trade_sound("sell")
            st.toast("Test Suono SELL completato!", icon="⬇️")

        if st.button("🗑️ **PULISCI SEGNALI**", use_container_width=True):
            st.session_state.signal_history = []
            st.session_state.session_pnl = 0.0  
            st.session_state.local_balance = 1000.0 
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
    
    # --- LOGICA DELLE 4 SESSIONI DINAMICHE ---
    nome_sessione_attiva = ""
    
    if st.session_state.weekend_mode:
        CURRENT_PAIRS = ["EURUSD", "USDJPY", "AUDUSD", "GBPUSD"]
        nome_sessione_attiva = "🎯 SESSIONE WEEKEND OTC"
    else:
        if time(0, 0) <= ora_attuale_time or ora_attuale_time < time(8, 0):
            CURRENT_PAIRS = ["EURUSD", "GBPUSD", "USDCHF", "USDCAD"]
            nome_sessione_attiva = "🐌 SESSIONE ASIATICA (Bassa Volatilità)"
        elif time(10, 30) <= ora_attuale_time < time(13, 30):
            CURRENT_PAIRS = ["AUDUSD", "NZDUSD", "USDJPY"]
            nome_sessione_attiva = "🇪🇺 SESSIONE EUROPEA (Trend Fluidi)"
        elif time(14, 30) <= ora_attuale_time < time(18, 00):
            CURRENT_PAIRS = ["EURUSD", "USDCAD"]
            nome_sessione_attiva = "🔥 OVERLAP EU+USA (Alta Volatilità)"
        else:
            CURRENT_PAIRS = ["EURJPY", "EURGBP", "EURUSD"]
            nome_sessione_attiva = "🇺🇸 SESSIONE AMERICANA (Ritracciamenti)"

    st.divider()
    st.subheader("🌍 Market Flow 24h")
    
    if st.session_state.weekend_mode or is_weekend_reale:
        try: st.image(Image.open("banner11.png"), use_column_width=True, caption="MODALITÀ WEEKEND ATTIVA 🔴 MERCATI CHIUSI")
        except: st.warning("Immagine banner11.png non trovata.")
    else:
        st.plotly_chart(draw_market_map_inverted(trading_autorizzato), use_container_width=True)

    if st.session_state.scanner_on:
        if not trading_autorizzato:
            st.error(motivo_blocco)
        elif st.session_state.weekend_mode:
            st.success("SCANNER OTC ATTIVO", icon="🎯")
        elif is_overlap_time:
            st.warning(f"⚠️ {nome_sessione_attiva} - In funzione con filtri di sicurezza 🔥")
        else:
            st.success(f"SISTEMA LIVE ATTIVO 🔥 | {nome_sessione_attiva}", icon="📡")

    if st.session_state.scanner_on:
        
        # --- NUOVO: BATTITO CARDIACO ORARIO SU TELEGRAM (SEMPRE ATTIVO) ---
        if st.session_state.last_status_hour != ora_attuale:
            
            sezione_stato = "🟢 *ATTIVO*" if trading_autorizzato else f"🛑 *IN PAUSA AUTOMATICA*\n⚠️ Motivo: {motivo_blocco}"
            
            stato_msg = (
                f"⏱️ *SENTINEL AI: STATUS UPDATE*\n"
                f"Stato Scanner: {sezione_stato}\n\n"
                f"🌍 *Fase:* {nome_sessione_attiva}\n"
                f"💱 *Asset in Scan:* {', '.join([p.replace('frx', '') for p in CURRENT_PAIRS])}\n\n"
                f"⚙️ *Filtri Attuali:*\n"
                f"• RSI: `{custom_rsi_buy}/{custom_rsi_sell}` (ON: {'Sì' if use_rsi else 'No'})\n"
                f"• Bande BB: `{bb_period} dev {bb_std}` (ON: {'Sì' if use_bb else 'No'})\n"
                f"• EMA Trend: `{ema_period}` (ON: {'Sì' if use_ema else 'No'})\n\n"
                #f"*(Questo è un messaggio automatico orario per confermare che il server è online)*"
            )
            invia_telegram(stato_msg)
            st.session_state.last_status_hour = ora_attuale

        #if not trading_autorizzato:
            #st.error(motivo_blocco)

        
        st.divider()
        st.subheader("🕵️ Coppie in Scansione (Auto-Selezionate)")
        cols = st.columns(len(CURRENT_PAIRS))
        for i, pair in enumerate(CURRENT_PAIRS):
            with cols[i]: st.code(f"{icons.get(pair, '🔍')} {pair}")

        for pair in CURRENT_PAIRS:
            if not trading_autorizzato:
                continue
                
            try:
                candles, source = get_candles(pair, timeframe, 400) 
                if not candles or len(candles) < 20: continue
                
                df = pd.DataFrame(candles)

                if st.session_state.weekend_mode and not stress_test:
                    r_buy, r_sell, b_period, b_std = 25, 75, 20, 2.00
                elif stress_test:
                    r_buy, r_sell, b_period, b_std = 45, 55, 20, 2.20
                else:
                    r_buy, r_sell, b_period, b_std = custom_rsi_buy, custom_rsi_sell, bb_period, bb_std

                df['RSI'] = ta.rsi(df['close'], length=7)
                bb = ta.bbands(df['close'], length=b_period, std=b_std)
                
                if use_ema:
                    df['EMA'] = ta.ema(df['close'], length=ema_period)

                if bb is None or bb.empty: continue

                price = df['close'].iloc[-1] 
                
                curr_rsi = df['RSI'].iloc[-2]
                curr_bb_low = float(bb.filter(like='BBL').iloc[-2].iloc[0])
                curr_bb_mid = float(bb.filter(like='BBM').iloc[-2].iloc[0]) 
                curr_bb_up = float(bb.filter(like='BBU').iloc[-2].iloc[0])

                chiusura_prec = df['close'].iloc[-2]

                if use_spread:
                    spread_val = 0.00008 if st.session_state.weekend_mode else 0.00020
                else:
                    spread_val = 0.0
                
                target_bb_low = curr_bb_low * (1 - spread_val)
                target_bb_up = curr_bb_up * (1 + spread_val)   
                
                if use_ema:
                    if 'EMA' in df.columns and not pd.isna(df['EMA'].iloc[-2]):
                        curr_ema = df['EMA'].iloc[-2]
                        cond_ema_buy = curr_bb_mid > curr_ema 
                        cond_ema_sell = curr_bb_mid < curr_ema
                    else:
                        cond_ema_buy, cond_ema_sell = False, False 
                else:
                    cond_ema_buy, cond_ema_sell = True, True
                
                cond_rsi_buy = (curr_rsi < r_buy) if use_rsi else True
                cond_bb_buy = (chiusura_prec <= target_bb_low) if use_bb else True
                
                cond_rsi_sell = (curr_rsi > r_sell) if use_rsi else True
                cond_bb_sell = (chiusura_prec >= target_bb_up) if use_bb else True

                is_buy = (cond_rsi_buy and cond_bb_buy and cond_ema_buy) 
                is_sell = (cond_rsi_sell and cond_bb_sell and cond_ema_sell) 
                
                if not use_bb and not use_rsi and not use_ema:
                    is_buy = False
                    is_sell = False

                current_time = time_module.time()
                trade_attivi_ora = len(st.session_state.active_trades)
                minuti_passati = (current_time - st.session_state.last_trade_time) / 60

                if (is_buy or is_sell) and pair not in st.session_state.active_trades:
                    if trade_attivi_ora >= 2:
                        continue 
                    if minuti_passati < st.session_state.cooldown_minutes:
                        continue

                    direction = "BUY" if is_buy else "SELL"
                    t_id = genera_trade_id()
                    tipo_mercato = "OTC" if st.session_state.weekend_mode else "LIVE"
                    
                    st.session_state.last_trade_time = current_time
                
                    st.session_state.active_trades[pair] = {
                        'id': t_id, 'entry_price': float(price), 'entry_time': current_time, 
                        'direction': direction, 'stake_num': float(st.session_state.stake)
                    }
                    
                    st.session_state.signal_history.append({
                        'id': t_id, 'time': datetime.now(fuso_roma).strftime("%Y-%m-%d %H:%M:%S"),
                        'pair': pair, 'dir': direction, 'price': float(price), 
                        'rsi_val': f"{curr_rsi:.1f}",
                        'stake': f"{st.session_state.stake:.0f}€",                         
                        'params_bb': f"{b_period}/{b_std}" if use_bb else "OFF", 
                        'params_rsi': f"{r_buy}/{r_sell}" if use_rsi else "OFF",
                        'params_ema': f"{ema_period}" if use_ema else "OFF", 
                        'mercato': tipo_mercato, 'result': "⏳ In corso...",
                        'check_120s': "-",
                        'check_180s': "-", 
                        'check_300s': "-", 
                        'inv_60s': "-",     # Variabile nascosta P&L inverso
                        'inv_120s': "-",    # Variabile nascosta P&L inverso
                        'inv_180s': "-",    # Variabile nascosta P&L inverso
                        'inv_300s': "-",    # Variabile nascosta P&L inverso
                        'pnl_numeric': 0.0
                    })

                    save_journal(st.session_state.signal_history)
                    send_telegram_signal(direction, pair, price, curr_rsi, t_id, st.session_state.stake, tipo_mercato)
                    
                    play_trade_sound(direction.lower())
                    st.session_state.new_signal_alert = {"dir": direction, "pair": pair}
                    st.rerun() 

            except Exception as e:
                continue
    
    # --- 5. ANALISI TECNICA GRAFICA ---
    st.divider()
    st.subheader("📈 Analisi Tecnica Principale")
    pair_display = st.selectbox("Seleziona asset per grafico", CURRENT_PAIRS)
    
    df_final = pd.DataFrame()
    
    try:
        candles_ta, src_ta = get_candles(pair_display, timeframe, 400)
            
        if candles_ta:
            st.caption(f"Sorgente dati attuale: **{src_ta}**")
            df_raw = pd.DataFrame(candles_ta)

            df_raw['RSI'] = ta.rsi(df_raw['close'], length=7)

            if st.session_state.weekend_mode and not stress_test:
                r_buy_graf, r_sell_graf, b_period_graf, b_std_graf = 25, 75, 20, 2.10
            elif stress_test:
                r_buy_graf, r_sell_graf, b_period_graf, b_std_graf = 45, 55, 20, 2.20
            else:
                r_buy_graf, r_sell_graf, b_period_graf, b_std_graf = custom_rsi_buy, custom_rsi_sell, bb_period, bb_std

            bb_ta = ta.bbands(df_raw['close'], length=b_period_graf, std=b_std_graf)
            
            if bb_ta is not None and not bb_ta.empty:
                bb_ta.columns = ['BBL', 'BBM', 'BBU', 'BBB', 'BBP'] 
                
                if use_ema:
                    df_raw['EMA'] = ta.ema(df_raw['close'], length=ema_period)
                
                df_final = pd.concat([df_raw, bb_ta[['BBL', 'BBM', 'BBU']]], axis=1).tail(100)

                if use_spread:
                    spread_val_graf = 0.00008 if st.session_state.weekend_mode else 0.00020
                else:
                    spread_val_graf = 0.0

                df_final['buy_sig'] = float('nan')
                df_final['sell_sig'] = float('nan')
                
                df_final['buy_sig'] = df_final.apply(lambda x: (x['close'] * 0.9998) if (
                    ((x['RSI'] < r_buy_graf) if use_rsi else True) and 
                    ((x['close'] <= (x['BBL'] * (1 - spread_val_graf))) if use_bb else True) and
                    ((x['BBM'] > x['EMA']) if (use_ema and 'EMA' in x and not pd.isna(x['EMA'])) else True)
                ) else float('nan'), axis=1)
                
                df_final['sell_sig'] = df_final.apply(lambda x: (x['close'] * 1.0002) if (
                    ((x['RSI'] > r_sell_graf) if use_rsi else True) and 
                    ((x['close'] >= (x['BBU'] * (1 + spread_val_graf))) if use_bb else True) and
                    ((x['BBM'] < x['EMA']) if (use_ema and 'EMA' in x and not pd.isna(x['EMA'])) else True)
                ) else float('nan'), axis=1)
                
                asse_x = df_final['time']
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.5, 0.25], vertical_spacing=0.07, subplot_titles=("📊 Prezzo & Volatilità", "📉 Oscillatore RSI"))
                fig.add_trace(go.Candlestick(x=asse_x, open=df_final['open'], high=df_final['max'], low=df_final['min'], close=df_final['close'], name="Prezzo"), row=1, col=1)
                fig.add_trace(go.Scatter(x=asse_x, y=df_final['BBU'], line=dict(color='rgba(0,71,171,0.4)', width=1), name="BBU"), row=1, col=1)
                fig.add_trace(go.Scatter(x=asse_x, y=df_final['BBM'], line=dict(color='rgba(170,170,170,0.3)', width=1), name="BBM"), row=1, col=1)
                fig.add_trace(go.Scatter(x=asse_x, y=df_final['BBL'], line=dict(color='rgba(0,71,171,0.4)', width=1), fill='tonexty', fillcolor='rgba(60, 130, 180, 0.05)', name="BBL"), row=1, col=1)
                
                if use_ema and 'EMA' in df_final.columns:
                    fig.add_trace(go.Scatter(x=asse_x, y=df_final['EMA'], line=dict(color='#FFA500', width=2), name=f"EMA {ema_period}"), row=1, col=1)

                fig.add_trace(go.Scatter(x=asse_x, y=df_final['RSI'], line=dict(color='#AB63FA'), name="RSI"), row=2, col=1)
                fig.add_hline(y=r_buy_graf, line_color="green", row=2, col=1, line_dash="dash")
                fig.add_hline(y=r_sell_graf, line_color="red", row=2, col=1, line_dash="dash")
                fig.update_layout(xaxis_rangeslider_visible=False, hovermode="x unified", template="plotly_dark", height=600)
                fig.update_xaxes(type='category', tickangle=45, nticks=20, showgrid=True, gridcolor='rgba(130,130,130,0.08)', showspikes=True, spikemode='across', spikecolor="black", spikethickness=1, spikedash="solid")
                fig.add_trace(go.Scatter(x=asse_x, y=df_final['buy_sig'], mode='markers', marker=dict(symbol='triangle-up', size=15, color='#00ff88', line=dict(width=1, color='white')), name="Entry BUY"), row=1, col=1)
                fig.add_trace(go.Scatter(x=asse_x, y=df_final['sell_sig'], mode='markers', marker=dict(symbol='triangle-down', size=15, color='#ff3333', line=dict(width=1, color='white')), name="Entry SELL"), row=1, col=1)
                st.plotly_chart(fig, use_container_width=True)

        st.write("---")
        st.subheader("📊 Analisi Performance (1m)")
        n_buy, n_sell = df_final['buy_sig'].notnull().sum(), df_final['sell_sig'].notnull().sum()
        totale_segnali = n_buy + n_sell

        if st.button("🔍 **VERIFICA ESITO (60s)**", use_container_width=True, type="primary"):
            wins_buy, wins_sell = 0, 0
            for i in range(len(df_final) - 1):
                if pd.notnull(df_final['buy_sig'].iloc[i]) and df_final['close'].iloc[i+1] > df_final['close'].iloc[i]: wins_buy += 1
                if pd.notnull(df_final['sell_sig'].iloc[i]) and df_final['close'].iloc[i+1] < df_final['close'].iloc[i]: wins_sell += 1

            tot_vinti = wins_buy + wins_sell
            tot_persi = totale_segnali - tot_vinti
            accuracy = (tot_vinti / totale_segnali * 100) if totale_segnali > 0 else 0
            bilancio_netto = (tot_vinti * (st.session_state.stake * 0.8)) - (tot_persi * st.session_state.stake)

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
                <small>Basato su investimento di {st.session_state.stake}€ e payout 80% medio</small>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Scegli la coppia di valute e verifica il risultato")
    except Exception as e:
        st.error(f"Errore grafico: {e}")
    
    # --- 6. VERIFICA ESITI TRADE CON DERIV ---
    current_ts = time_module.time() 
    trades_pendenti = list(st.session_state.active_trades.items())

    for pair, trade in trades_pendenti:
        attesa_reale = max(timeframe, 300) 
        scadenza = trade['entry_time'] + attesa_reale + 2 

        if current_ts >= scadenza:
            try:
                res, _ = get_candles(pair, 60, 10)
                
                if res and len(res) >= 7:
                    entry_price = trade['entry_price']
                    dir_trade, t_id = trade['direction'], trade['id']
                    
                    exit_60 = res[-6]['close']
                    exit_120 = res[-5]['close']
                    exit_180 = res[-4]['close']
                    exit_300 = res[-2]['close']
                    
                    # Logica Strategia Originale
                    win_60 = (exit_60 > entry_price) if dir_trade == "BUY" else (exit_60 < entry_price)
                    win_120 = (exit_120 > entry_price) if dir_trade == "BUY" else (exit_120 < entry_price)
                    win_180 = (exit_180 > entry_price) if dir_trade == "BUY" else (exit_180 < entry_price)
                    win_300 = (exit_300 > entry_price) if dir_trade == "BUY" else (exit_300 < entry_price)

                    # Logica Strategia Inversa (i pareggi matematici restano LOSS per entrambe le strategie)
                    win_60_inv = (exit_60 < entry_price) if dir_trade == "BUY" else (exit_60 > entry_price)
                    win_120_inv = (exit_120 < entry_price) if dir_trade == "BUY" else (exit_120 > entry_price)
                    win_180_inv = (exit_180 < entry_price) if dir_trade == "BUY" else (exit_180 > entry_price)
                    win_300_inv = (exit_300 < entry_price) if dir_trade == "BUY" else (exit_300 > entry_price)
                    
                    if timeframe == 60: win = win_60
                    elif timeframe == 120: win = win_120
                    elif timeframe == 180: win = win_180
                    else: win = win_300 

                    res_status = "WIN" if win else "LOSS"
                    profit = (trade['stake_num'] * 0.92) if (res_status == "WIN") else -trade['stake_num']
                    
                    for s in st.session_state.signal_history:
                        if s.get('id') == t_id and s.get('result') == "⏳ In corso...":
                            s['result'] = f"{'✅' if win_60 else '❌'} {'WIN' if win_60 else 'LOSS'}"
                            s['check_120s'] = f"{'✅' if win_120 else '❌'} {'WIN' if win_120 else 'LOSS'}"
                            s['check_180s'] = f"{'✅' if win_180 else '❌'} {'WIN' if win_180 else 'LOSS'}"
                            s['check_300s'] = f"{'✅' if win_300 else '❌'} {'WIN' if win_300 else 'LOSS'}"
                            
                            # Variabili nascoste per il calcolo della strategia Inversa
                            s['inv_60s'] = "WIN" if win_60_inv else "LOSS"
                            s['inv_120s'] = "WIN" if win_120_inv else "LOSS"
                            s['inv_180s'] = "WIN" if win_180_inv else "LOSS"
                            s['inv_300s'] = "WIN" if win_300_inv else "LOSS"

                            s['pnl_numeric'] = float(profit)
                            
                            rsi_ingresso = s.get('rsi_val', 'N/D')
                            st.session_state.session_pnl += profit

                            save_journal(st.session_state.signal_history)

                            esito_120s = f"{'✅' if win_120 else '❌'}"
                            esito_180s = f"{'✅' if win_180 else '❌'}"
                            esito_300s = f"{'✅' if win_300 else '❌'}"
                            tipo_mercato = "OTC" if st.session_state.weekend_mode else "LIVE"
                            
                            p_60 = (trade['stake_num'] * 0.92) if win_60 else -trade['stake_num']
                            p_120 = (trade['stake_num'] * 0.92) if win_120 else -trade['stake_num']
                            p_180 = (trade['stake_num'] * 0.92) if win_180 else -trade['stake_num']
                            p_300 = (trade['stake_num'] * 0.92) if win_300 else -trade['stake_num']

                            # Calcolo Totali Originali
                            storico_df = pd.DataFrame(st.session_state.signal_history)
                            stk = float(st.session_state.stake)
                            
                            w60 = storico_df['result'].astype(str).str.contains("✅").sum()
                            l60 = storico_df['result'].astype(str).str.contains("❌").sum()
                            tot_60 = (w60 * stk * 0.92) - (l60 * stk)
                            
                            w120 = storico_df['check_120s'].astype(str).str.contains("✅").sum()
                            l120 = storico_df['check_120s'].astype(str).str.contains("❌").sum()
                            tot_120 = (w120 * stk * 0.92) - (l120 * stk)
                            
                            w180 = storico_df['check_180s'].astype(str).str.contains("✅").sum()
                            l180 = storico_df['check_180s'].astype(str).str.contains("❌").sum()
                            tot_180 = (w180 * stk * 0.92) - (l180 * stk)

                            w300 = storico_df['check_300s'].astype(str).str.contains("✅").sum()
                            l300 = storico_df['check_300s'].astype(str).str.contains("❌").sum()
                            tot_300 = (w300 * stk * 0.92) - (l300 * stk)

                            # Calcolo Totali Inversi
                            if 'inv_60s' in storico_df.columns:
                                w60_inv = storico_df['inv_60s'].astype(str).str.contains("WIN").sum()
                                l60_inv = storico_df['inv_60s'].astype(str).str.contains("LOSS").sum()
                                tot_60_inv = (w60_inv * stk * 0.92) - (l60_inv * stk)

                                w120_inv = storico_df['inv_120s'].astype(str).str.contains("WIN").sum()
                                l120_inv = storico_df['inv_120s'].astype(str).str.contains("LOSS").sum()
                                tot_120_inv = (w120_inv * stk * 0.92) - (l120_inv * stk)

                                w180_inv = storico_df['inv_180s'].astype(str).str.contains("WIN").sum()
                                l180_inv = storico_df['inv_180s'].astype(str).str.contains("LOSS").sum()
                                tot_180_inv = (w180_inv * stk * 0.92) - (l180_inv * stk)

                                w300_inv = storico_df['inv_300s'].astype(str).str.contains("WIN").sum()
                                l300_inv = storico_df['inv_300s'].astype(str).str.contains("LOSS").sum()
                                tot_300_inv = (w300_inv * stk * 0.92) - (l300_inv * stk)
                            else:
                                tot_60_inv = tot_120_inv = tot_180_inv = tot_300_inv = 0.0
                            
                            # 3. Costruzione del nuovo messaggio Telegram
                            msg = (f"🏁 *ESITO TRADE*\n"
                                   f"🆔 ID: `{t_id}`\n"
                                   f"💱 Asset: {pair}\n"
                                   f"🌍 Market: {tipo_mercato}\n"
                                   f"📈 RSI IN: `{rsi_ingresso}`\n"
                                   f"💶 Stake: `{trade['stake_num']:.0f}€`\n\n"
                                   f"🎯 *W&L BASE*\n"
                                   f"• 1m: {'✅' if win_60 else '❌'} ({p_60:.0f}€)\n"
                                   f"• 2m: {esito_120s} ({p_120:.0f}€)\n"
                                   f"• 3m: {esito_180s} ({p_180:.0f}€)\n"
                                   f"• 5m: {esito_300s} ({p_300:.0f}€)\n\n"
                                   f"📊 *P&L BASE*\n"
                                   f"• 1m: `{tot_60:.0f}€`\n"
                                   f"• 2m: `{tot_120:.0f}€`\n"
                                   f"• 3m: `{tot_180:.0f}€`\n"
                                   f"• 5m: `{tot_300:.0f}€`\n\n"
                                   f"🔄 *P&L INVERSE*\n"
                                   f"• 1m: `{tot_60_inv:.0f}€`\n"
                                   f"• 2m: `{tot_120_inv:.0f}€`\n"
                                   f"• 3m: `{tot_180_inv:.0f}€`\n"
                                   f"• 5m: `{tot_300_inv:.0f}€`")
                            invia_telegram(msg)

                            if res_status == "WIN": play_trade_sound("win")
                            
                            if pair in st.session_state.active_trades:
                                del st.session_state.active_trades[pair]
                else:
                    if current_ts > scadenza + 240:
                        if pair in st.session_state.active_trades:
                            del st.session_state.active_trades[pair]
                            
            except Exception as e:
                if current_ts > scadenza + 240:
                    if pair in st.session_state.active_trades:
                        del st.session_state.active_trades[pair]
                continue
                    
    st.divider()

    # --- 7. TABELLA JOURNAL E FILTRI DINAMICI ---
    st.subheader("📋 Trading Journal & Performance Hub")

    if st.session_state.signal_history:
        df_journal = pd.DataFrame(st.session_state.signal_history)
        colonne_critiche = ['result', 'check_120s', 'check_180s', 'check_300s', 'rsi_val', 'params_ema', 'pnl_numeric']
        for col in colonne_critiche:
            if col not in df_journal.columns:
                df_journal[col] = 0.0 if col == 'pnl_numeric' else "-"
    else:
        df_journal = pd.DataFrame(columns=['id', 'time', 'pair', 'dir', 'price', 'rsi_val', 'stake', 'params_bb', 'params_rsi', 'params_ema', 'mercato', 'result', 'check_120s', 'check_180s', 'check_300s', 'pnl_numeric'])

    df_journal['pnl_numeric'] = pd.to_numeric(df_journal.get('pnl_numeric', 0.0), errors='coerce').fillna(0.0)
    remaining = 0.0 

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
    best_pairs_str, best_pairs_str_120, best_pairs_str_180, best_pairs_str_300 = "-", "-", "-", "-"
    wins, losses, wins_120, losses_120, wins_180, losses_180, wins_300, losses_300 = 0, 0, 0, 0, 0, 0, 0, 0
    total_pnl_60, total_pnl_120, total_pnl_180, total_pnl_300 = 0.0, 0.0, 0.0, 0.0
    
    if total_trades > 0:
        wins = df_filtered['result'].astype(str).str.contains("WIN").sum()
        losses = df_filtered['result'].astype(str).str.contains("LOSS").sum()
        wins_120 = df_filtered['check_120s'].astype(str).str.contains("✅").sum()
        losses_120 = df_filtered['check_120s'].astype(str).str.contains("❌").sum()
        wins_180 = df_filtered['check_180s'].astype(str).str.contains("✅").sum()
        losses_180 = df_filtered['check_180s'].astype(str).str.contains("❌").sum()
        wins_300 = df_filtered['check_300s'].astype(str).str.contains("✅").sum()
        losses_300 = df_filtered['check_300s'].astype(str).str.contains("❌").sum()
        
        total_pnl_60 = df_filtered['pnl_numeric'].sum()
        
        stake_rif = float(st.session_state.stake)
        total_pnl_120 = (wins_120 * (stake_rif * 0.75)) - (losses_120 * stake_rif)
        total_pnl_180 = (wins_180 * (stake_rif * 0.75)) - (losses_180 * stake_rif)
        total_pnl_300 = (wins_300 * (stake_rif * 0.75)) - (losses_300 * stake_rif)
        
        profit_by_pair = df_filtered.groupby('pair')['pnl_numeric'].sum()
        
        def calc_pnl_120(row):
            val = str(row['check_120s'])
            if "✅" in val: return stake_rif * 0.75
            if "❌" in val: return -stake_rif
            return 0.0
            
        def calc_pnl_180(row):
            val = str(row['check_180s'])
            if "✅" in val: return stake_rif * 0.75
            if "❌" in val: return -stake_rif
            return 0.0

        def calc_pnl_300(row):
            val = str(row['check_300s'])
            if "✅" in val: return stake_rif * 0.75
            if "❌" in val: return -stake_rif
            return 0.0
            
        df_filtered['pnl_120_tmp'] = df_filtered.apply(calc_pnl_120, axis=1)
        df_filtered['pnl_180_tmp'] = df_filtered.apply(calc_pnl_180, axis=1)
        df_filtered['pnl_300_tmp'] = df_filtered.apply(calc_pnl_300, axis=1)
        
        profit_by_pair_120 = df_filtered.groupby('pair')['pnl_120_tmp'].sum()
        profit_by_pair_180 = df_filtered.groupby('pair')['pnl_180_tmp'].sum()
        profit_by_pair_300 = df_filtered.groupby('pair')['pnl_300_tmp'].sum()
        
        best_pairs_str = ", ".join(profit_by_pair[profit_by_pair == profit_by_pair.max()].index.tolist()) if not profit_by_pair.empty and profit_by_pair.max() > 0 else "-"
        best_pairs_str_120 = ", ".join(profit_by_pair_120[profit_by_pair_120 == profit_by_pair_120.max()].index.tolist()) if not profit_by_pair_120.empty and profit_by_pair_120.max() > 0 else "-"
        best_pairs_str_180 = ", ".join(profit_by_pair_180[profit_by_pair_180 == profit_by_pair_180.max()].index.tolist()) if not profit_by_pair_180.empty and profit_by_pair_180.max() > 0 else "-"
        best_pairs_str_300 = ", ".join(profit_by_pair_300[profit_by_pair_300 == profit_by_pair_300.max()].index.tolist()) if not profit_by_pair_300.empty and profit_by_pair_300.max() > 0 else "-"

    win_rate_60 = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0.0
    win_rate_120 = (wins_120 / (wins_120 + losses_120) * 100) if (wins_120 + losses_120) > 0 else 0.0
    win_rate_180 = (wins_180 / (wins_180 + losses_180) * 100) if (wins_180 + losses_180) > 0 else 0.0
    win_rate_300 = (wins_300 / (wins_300 + losses_300) * 100) if (wins_300 + losses_300) > 0 else 0.0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🎯 W/L 60s", f"{wins}W - {losses}L")
    c2.metric("💰 P&L 60s", f"{total_pnl_60:.0f} €")
    c3.metric("🏁 Win Rate 60s", f"{win_rate_60:.1f}%")
    c4.metric("🏆 Top Asset 60s", best_pairs_str)

    st.markdown("<hr style='border:1px dashed #555; margin: 10px 0; opacity: 0.5;'>", unsafe_allow_html=True)

    d1, d2, d3, d4 = st.columns(4) 
    d1.metric("🎯 W/L 120s", f"{wins_120}W - {losses_120}L")
    d2.metric("💰 P&L 120s", f"{total_pnl_120:.0f} €")
    d3.metric("🏁 Win Rate 120s", f"{win_rate_120:.1f}%")
    d4.metric("🏆 Top Asset 120s", best_pairs_str_120)
    
    st.markdown("<hr style='border:1px dashed #555; margin: 10px 0; opacity: 0.5;'>", unsafe_allow_html=True)

    e1, e2, e3, e4 = st.columns(4) 
    e1.metric("🎯 W/L 180s", f"{wins_180}W - {losses_180}L")
    e2.metric("💰 P&L 180s", f"{total_pnl_180:.0f} €")
    e3.metric("🏁 Win Rate 180s", f"{win_rate_180:.1f}%")
    e4.metric("🏆 Top Asset 180s", best_pairs_str_180)

    st.markdown("<hr style='border:1px dashed #555; margin: 10px 0; opacity: 0.5;'>", unsafe_allow_html=True)

    g1, g2, g3, g4 = st.columns(4) 
    g1.metric("🎯 W/L 300s", f"{wins_300}W - {losses_300}L")
    g2.metric("💰 P&L 300s", f"{total_pnl_300:.0f} €")
    g3.metric("🏁 Win Rate 300s", f"{win_rate_300:.1f}%")
    g4.metric("🏆 Top Asset 300s", best_pairs_str_300)

    if not df_filtered.empty:
        rename_map = {'id': '🆔 ID', 'time': '⏰ DATE', 'pair': '💱 PAIR', 'dir': '🚀 SIG', 'price': '💰 PRICE', 'rsi_val': '📈 RSI IN', 'stake': '💶 STAKE', 'params_bb': '↔️ BB', 'params_rsi': '📉 RSI', 'params_ema': '🌊 EMA', 'mercato': '🌍 MKT', 'result': '⏱️ 60s', 'check_120s': '⏱️ 120s', 'check_180s': '⏱️ 180s', 'check_300s': '⏱️ 300s', 'pnl_numeric': '📈 P&L'}

        # Usiamo solo le colonne visibili per la UI (le 'inv_*' non ci sono)
        cols_to_use = ['id', 'time', 'pair', 'dir', 'price', 'rsi_val', 'stake', 'params_bb', 'params_rsi', 'params_ema', 'mercato', 'result', 'check_120s', 'check_180s', 'check_300s', 'pnl_numeric']
        
        df_display = df_filtered.iloc[::-1].copy()[[c for c in cols_to_use if c in df_filtered.columns]].rename(columns=rename_map)
        
        df_display['📈 P&L'] = df_display['📈 P&L'].apply(lambda x: f"{x:.0f}€" if x % 1 != 0 else f"{x:.0f}€")
        try:
            colonne_esito = [c for c in ['🎯 60s', '⏱️ 120s', '⏱️ 180s', '⏱️ 300s'] if c in df_display.columns]
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
        
        indices = [("Volatility 50", "EURUSD"), ("Volatility 75", "USDJPY"), ("Volatility 100", "AUDUSD")]
        
        for i, (name, pair) in enumerate(indices):
            with m_cols[i]:
                st.caption(f"📈 {name}")
                candles, _ = get_candles(pair, 60, 40)
                if candles:
                    df = pd.DataFrame(candles)
                    fig = go.Figure(data=[go.Candlestick(x=df['time'], open=df['open'], high=df['max'], low=df['min'], close=df['close'])])
                    fig.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0), xaxis_rangeslider_visible=False, template="plotly_dark")
                    st.plotly_chart(fig, use_container_width=True, key=f"mini_{pair}")
                else:
                    st.warning("In attesa di dati...")
    
    if st.session_state.scanner_on:
        time_module.sleep(30)
        st.rerun()
