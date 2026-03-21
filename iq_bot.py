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
import yfinance as yf  # <--- AGGIUNTO YAHOO FINANCE

# --- 1. CONFIGURAZIONI, TELEGRAM E DERIV ---
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "IL_TUO_TOKEN_QUI")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "IL_TUO_CHAT_ID_QUI")
DERIV_TOKEN = st.secrets.get("DERIV_TOKEN", "") 
DERIV_APP_ID = "71759" 

ALL_PAIRS = ["EURGBP", "USDCHF", "USDJPY", "EURUSD", "GBPUSD", "AUDUSD", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"]
icons = {"EURGBP": "🇪🇺🇬🇧", "USDCHF": "🇺🇸🇨🇭", "USDJPY": "🇺🇸🇯🇵","EURUSD": "🇪🇺🇺🇸", "GBPUSD": "🇬🇧🇺🇸", "AUDUSD": "🇦🇺🇺🇸", "USDCAD": "🇺🇸🇨🇦", "NZDUSD": "🇳🇿🇺🇸", "EURJPY": "🇪🇺🇯🇵", "GBPJPY": "🇬🇧🇯🇵"}

fuso_roma = pytz.timezone('Europe/Rome')
now_roma = datetime.now(fuso_roma)
giorno_settimana = now_roma.weekday() 
is_weekend_reale = giorno_settimana >= 5  
now_cet = now_roma.time()
ora_attuale = now_roma.hour

def to_deriv_symbol(pair):
    # Mapping ristretto a R_10 e R_25 per massima stabilità
    if is_weekend_reale:
        # Recupera la scelta dalla session_state (impostata nella sidebar)
        vol_level = st.session_state.get('otc_config', {}).get(pair, "10")
        return f"R_{vol_level}"
    
    # Durante la settimana usa il Forex reale
    return f"frx{pair}"

# --- NUOVA FUNZIONE IBRIDA (DERIV + YAHOO) ---
def get_candles(pair, timeframe_sec, count):
    """Prova Deriv, se fallisce usa Yahoo Finance"""
    # 1. Tentativo Deriv
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
            return candles, "DERIV 🟢"
    except Exception as e: # Aggiungi 'Exception as e'
        print(f"Errore Deriv: {e}")
        pass 

    # 2. Tentativo Yahoo Finance (SOLO SE NON È WEEKEND)
    if not is_weekend_reale:
        try:
            # ... (tua logica Yahoo Finance attuale)
            return candles, "YAHOO FINANCE 🔵"
        except:
            pass
    
    return None, "MERCATO CHIUSO/ERRORE 🔴"

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
    return f"TRD-{int(datetime.now().timestamp()) % 1000000}"

def get_market_status():
    fuso_roma = pytz.timezone('Europe/Rome')
    now_time = datetime.now(fuso_roma).time()
    londra = (time(9,0), time(18,0))
    new_york = (time(14,0), time(23,0))
    we = is_weekend_reale
    
    if we: return "⚠️ **WEEKEND OTC**"
    if londra[0] <= now_time <= londra[1] and new_york[0] <= now_time <= new_york[1]:
        return "🔥 **OVERLAP EU+USA**\n\nAlta Volatilità"
    if londra[0] <= now_time <= londra[1]: return "🇪🇺 **SESSIONE LONDRA**"
    if new_york[0] <= now_time <= new_york[1]: return "🇺🇸 **SESSIONE NEW YORK**"
    return "💤 **MERCATO LENTO**"

def reset_manual_prices():
    st.session_state.manual_prices = {"EURGBP": 0.0, "USDCHF": 0.0, "AUDUSD": 0.0, "EURUSD": 0.0}
    st.rerun()

def draw_market_map_inverted(trading_autorizzato):
    fig = go.Figure()
    tz_roma = pytz.timezone('Europe/Rome')
    now_roma = datetime.now(tz_roma)
    x_pos = float(now_roma.hour + (now_roma.minute / 60.0))

    try:
        bg_image = Image.open("mondo.png")
    except:
        bg_image = Image.open("banner2.png")

    fig.add_layout_image(dict(
        source=bg_image, xref="x", yref="y", x=24, y=4.5,
        sizex=24, sizey=4.5, sizing="stretch", opacity=1.0, layer="below"
    ))

    color_laser = "#FFD700" if trading_autorizzato else "#0F3ADA"
    fig.add_shape(type="line", x0=x_pos, x1=x_pos, y0=0, y1=4.5, line=dict(color=color_laser, width=3))

    fig.update_layout(
        xaxis=dict(range=[24, 0], showgrid=False, visible=False, fixedrange=True),
        yaxis=dict(range=[0, 4.5], showgrid=False, visible=False, fixedrange=True),
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=0, b=0), height=350
    )
    return fig

def invia_telegram(messaggio):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": messaggio, "parse_mode": "Markdown"}, timeout=5)
    except Exception:
        pass

def send_telegram_signal(signal_type, pair, price, rsi, trade_id, stake): 
    timestamp = datetime.now(fuso_roma).strftime("%H:%M:%S")
    message = (
        f"🚀 *NUOVO TRADE*\n"
        f"🔔 *Segnale:* {signal_type}\n"
        f"🆔 ID: `{trade_id}`\n"
        f"🌍 Market: {mercato}\n"
        f"📊 Asset: {pair}\n"
        f"💵 Stake: `{stake:.0f} €` \n" 
        f"💰 Prezzo: `{price:.5f}`\n"
        f"📊 RSI: `{rsi:.1f}`\n"
        f"⏰ Ora: {timestamp}"
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
    with open(JOURNAL_FILE, "w") as f:
        json.dump(history, f)

def style_pnl(val):
    try:
        clean_val = str(val).replace('€', '').replace(' ', '').strip()
        num_val = float(clean_val)
        if num_val > 0: return 'color: #32cd32; font-weight: bold;'
        elif num_val < 0: return 'color: #ff4b4b; font-weight: bold;'
        return 'color: white;'
    except: return 'color: white;' 

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

# --- 2. SETUP STREAMLIT E SESSIONE ---
st.set_page_config(page_title="Sentinel AI", page_icon="🚀", layout="wide")
st.markdown("""<style>[data-testid="stAppViewContainer"] * { transition: none !important; } div[data-testid="stVerticalBlock"] { opacity: 1 !important; }</style>""", unsafe_allow_html=True)

try:
    logo = Image.open("banner.png")
    st.image(logo, use_column_width=True)
except:
    st.image("https://via.placeholder.com/800x100/ff4b4b/white?text=SENTINEL+AI", use_column_width=True)

if 'connected' not in st.session_state: st.session_state.connected = False
if 'connection_source' not in st.session_state: st.session_state.connection_source = "Nessuna"
if 'active_trades' not in st.session_state: st.session_state.active_trades = {}
if 'signal_history' not in st.session_state: st.session_state.signal_history = load_journal()
if 'local_balance' not in st.session_state: st.session_state.local_balance = 10000.0
if 'scanner_on' not in st.session_state: st.session_state.scanner_on = False
if 'weekend_mode' not in st.session_state: st.session_state.weekend_mode = is_weekend_reale 
if 'api_token' not in st.session_state: st.session_state.api_token = DERIV_TOKEN

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("⚙️ AI TRADING")
    
    if not st.session_state.connected:
        if st.button("🔌 CONNETTI SISTEMA", use_container_width=True, type="primary"):
            with st.spinner("Ricerca connessione disponibile..."):
                # Prova la connessione e mostra la sorgente trovata
                test_data, source = get_candles("EURUSD", 60, 1)
                if test_data:
                    st.session_state.connected = True
                    st.session_state.connection_source = source
                    st.rerun()
                else:
                    st.error("Nessuna sorgente dati disponibile.")
    else:
        st.success(f"Connesso via: **{st.session_state.connection_source}**")
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
        st.subheader("💸 **MERCATO LIVE/OTC**")
        
        if st.session_state.weekend_mode:
            st.warning("🚨 **MERCATO OTC (Sab-Dom)**")
            use_bb, use_rsi = True, True
            bb_period, bb_std = 20, 2.20
            custom_rsi_buy, custom_rsi_sell = 20, 80
        else:
            st.success("🟢 **MERCATO LIVE (Lun-Ven)**")
            col_t1, col_t2 = st.columns(2)
            use_bb = col_t1.toggle("**BB**", value=True)
            use_rsi = col_t2.toggle("**RSI**", value=True)
            c_bb1, c_rsi1 = st.columns(2)
            bb_period = c_bb1.selectbox("Periodo BB", [14, 20], index = 1)
            custom_rsi_buy = c_rsi1.selectbox("RSI Buy", [30, 25, 20, 15], index = 2)
            c_bb2, c_rsi2 = st.columns(2)
            bb_std = c_bb2.selectbox("Dev BB", [2.00, 2.20, 2.50, 2.70], index = 0)
            custom_rsi_sell = c_rsi2.selectbox("RSI Sell", [70, 75, 80, 85], index = 2)

        if st.session_state.weekend_mode:
            st.divider()
            st.subheader("🎯 SETTAGGIO STRATEGIA OTC")
            
            # Selezione rapida della configurazione
            scelta_config = st.radio(
                "Seleziona Setup Operativo:",
                ["Configurazione 1 (BB 2.0)", "Configurazione 2 (BB 2.2)"],
                index=1, # Default sulla più sicura (2.2)
                help="C1: Più aggressiva | C2: Più conservativa (Sniper)"
            )
        
            # Definiamo le variabili globali per la sessione di scansione
            if scelta_config == "Configurazione 1 (BB 2.0)":
                bb_std_otc = 2.0
            else:
                bb_std_otc = 2.2
            
            # RSI fisso a 20/80 come da tua richiesta
            rsi_buy_otc, rsi_sell_otc = 20, 80
        
            st.divider()
            st.subheader("💱 ASSET & VOLATILITÀ")
            
            if 'otc_config' not in st.session_state:
                st.session_state.otc_config = {pair: "10" for pair in ALL_PAIRS}
        
            # Griglia per selezionare la velocità dell'indice per ogni coppia
            for pair in ALL_PAIRS:
                col_p, col_v = st.columns([2, 1])
                with col_p:
                    st.markdown(f"**{pair}**")
                with col_v:
                    vol_choice = st.selectbox(
                        "Vol", ["10", "25"], 
                        key=f"vol_{pair}", 
                        index=0 if st.session_state.otc_config.get(pair) == "10" else 1,
                        label_visibility="collapsed"
                    )
                    st.session_state.otc_config[pair] = vol_choice
        
        st.divider()
        st.subheader("🌍 SESSIONI DI MERCATO")
        for city, (start, end) in {"🇬🇧 LONDRA:": (time(9,0), time(18,0)), "🇺🇸 NEW YORK:": (time(14,0), time(23,0)), "🇦🇺 SYDNEY:": (time(0,0), time(8,0)), "🇯🇵 TOKYO:": (time(0,0), time(9,0))}.items():
            status = "Open 🟢" if not is_weekend_reale and start <= now_cet <= end else "Closed 🔴"
            st.write(f"{city} {status}")
            
        st.info(get_market_status())
        
        st.divider()
        st.subheader("🛠️ PARAMETRI TRADING")
        st.session_state.stake = st.number_input("💶 INVESTIMENTO (€)", value=10.0)
        timeframe = st.selectbox("⏱️ TIMEFRAME (s)", [60, 120], index=0)

        st.divider()
        stress_test = st.toggle("🚀 **STRESS MODE**", value=False)
        if stress_test:
            st.warning("⚠️ **Modalità TEST:**\n\nno BB - RSI (45/55)")
            use_bb, use_rsi = False, True
            custom_rsi_buy, custom_rsi_sell = 45, 55
        else:
            if is_weekend_reale:
                st.info("⚠️ **Modalità WEEKEND OTC**\n\nBB (20/2.20) - RSI (20/80)")
            else:
                st.success("🟢 **Modalità REALE:**\n\nvedi gli indicatori scelti sopra")

        st.divider()
        if st.button("🔔 **TEST AUDIO & TELEGRAM**", use_container_width=True):
            play_trade_sound("buy")
            invia_telegram("✅ **SENTINEL AI: SYSTEM CHECK**\nBot online e pronto 🚀")
            st.toast("Test completato!", icon="📲")

        st.divider()
        if st.button("🗑️ **PULISCI SEGNALI**", use_container_width=True):
            st.session_state.signal_history = []
            save_journal([]) 
            st.rerun()

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
            if st.button("🔄 UNISCI DATI CARICATI", use_container_width=True, type="secondary"):
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

# --- 4. MAIN DASHBOARD ---

    window_1 = (time(0, 0), time(12, 0))
    window_2 = (time(12, 0), time(23, 0))
    is_trading_time = (window_1[0] <= now_cet <= window_1[1]) or (window_2[0] <= now_cet <= window_2[1])
    trading_autorizzato = is_trading_time or stress_test

    st.subheader("🌍 Live Market Flow 24h")
    
    if st.session_state.weekend_mode or is_weekend_reale:
        try:
            img_weekend = Image.open("banner2.png")
            st.image(img_weekend, use_column_width=True, caption="MODALITÀ WEEKEND ATTIVA 🔴 MERCATI CHIUSI")
        except:
            st.warning("Immagine banner2.png non trovata. Carica il file nella cartella del progetto.")
    else:
        st.plotly_chart(draw_market_map_inverted(trading_autorizzato), use_container_width=True)

    placeholder_scanner = st.empty()
    
    if st.session_state.scanner_on:
        if st.session_state.weekend_mode:
            st.success("SCANNER OTC ATTIVO su 🇪🇺🇬🇧-🇺🇸🇨🇭-🇦🇺🇺🇸-🇪🇺🇺🇸 ", icon="🎯")
            esegui_scansione = True
        else:
            if not trading_autorizzato:
                st.warning("🛡️ PROTEZIONE ATTIVA: Mercato fuori orario. Scanner in pausa.")
                esegui_scansione = False
            else:
                if st.session_state.scanner_on:
                    with placeholder_scanner.container(): 
                        st.success("SISTEMA IN SCANSIONE ATTIVA 🔥🔥🔥", icon="📡")
                st.divider()
                st.subheader("🕵️ Coppie di valute osservate")
                cols = st.columns(5)
                for i, pair in enumerate(ALL_PAIRS):
                    with cols[i % 5]: st.code(f"{icons.get(pair, '🔍')} {pair}")
                esegui_scansione = True

        for pair in ALL_PAIRS:

            try:
                # Estrai in modo sicuro le variabili dalla funzione ibrida
                candles, source = get_candles(pair, timeframe, 100) 
                if not candles or len(candles) < 20: continue
                
                df = pd.DataFrame(candles)
                
                # --- LOGICA OTTIMIZZATA PUNTO 3 ---
                if st.session_state.weekend_mode and not stress_test:
                    # Parametri basati sulla scelta nella Sidebar (Config 1 o Config 2)
                    r_buy, r_sell = 20, 80
                    b_per = 20
                    b_std = bb_std_otc  # Questa variabile arriva dalla selezione radio nella sidebar
                elif stress_test:
                    r_buy, r_sell = 45, 55
                    b_per, b_std = 20, 2.20
                else:
                    # Parametri Mercato LIVE (Lun-Ven)
                    r_buy, r_sell = custom_rsi_buy, custom_rsi_sell
                    b_per, b_std = bb_period, bb_std

                # Calcolo effettivo degli indicatori
                df['RSI'] = ta.rsi(df['close'], length=7)
                bb = ta.bbands(df['close'], length=b_per, std=b_std)
                # ----------------------------------

                if bb is None or bb.empty: continue
                price, curr_rsi = df['close'].iloc[-1], df['RSI'].iloc[-1]
                curr_bb_low = float(bb.filter(like='BBL').iloc[-1].iloc[0])
                curr_bb_up = float(bb.filter(like='BBU').iloc[-1].iloc[0])
                
                cond_rsi_buy = (curr_rsi < r_buy) if use_rsi else True
                cond_bb_buy = (price <= curr_bb_low) if use_bb else True
                cond_rsi_sell = (curr_rsi > r_sell) if use_rsi else True
                cond_bb_sell = (price >= curr_bb_up) if use_bb else True
                
                is_consecutive = check_consecutive_candles(df, count=3)
                
                is_buy = (cond_rsi_buy and cond_bb_buy) and (use_rsi or use_bb) and not is_consecutive
                is_sell = (cond_rsi_sell and cond_bb_sell) and (use_rsi or use_bb) and not is_consecutive
                
                if (is_buy or is_sell) and pair not in st.session_state.active_trades:
                    direction = "BUY" if is_buy else "SELL"
                    t_id = genera_trade_id()
                    tipo_mercato = "OTC" if st.session_state.weekend_mode else "LIVE"
                    params_bb = f"{b_per}/{b_std}" if use_bb else "OFF"
                    params_rsi = f"{r_buy}/{r_sell}"
                
                    st.session_state.active_trades[pair] = {
                        'id': t_id, 'entry_price': float(price), 'entry_time': time_module.time(), 
                        'direction': direction, 'stake_num': float(st.session_state.stake)
                    }
                    
                    st.session_state.signal_history.append({
                        'id': t_id, 'time': datetime.now(fuso_roma).strftime("%Y-%m-%d %H:%M:%S"),
                        'pair': pair, 'dir': direction, 'price': float(price), 
                        'stake': f"{st.session_state.stake:.0f}€",                         
                        'params_bb': params_bb, 'params_rsi': params_rsi, 
                        'mercato': tipo_mercato, 'result': "⏳ In corso...",
                        'check_75s': "-", 'check_120s': "-", 'pnl_numeric': 0.0
                    })
                    
                    save_journal(st.session_state.signal_history)
                    send_telegram_signal(direction, pair, price, curr_rsi, t_id, st.session_state.stake)
                    play_trade_sound("buy")
            except Exception as e:
                continue
    
    # --- 5. ANALISI TECNICA GRAFICA ---
    st.divider()
    st.subheader("📈 Analisi Tecnica")
    pair_display = st.selectbox("Seleziona asset per grafico", ALL_PAIRS)
    
    try:
        if st.session_state.weekend_mode and pair_display in st.session_state.get('manual_prices', {}) and st.session_state.manual_prices[pair_display] > 0:
            candles_ta, src_ta = get_candles(pair_display, timeframe, 160)
            if candles_ta:
                candles_ta[-1]['close'] = st.session_state.manual_prices[pair_display]
        else:
            candles_ta, src_ta = get_candles(pair_display, timeframe, 160)
            
        if candles_ta:
            st.caption(f"Sorgente dati attuale: **{src_ta}**")
            df_raw = pd.DataFrame(candles_ta)
            
            df_raw['RSI'] = ta.rsi(df_raw['close'], length=7)
            
            # Parametri dinamici anche per il grafico
            b_per_graf, b_std_graf = (20, 2.20) if st.session_state.weekend_mode and not stress_test else (bb_period, bb_std)
            r_buy_graf, r_sell_graf = (20, 80) if st.session_state.weekend_mode and not stress_test else (custom_rsi_buy, custom_rsi_sell)
            
            bb_ta = ta.bbands(df_raw['close'], length=b_per_graf, std=b_std_graf)
            if bb_ta is None or bb_ta.empty: st.stop()
            
            bb_ta.columns = ['BBL', 'BBM', 'BBU', 'BBB', 'BBP'] 
            df_final = pd.concat([df_raw, bb_ta[['BBL', 'BBM', 'BBU']]], axis=1).tail(100)

            df_final['buy_sig'] = df_final.apply(lambda x: x['close'] if (
                ((x['RSI'] < r_buy_graf) if use_rsi else True) and 
                ((x['close'] <= x['BBL']) if use_bb else True) 
            ) else None, axis=1)
            
            df_final['sell_sig'] = df_final.apply(lambda x: x['close'] if (
                ((x['RSI'] > r_sell_graf) if use_rsi else True) and 
                ((x['close'] >= x['BBU']) if use_bb else True)
            ) else None, axis=1)
         
            asse_x = df_final['time']
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.5, 0.25], vertical_spacing=0.07, subplot_titles=("📊 Prezzo & Volatilità", "📉 Oscillatore RSI"))
            fig.add_trace(go.Candlestick(x=asse_x, open=df_final['open'], high=df_final['max'], low=df_final['min'], close=df_final['close'], name="Prezzo"), row=1, col=1)
            fig.add_trace(go.Scatter(x=asse_x, y=df_final['BBU'], line=dict(color='rgba(0,71,171,0.4)', width=1), name="BBU"), row=1, col=1)
            fig.add_trace(go.Scatter(x=asse_x, y=df_final['BBM'], line=dict(color='rgba(170,170,170,0.3)', width=1), name="BBM"), row=1, col=1)
            fig.add_trace(go.Scatter(x=asse_x, y=df_final['BBL'], line=dict(color='rgba(0,71,171,0.4)', width=1), fill='tonexty', fillcolor='rgba(100, 100, 255, 0.05)', name="BBL"), row=1, col=1)
            fig.add_trace(go.Scatter(x=asse_x, y=df_final['RSI'], line=dict(color='#AB63FA'), name="RSI"), row=2, col=1)
            fig.add_hline(y=r_buy_graf, line_color="green", row=2, col=1, line_dash="dash")
            fig.add_hline(y=r_sell_graf, line_color="red", row=2, col=1, line_dash="dash")
            fig.update_layout(xaxis_rangeslider_visible=False, hovermode="x unified", template="plotly_dark", height=800)
            fig.update_xaxes(type='category', tickangle=45, nticks=20, showgrid=True, gridcolor='rgba(130,130,130,0.08)', showspikes=True, spikemode='across', spikecolor="black", spikethickness=1, spikedash="solid")
            fig.add_trace(go.Scatter(x=asse_x, y=df_final['buy_sig'] * 0.9998, mode='markers', marker=dict(symbol='triangle-up', size=15, color='#00ff88', line=dict(width=1, color='white')), name="Entry BUY"), row=1, col=1)
            fig.add_trace(go.Scatter(x=asse_x, y=df_final['sell_sig'] * 1.0002, mode='markers', marker=dict(symbol='triangle-down', size=15, color='#ff3333', line=dict(width=1, color='white')), name="Entry SELL"), row=1, col=1)
            st.plotly_chart(fig, use_container_width=True)

            if st.session_state.weekend_mode:
                st.divider()
                st.subheader("🎯 **Monitoraggio Sniper OTC**")
                ultimo_prezzo, bbu_25, bbl_25 = df_final['close'].iloc[-1], df_final['BBU'].iloc[-1], df_final['BBL'].iloc[-1]
                distanza_su, distanza_giu = bbu_25 - ultimo_prezzo, ultimo_prezzo - bbl_25
                canale_totale = bbu_25 - bbl_25
                perc_su = max(0, (1 - (distanza_su / (canale_totale/2))) * 100) if canale_totale > 0 else 0
                perc_giu = max(0, (1 - (distanza_giu / (canale_totale/2))) * 100) if canale_totale > 0 else 0

                m1, m2 = st.columns(2)
                with m1:
                    st.metric("DISTANZA BANDA SUPERIORE (SELL)", f"{distanza_su:.5f}", delta=f"{perc_su:.1f}% al Target", delta_color="inverse")
                    if distanza_su <= 0: st.error("🔥 ZONA SELL RAGGIUNTA!")
                with m2:
                    st.metric("DISTANZA BANDA INFERIORE (BUY)", f"{distanza_giu:.5f}", delta=f"{perc_giu:.1f}% al Target", delta_color="normal")
                    if distanza_giu <= 0: st.success("🔥 ZONA BUY RAGGIUNTA!")
                st.progress(min(max(perc_su, perc_giu) / 100, 1.0))
            
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
                bilancio_netto = (tot_vinti * (st.session_state.stake * 0.85)) - (tot_persi * st.session_state.stake)

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
    except Exception as e:
        st.error(f"Errore grafico: {e}")
    
    # --- 6. VERIFICA ESITI TRADE CON DERIV (FIX FINALE) ---
    current_ts = time_module.time() 
    trades_pendenti = list(st.session_state.active_trades.items())

    for pair, trade in trades_pendenti:
        scadenza = trade['entry_time'] + timeframe + 125
        if current_ts >= scadenza:
            try:
                res, _ = get_candles(pair, timeframe, 2)
                if res and len(res) > 0:
                    exit_price, exit_price_120 = res[-2]['close'], res[-1]['close']
                    entry_price, price_75 = trade['entry_price'], float(res[-2]['close'])
                    dir_trade, t_id = trade['direction'], trade['id']
                    
                    win = (exit_price > entry_price) if dir_trade == "BUY" else (exit_price < entry_price)
                    win_75 = (price_75 > entry_price) if dir_trade == "BUY" else (price_75 < entry_price)
                    win_120 = (exit_price_120 > entry_price) if dir_trade == "BUY" else (exit_price_120 < entry_price)

                    res_status = "WIN" if win else "LOSS"
                    icona_esito = "✅" if win else "❌"
                    stake_usato = trade.get('stake_num', float(st.session_state.stake))
                    profit = (stake_usato * 0.85) if win else -stake_usato
                    
                    st.session_state.local_balance += profit
                    for s in st.session_state.signal_history:
                        if s.get('id') == t_id: 
                            s.update({'result': f"{icona_esito} {res_status}", 'check_75s': "✅" if win_75 else "❌", 'check_120s': "✅" if win_120 else "❌", 'pnl_numeric': float(profit)})
                            break

                    msg = (f"🏁 *ESITO* {'💰' if win else '💀'} {res_status}\n"
                           f"🆔 ID: `{t_id}`\n📊 Asset: {pair}\n"
                           f"📉 Esito 60s: {res_status}\n⏱️ Esito 75s: {'✅' if win_75 else '❌'}\n"
                           f"⏱️ Esito 120s: {'✅' if win_120 else '❌'}\n💵 P&L: `{profit:.2f} €`")
                    invia_telegram(msg)
                    if win: play_trade_sound("win")
                        
                    del st.session_state.active_trades[pair]
                    save_journal(st.session_state.signal_history)
                    st.rerun()
            except Exception as e:
                st.error(f"Errore critico verifica {pair}: {e}")
                continue

    st.divider()
    # --- 7. TABELLA JOURNAL E FILTRI DINAMICI ---
    st.subheader("📋 Trading Journal & Performance Hub")
    if st.session_state.signal_history:
        df_journal = pd.DataFrame(st.session_state.signal_history)
        if 'check_75s' not in df_journal.columns: df_journal['check_75s'] = "-"    
        if 'check_120s' not in df_journal.columns: df_journal['check_120s'] = "-"    
    else:
        df_journal = pd.DataFrame(columns=['id', 'time', 'pair', 'dir', 'price', 'stake', 'params_bb', 'params_rsi', 'mercato', 'result', 'check_75s', 'check_120s', 'pnl_numeric'])

    df_journal['pnl_numeric'] = pd.to_numeric(df_journal.get('pnl_numeric', 0.0), errors='coerce').fillna(0.0)

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
    best_pairs_str, wins, losses, total_pnl, wins_75, losses_75, wins_120, losses_120 = "", 0, 0, 0.0, 0, 0, 0, 0
    if total_trades > 0:
        wins, losses = df_filtered['result'].astype(str).str.contains("WIN").sum(), df_filtered['result'].astype(str).str.contains("LOSS").sum()
        wins_75, losses_75 = df_filtered['check_75s'].astype(str).str.contains("✅").sum(), df_filtered['check_75s'].astype(str).str.contains("❌").sum()
        wins_120, losses_120 = df_filtered['check_120s'].astype(str).str.contains("✅").sum(), df_filtered['check_120s'].astype(str).str.contains("❌").sum()
        total_pnl = df_filtered['pnl_numeric'].sum()
        profit_by_pair = df_filtered.groupby('pair')['pnl_numeric'].sum()
        if not profit_by_pair.empty and profit_by_pair.max() > 0: best_pairs_str = ", ".join(profit_by_pair[profit_by_pair == profit_by_pair.max()].index.tolist())

    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0.0
    win_rate_75 = (wins_75 / (wins_75 + losses_75) * 100) if (wins_75 + losses_75) > 0 else 0.0
    win_rate_120 = (wins_120 / (wins_120 + losses_120) * 100) if (wins_120 + losses_120) > 0 else 0.0
    diff_win_rate = win_rate_75 - win_rate
    
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("💰 Profitto", f"{total_pnl:.2f} €", delta=f"{total_pnl:.2f} €")
    c2.metric("🎯 Win/Loss", f"{wins}W - {losses}L", delta=f"Totali: {total_trades}")
    c3.metric("🏁 Win Rate 60s", f"{win_rate:.1f}%")
    c4.metric("🏁 Win Rate 75s", f"{win_rate_75:.1f}%")
    c5.metric("🏁 Win Rate 120s", f"{win_rate_120:.1f}%")
    c6.metric("🏆 Top Asset", best_pairs_str if best_pairs_str else "-")

    if total_trades >= 3:
        with st.expander("🔍 Analisi Strategica: Quali coppie eliminare?"):
            stats_per_pair = []
            for p in df_filtered['pair'].unique():
                df_p = df_filtered[df_filtered['pair'] == p]
                w, w_75 = df_p['result'].astype(str).str.contains("WIN").sum(), df_p['check_75s'].astype(str).str.contains("✅").sum()
                w_120 = df_p['check_120s'].astype(str).str.contains("✅").sum()
                tot_p = len(df_p)
                wr, wr_75, wr_120 = (w / tot_p * 100), (w_75 / tot_p * 100), (w_120 / tot_p * 100)
                diff = wr_75 - wr
                stats_per_pair.append({"Coppia": p, "Trades": tot_p, "WR 60s": f"{wr:.1f}%", "WR 75s": f"{wr_75:.1f}%", "WR 120s": f"{wr_120:.1f}%", "Stabilità": "🟢 Alta" if abs(diff) < 5 else ("🟡 Media" if abs(diff) < 15 else "🔴 Critica")})
            st.dataframe(pd.DataFrame(stats_per_pair), hide_index=True, use_container_width=True)

    if (wins + losses) >= 5:
        if diff_win_rate <= -10: st.error(f"⚡ **ALLERTA VELOCITÀ:** Se ritardi le entrate perdi il {abs(diff_win_rate):.1f}% di Win Rate.")
        elif diff_win_rate >= 10: st.success(f"🐢 **NESSUNA FRETTA:** I trade a 75s vanno meglio del {diff_win_rate:.1f}%.")
        else: st.info(f"⚖️ **STABILITÀ ALTA:** La differenza di timing è irrilevante ({diff_win_rate:+.1f}%).")
    
    if st.session_state.scanner_on: st.caption(f"🔄 Scanner attivo... Ultimo check: {now_roma.time().strftime('%H:%M:%S')}")

    if not df_filtered.empty:
        rename_map = {'id': '🆔 ID', 'time': '⏰ DATA', 'pair': '💱 VALUTE', 'dir': '🚀 TIPO', 'price': '💰 PRICE', 'stake': '💶 STAKE', 'params_bb': '↔️ BB', 'params_rsi': '📉 RSI', 'mercato': '🌍 MERCATO', 'result': '🔍 ESITO 60s', 'check_75s': '⏱️ 75s', 'check_120s': '⏱️ 120s', 'pnl_numeric': '📈 P&L'}
        df_display = df_filtered.iloc[::-1].copy()[[c for c in ['id', 'time', 'pair', 'dir', 'price', 'stake', 'params_bb', 'params_rsi', 'mercato', 'result', 'check_75s', 'check_120s', 'pnl_numeric'] if c in df_filtered.columns]].rename(columns=rename_map)
        df_display['📈 P&L'] = df_display['📈 P&L'].apply(lambda x: f"{x:.1f}€" if x % 1 != 0 else f"{x:.0f}€")
        try:
            colonne_esito = [c for c in ['🔍 ESITO 60s', '⏱️ 75s', '⏱️ 120s'] if c in df_display.columns]
            st.dataframe(df_display.style.applymap(style_result, subset=colonne_esito).applymap(style_pnl, subset=['📈 P&L']), use_container_width=True, hide_index=True)
        except Exception as e:
            st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        if not st.session_state.signal_history: st.info("⏳ Avvia lo Scanner e attendi il primo segnale...")
        else: st.warning("❌ Nessun segnale corrisponde ai filtri selezionati.")

    if st.session_state.scanner_on:
        time_module.sleep(5) 
        st.rerun()
