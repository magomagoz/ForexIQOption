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
import websocket  # Richiede: pip install websocket-client
from datetime import datetime, time, timedelta

# --- 1. CONFIGURAZIONI, TELEGRAM E DERIV ---
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "IL_TUO_TOKEN_QUI")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "IL_TUO_CHAT_ID_QUI")
DERIV_TOKEN = st.secrets.get("DERIV_TOKEN", "") # Inserisci qui il tuo token API Demo di Deriv (Read/Trade)

DERIV_APP_ID = "1089" # App ID generico di Deriv

fuso_roma = pytz.timezone('Europe/Rome')
now_roma = datetime.now(fuso_roma)
giorno_settimana = now_roma.weekday() 
is_weekend_reale = giorno_settimana >= 5  
now_cet = now_roma.time()
ora_attuale = now_roma.hour

def to_deriv_symbol(pair):
    """Converte EURUSD in frxEURUSD per l'API di Deriv"""
    return f"frx{pair}"

def get_deriv_balance(token):
    """Recupera il saldo live dal conto Deriv"""
    try:
        ws = websocket.create_connection(f"wss://ws.binaryws.com/websockets/v3?app_id={DERIV_APP_ID}", timeout=5)
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

def get_deriv_candles(pair, timeframe_sec, count):
    """Scarica le candele tramite WebSocket di Deriv"""
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
            return candles
        return None
    except Exception as e:
        print(f"Errore Deriv WebSocket per {pair}: {e}")
        return None

def genera_trade_id():
    return f"TRD-{int(datetime.now().timestamp()) % 1000000}"

def get_market_status():
    fuso_roma = pytz.timezone('Europe/Rome')
    now_roma = datetime.now(fuso_roma)
    now_time = now_roma.time()

    londra = (time(9,0), time(18,0))
    new_york = (time(14,0), time(23,0))
    
    is_londra = londra[0] <= now_time <= londra[1]
    is_ny = new_york[0] <= now_time <= new_york[1]
    
    if is_londra and is_ny:
        return "🔥 **MERCATI EU+USA**\n\nAlta Volatilità"
    elif is_londra:
        return "🇪🇺 SESSIONE LONDRA"
    elif is_ny:
        return "🇺🇸 SESSIONE NEW YORK"
    else:
        return "💤 MERCATO LENTO"

def reset_manual_prices():
    st.session_state.manual_prices = {"EURGBP": 0.0, "USDCHF": 0.0, "AUDUSD": 0.0, "EURUSD": 0.0}
    st.rerun()

def draw_market_map_inverted(trading_autorizzato):
    fig = go.Figure()
    # Calcolo ora decimale di Roma interno per massima precisione
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

    # Oro se attivo, Blu se protetto
    color_laser = "#FFD700" if trading_autorizzato else "#0F3ADA"

    # Linea Laser + Glow (CORRETTO L'OPACITY QUI)
    fig.add_shape(type="line", x0=x_pos, x1=x_pos, y0=0, y1=4.5, line=dict(color=color_laser, width=3))
    #fig.add_shape(type="line", x0=x_pos, x1=x_pos, y0=0, y1=4.5, line=dict(color=color_laser, width=15), opacity=0.15)

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
    except Exception as e:
        pass

def send_telegram_signal(signal_type, pair, price, rsi, trade_id, stake): 
    timestamp = datetime.now(fuso_roma).strftime("%H:%M:%S")
    message = (
        f"🚀 *NUOVO TRADE*\n"
        f"🔔 *Segnale:* {signal_type}\n"
        f"🆔 ID: `{trade_id}`\n"
        f"📊 Asset: {pair} (Deriv)\n"
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
st.set_page_config(page_title="Sentinel AI - Deriv", page_icon="🚀", layout="wide")

st.markdown("""<style>[data-testid="stAppViewContainer"] * { transition: none !important; } div[data-testid="stVerticalBlock"] { opacity: 1 !important; }</style>""", unsafe_allow_html=True)

try:
    logo = Image.open("banner.png")
    st.image(logo, use_column_width=True)
except:
    st.image("https://via.placeholder.com/800x100/ff4b4b/white?text=SENTINEL+AI+DERIV", use_column_width=True)

if 'connected' not in st.session_state: st.session_state.connected = False
if 'account_type' not in st.session_state: st.session_state.account_type = "DEMO (DERIV)"
if 'active_trades' not in st.session_state: st.session_state.active_trades = {}
if 'signal_history' not in st.session_state: st.session_state.signal_history = load_journal()
if 'local_balance' not in st.session_state: st.session_state.local_balance = 10000.0
if 'scanner_on' not in st.session_state: st.session_state.scanner_on = False
if 'weekend_mode' not in st.session_state: st.session_state.weekend_mode = is_weekend_reale 
if 'api_token' not in st.session_state: st.session_state.api_token = DERIV_TOKEN

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("⚙️ DERIV TRADING")
    
    st.session_state.api_token = st.text_input("🔑 Token Deriv", value=st.session_state.api_token, type="password")

    if not st.session_state.connected:
        st.info("Connettiti per i dati live.")
        if st.button("🔌 CONNETTI SISTEMA", use_container_width=True, type="primary"):
            with st.spinner("Sincronizzazione WS..."):
                test_data = get_deriv_candles("EURUSD", 60, 1)
                if test_data:
                    st.session_state.connected = True
                    # Tenta di prendere il saldo vero se c'è il token
                    if st.session_state.api_token:
                        bal = get_deriv_balance(st.session_state.api_token)
                        if bal: st.session_state.local_balance = bal
                    st.rerun()
                else:
                    st.error("Errore connessione a Deriv API.")
    else:
        if st.button("🔴 DISCONNETTI", use_container_width=True):
            st.session_state.connected = False
            st.session_state.scanner_on = False
            st.rerun()

        st.divider()
        st.subheader("👁️ CONTROLLO SCANNER")
        label = "🛑 STOP SCANNER" if st.session_state.scanner_on else "🚀 AVVIA SCANNER"
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
            bb_period, bb_std = 20, 2.65
            custom_rsi_buy, custom_rsi_sell = 15, 85
        else:
            st.success("🟢 **MERCATO LIVE (Lun-Ven)**")
            col_t1, col_t2 = st.columns(2)
            use_bb = col_t1.toggle("**BB**", value=True)
            use_rsi = col_t2.toggle("**RSI**", value=True)
            c_bb1, c_rsi1 = st.columns(2)
            bb_period = c_bb1.selectbox("Periodo BB", [20, 14], index = 0)
            custom_rsi_buy = c_rsi1.selectbox("RSI Buy", [30, 28, 25], index = 2)
            c_bb2, c_rsi2 = st.columns(2)
            bb_std = c_bb2.selectbox("Dev BB", [1.80, 2.00, 2.20], index = 1)
            custom_rsi_sell = c_rsi2.selectbox("RSI Sell", [70, 72, 75], index = 2)


        # --- LOGICA SIDEBAR OTC ---
        if st.session_state.weekend_mode:
            st.divider()
            st.subheader("🎯 PREZZO MANUALE OTC")
                            
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
        st.subheader("🌍 SESSIONI DI MERCATO")
        
        # Sostituisci la logica dentro il ciclo for delle città con questa:
        for city, (start, end) in {"🇬🇧 LONDRA:": (time(9,0), time(18,0)), "🇺🇸 NEW YORK:": (time(14,0), time(23,0)), "🇦🇺 SYDNEY:": (time(0,0), time(8,0)), "🇯🇵 TOKYO:": (time(0,0), time(9,0))}.items():
            # Usiamo now_cet (che è già un .time()) invece di now_roma
            status = "Open 🟢" if start <= now_cet <= end else "Closed 🔴"
            st.write(f"{city} {status}")
            
        st.info(get_market_status())
        
        st.divider()
        st.subheader("🛠️ PARAMETRI TRADING")
        st.metric(label=f"💰 SALDO DEMO", value=f"{st.session_state.local_balance:.2f} €")
        st.session_state.stake = st.number_input("💶 INVESTIMENTO (€)", value=100.0)
        timeframe = st.selectbox("⏱️ TIMEFRAME (s)", [60, 300], index=0)
                
        st.divider()
        stress_test = st.toggle("🚀 **STRESS MODE**", value=False)
        if stress_test:
            st.warning("⚠️ **Modalità TEST:** \nno BB - RSI (45/55)")
            # --- OVERRIDE DI SISTEMA ---
            use_bb = False       # Spegne forzatamente le BB
            use_rsi = True       # Accende forzatamente l'RSI
            custom_rsi_buy = 45  # Forza soglia BUY
            custom_rsi_sell = 55 # Forza soglia SELL
        else:
            st.success("🟢 **Modalità REALE:** \nvedi gli indicatori scelti sopra")

        #if stress_test:
            #use_bb, use_rsi = False, True       
            #custom_rsi_buy, custom_rsi_sell = 45, 55 

        st.divider()
        if st.button("🔔 **TEST AUDIO & TELEGRAM**", use_container_width=True):
            play_trade_sound("buy")
            invia_telegram("✅ **SENTINEL AI: SYSTEM CHECK**\nBot online e sincronizzato con Deriv 🚀")
            st.toast("Test completato!", icon="📲")

        st.divider()
        if st.button("🗑️ **PULISCI SEGNALI**", use_container_width=True):
            st.session_state.signal_history = []
            save_journal([]) 
            st.rerun()

        st.divider()

        # --- SEZIONE GESTIONE DATI CSV ---
        st.header("💾 GESTIONE SEGNALI")

        # 1. TASTO ESPORTA CSV
        if st.session_state.signal_history:
            df_export = pd.DataFrame(st.session_state.signal_history)
            csv_data = df_export.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 ESPORTA STORICO (CSV)",
                data=csv_data,
                file_name=f"sentinel_history_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            # Tasto disabilitato se non ci sono segnali da esportare
            st.button("📥 ESPORTA STORICO (CSV)", disabled=True, use_container_width=True)

        # 2. WIDGET IMPORTA CSV
        st.caption("Carica un file CSV per ripristinare o unire dati passati:")
        uploaded_file = st.file_uploader("📤 IMPORTA DATI", type=["csv"], label_visibility="collapsed")
        
        if uploaded_file is not None:
            if st.button("🔄 UNISCI DATI CARICATI", use_container_width=True, type="secondary"):
                try:
                    # Legge il file caricato
                    df_import = pd.read_csv(uploaded_file)
                    nuovi_dati = df_import.to_dict('records')
                    
                    # Uniamo la cronologia attuale con quella caricata dal file
                    st.session_state.signal_history.extend(nuovi_dati)
                    
                    # Protezione: rimuove i duplicati esatti (stessa ora e stessa valuta)
                    # per evitare di falsare le statistiche se importi file sovrapposti
                    df_pulito = pd.DataFrame(st.session_state.signal_history).drop_duplicates(subset=['time', 'pair'], keep='last')
                    st.session_state.signal_history = df_pulito.to_dict('records')
                    
                    # Salva anche nel file JSON locale per persistenza
                    save_journal(st.session_state.signal_history) 
                    
                    st.success("✅ Storico fuso con successo!")
                    time_module.sleep(1.5) # Pausa breve per mostrare il messaggio
                    st.rerun()
                except Exception as e:
                    st.error(f"⚠️ Errore nel file: {e}")

        st.divider()
# --- 4. MAIN DASHBOARD ---
if st.session_state.connected:
    ALL_PAIRS = ["EURGBP", "USDCHF", "USDJPY", "EURUSD", "GBPUSD", "AUDUSD", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"]
    icons = {"EURGBP": "🇪🇺🇬🇧", "USDCHF": "🇺🇸🇨🇭", "USDJPY": "🇺🇸🇯🇵","EURUSD": "🇪🇺🇺🇸", "GBPUSD": "🇬🇧🇺🇸", "AUDUSD": "🇦🇺🇺🇸", "USDCAD": "🇺🇸🇨🇦", "NZDUSD": "🇳🇿🇺🇸", "EURJPY": "🇪🇺🇯🇵", "GBPJPY": "🇬🇧🇯🇵"}

    window_1 = (time(0, 0), time(12, 0))
    window_2 = (time(12, 0), time(23, 0))
    is_trading_time = (window_1[0] <= now_cet <= window_1[1]) or (window_2[0] <= now_cet <= window_2[1])
    trading_autorizzato = is_trading_time or stress_test

    st.subheader("🌍 Live Market Flow 24h")
    
    # Rimosso il commento (#) per riattivare la visualizzazione
    if st.session_state.weekend_mode or is_weekend_reale:
        try:
            img_weekend = Image.open("banner2.png")
            st.image(img_weekend, use_column_width=True, caption="MODALITÀ WEEKEND ATTIVA 🔴 MERCATI CHIUSI")
        except:
            st.warning("Immagine banner2.png non trovata. Carica il file nella cartella del progetto.")
    else:
        st.plotly_chart(draw_market_map_inverted(trading_autorizzato), use_container_width=True)

    # --- GESTIONE STATO SCANNER E PROTEZIONE ORARIA ---
        #esegui_scansione = False # Di default è spento
        
    if st.session_state.scanner_on:
        # Messaggio dinamico in base alla modalità
        if st.session_state.weekend_mode:
            st.success("SCANNER OTC ATTIVO su 🇪🇺🇬🇧-🇺🇸🇨🇭-🇦🇺🇺🇸-🇪🇺🇺🇸 ", icon="🎯")
            esegui_scansione = True
        else:
            if not trading_autorizzato:
                st.warning("🛡️ PROTEZIONE ATTIVA: Mercato fuori orario. Scanner in pausa.")
                esegui_scansione = False # IL VERO BLOCCO
            else:
                st.success("SISTEMA IN SCANSIONE ATTIVA 🔥🔥🔥", icon="📡")
 
                st.divider()
                st.subheader("🕵️ Coppie di valute osservate")
                cols = st.columns(5)
                for i, pair in enumerate(ALL_PAIRS):
                    with cols[i % 5]: 
                        st.code(f"{icons.get(pair, '🔍')} {pair}")
                esegui_scansione = True

        for pair in ALL_PAIRS:
            try:
                # Utilizziamo la nuova funzione Deriv
                candles = get_deriv_candles(pair, timeframe, 100)
                if not candles or len(candles) < 20: continue
                
                df = pd.DataFrame(candles)
                df['RSI'] = ta.rsi(df['close'], length=7)
                price, curr_rsi = df['close'].iloc[-1], df['RSI'].iloc[-1]

                r_buy, r_sell = (20, 80) if st.session_state.weekend_mode and not stress_test else (custom_rsi_buy, custom_rsi_sell)
                b_per, b_std = (20, 2.5) if st.session_state.weekend_mode and not stress_test else (bb_period, bb_std)
   
                bb = ta.bbands(df['close'], length=b_per, std=b_std)
                if bb is None or bb.empty: continue

                curr_bb_low = float(bb.filter(like='BBL').iloc[-1].iloc[0])
                curr_bb_up = float(bb.filter(like='BBU').iloc[-1].iloc[0])
                
                cond_rsi_buy = (curr_rsi < r_buy) if use_rsi else True
                cond_bb_buy = (price <= curr_bb_low) if use_bb else True
                cond_rsi_sell = (curr_rsi > r_sell) if use_rsi else True
                cond_bb_sell = (price >= curr_bb_up) if use_bb else True

                is_buy = (cond_rsi_buy and cond_bb_buy) and (use_rsi or use_bb)
                is_sell = (cond_rsi_sell and cond_bb_sell) and (use_rsi or use_bb)

                if (is_buy or is_sell) and pair not in st.session_state.active_trades:
                    direction = "BUY" if is_buy else "SELL"
                    t_id = genera_trade_id()
                    tipo_mercato = "OTC" if st.session_state.weekend_mode else "LIVE"
                    params_bb = f"{bb_period}/{bb_std}"
                    params_rsi = f"{custom_rsi_buy}/{custom_rsi_sell}"
                
                    st.session_state.active_trades[pair] = {
                        'id': t_id, 
                        'entry_price': float(price), 
                        'entry_time': time_module.time(), 
                        'direction': direction, 
                        'stake_num': float(st.session_state.stake)
                    }
                    
                    st.session_state.signal_history.append({
                        'id': t_id,
                        'time': datetime.now(fuso_roma).strftime("%Y-%m-%d %H:%M:%S"),
                        'pair': pair, 
                        'dir': direction, 
                        'price': float(price), 
                        'stake': f"{st.session_state.stake:.0f}€", 
                        'params_bb': f"{b_per}/{b_std}",
                        'params_rsi': f"{r_buy}/{r_sell}",
                        'mercato': tipo_mercato,
                        'result': "⏳ In corso...",
                        'pnl_numeric': 0.0
                    })
                    
                    save_journal(st.session_state.signal_history)
                    send_telegram_signal(direction, pair, price, curr_rsi, t_id, st.session_state.stake)
                    play_trade_sound("buy")

            except Exception as e:
                continue
    
    # --- 5. ANALISI TECNICA GRAFICA (CORRETTA) ---
    st.divider()
    st.subheader("📈 Analisi Tecnica")
    pair_display = st.selectbox("Seleziona asset per grafico", ALL_PAIRS)
    
    try:
        # LOGICA COERENTE CON L'OVERRIDE (Niente 'token' passato alla funzione)
        if st.session_state.weekend_mode and pair_display in st.session_state.get('manual_prices', {}) and st.session_state.manual_prices[pair_display] > 0:
            candles_ta = get_deriv_candles(pair_display, timeframe, 160)
            if candles_ta:
                candles_ta[-1]['close'] = st.session_state.manual_prices[pair_display]
        else:
            candles_ta = get_deriv_candles(pair_display, timeframe, 160)
            
        if candles_ta:
            df_raw = pd.DataFrame(candles_ta)
            
            # Calcolo indicatori
            df_raw['RSI'] = ta.rsi(df_raw['close'], length=7)
            bb_ta = ta.bbands(df_raw['close'], length=bb_period, std=bb_std)
            
            # --- AGGIUNGI QUESTO CONTROLLO SICUREZZA ---
            if bb_ta is None or bb_ta.empty:
                st.error(f"⚠️ Impossibile calcolare le Bande di Bollinger per {pair_display}. Prova a cambiare periodo o asset.")
                st.stop() # Ferma l'esecuzione di questo blocco senza crashare l'app
            
            # Rinominiano le colonne per sicurezza (gestisce nomi diversi della libreria)
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
            fig.add_hline(y=custom_rsi_buy, line_color="green", row=2, col=1, line_dash="dash")
            fig.add_hline(y=custom_rsi_sell, line_color="red", row=2, col=1, line_dash="dash")

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
            st.subheader("📊 Analisi Performance (1m)")
            
            # Calcoliamo i segnali attuali basati sui parametri scelti
            n_buy = df_final['buy_sig'].notnull().sum()
            n_sell = df_final['sell_sig'].notnull().sum()
            totale_segnali = n_buy + n_sell

            if st.button("🔍 VERIFICA ESITO (60s)", use_container_width=True, type="primary"):
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
    
    # --- 6. VERIFICA ESITI TRADE CON DERIV (FIX FINALE) ---
    # Definiamo il timestamp corrente prima di iniziare il ciclo
    current_ts = time_module.time() 
    
    # Creiamo una lista fissa dei trade attivi per evitare errori di mutazione del dizionario
    trades_pendenti = list(st.session_state.active_trades.items())
    
    for pair, trade in trades_pendenti:
        # Calcoliamo quando deve scadere il trade (Entrata + Timeframe + 5 secondi di sicurezza)
        scadenza = trade['entry_time'] + timeframe + 5
        
        if current_ts >= scadenza:
            try:
                # Recuperiamo le candele recenti per verificare il prezzo di chiusura
                res = get_deriv_candles(pair, timeframe, 2)
                if res and len(res) > 0:
                    exit_price = res[-1]['close']
                    entry_price = trade['entry_price']
                    
                    # Logica Win/Loss
                    win = (exit_price > entry_price) if trade['direction'] == "BUY" else (exit_price < entry_price)
                    res_status = "WIN" if win else "LOSS"
                    icona = "✅" if win else "❌"
                    
                    # Calcolo Profitto (Assumiamo payout 85%)
                    stake_usato = trade.get('stake_num', float(st.session_state.stake))
                    profit = (stake_usato * 0.85) if win else -stake_usato
                    
                    # 1. Aggiornamento Saldo Locale
                    st.session_state.local_balance += profit
                    
                    # 2. Aggiornamento Storico (Journal)
                    for s in st.session_state.signal_history:
                        if s.get('id') == trade['id']: 
                            s['result'] = f"{icona} {res_status}"
                            s['pnl_numeric'] = profit
                    
                    # 3. Notifiche Telegram e Suoni
                    invia_telegram(f"🏁 *ESITO* {icona}\n🆔 ID: `{trade['id']}`\n📊 Asset: {pair}\n💵 Profit: {profit:.2f}€")
                    if win: 
                        play_trade_sound("win")
                    
                    # 4. Rimoziome dalla lista dei trade attivi e salvataggio
                    if pair in st.session_state.active_trades:
                        del st.session_state.active_trades[pair]
                    
                    save_journal(st.session_state.signal_history)
                    
                    # Forza il refresh per aggiornare la tabella journal e i box statistici
                    st.rerun()

            except Exception as e:
                # Gestisce eventuali errori di connessione durante la verifica
                print(f"Errore verifica per {pair}: {e}")
                continue

    st.divider()
                                
    # --- 7. TABELLA JOURNAL E FILTRI DINAMICI ---
    st.subheader("📋 Trading Journal & Performance Hub")
    
    if not st.session_state.signal_history:
        st.info("⏳ Nessun trade registrato in questa sessione. Avvia lo Scanner...")
    else:
        # 1. Creiamo il DataFrame base con tutti i dati
        df_journal = pd.DataFrame(st.session_state.signal_history)
        
        # Assicuriamoci che 'pnl_numeric' esista e sia un numero (per sicurezza)
        if 'pnl_numeric' not in df_journal.columns:
            df_journal['pnl_numeric'] = 0.0
        else:
            df_journal['pnl_numeric'] = pd.to_numeric(df_journal['pnl_numeric'], errors='coerce').fillna(0.0)

        # 2. Setup dei 4 Filtri nella UI
        f1, f2, f3, f4 = st.columns(4)
        with f1:
            filtro_mercato = st.selectbox("🌍 Filtro Mercato:", ["TUTTI", "OTC", "LIVE"], index=0)
        with f2:
            # Aggiungo "TUTTE" come prima opzione per non bloccare la vista su una sola coppia
            lista_valute = ["TUTTE"] + ALL_PAIRS
            filtro_coppia = st.selectbox("💱 Coppia di valute:", lista_valute, index=0)
        with f3:
            time_start = st.time_input("🟢 Orario Inizio:", value=time(0, 0))
        with f4:
            time_end = st.time_input("🛑 Orario Fine:", value=time(23, 59))

        # --- LINEA TRATTEGGIATA ---
        st.markdown('<hr style="border: none; border-top: 2px dashed #555; margin: 15px 0; opacity: 0.4;">', unsafe_allow_html=True)

        #st.diveder()
        # 3. Applichiamo le regole di filtraggio al DataFrame
        df_filtered = df_journal.copy()

        # Filtro Mercato
        if filtro_mercato != "TUTTI":
            df_filtered = df_filtered[df_filtered['mercato'].str.contains(filtro_mercato, na=False)]
            
        # Filtro Coppia di Valute
        if filtro_coppia != "TUTTE":
            df_filtered = df_filtered[df_filtered['pair'] == filtro_coppia]

        # Filtro Orario (estrae l'orario dalla stringa 'time' e lo confronta)
        try:
            orari_df = pd.to_datetime(df_filtered['time']).dt.time
            df_filtered = df_filtered[(orari_df >= time_start) & (orari_df <= time_end)]
        except Exception as e:
            pass # Ignora se ci sono errori nei formati data vecchi

        # 4. Ricalcolo Statistiche Dinamiche basate SOLO sui dati filtrati
        total_trades = len(df_filtered)
        best_pairs_str = "" # Stringa vuota di default
        
        if total_trades > 0:
            # Conta quante volte compare WIN o LOSS nella colonna result
            wins = df_filtered['result'].astype(str).str.contains("WIN").sum()
            losses = df_filtered['result'].astype(str).str.contains("LOSS").sum()
            total_pnl = df_filtered['pnl_numeric'].sum()
            
            # --- CALCOLO VALUTA PIÙ PROFITTEVOLE ---
            # Raggruppa per valuta e somma i profitti/perdite
            profit_by_pair = df_filtered.groupby('pair')['pnl_numeric'].sum()
            
            if not profit_by_pair.empty:
                max_profit = profit_by_pair.max()
                # Se c'è almeno un profitto positivo, troviamo le valute corrispondenti
                if max_profit > 0:
                    best_pairs = profit_by_pair[profit_by_pair == max_profit].index.tolist()
                    best_pairs_str = ", ".join(best_pairs) # Unisce se ce n'è più di una
        else:
            wins, losses, total_pnl = 0, 0, 0.0
            
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0.0

        # 5. Mostriamo le Metriche aggiornate in tempo reale (ORA SU 4 COLONNE)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Profitto Filtrato", f"{total_pnl:.2f} €", delta=f"{total_pnl:.2f} €")
        c2.metric("🎯 Win/Loss", f"{wins}W - {losses}L", delta=f"Tot: {total_trades}")
        c3.metric("🏁 Win Rate", f"{win_rate:.1f}%")
        
        # Mostra la metrica Top Asset (vuota se best_pairs_str è vuota, con un trattino o "N/A" per pulizia visiva)
        c4.metric("🏆 Top Asset", best_pairs_str if best_pairs_str else "-")

    if st.session_state.signal_history:
        df_journal = pd.DataFrame(st.session_state.signal_history)
        
        rename_map = {
            'time': '⏰ DATA', 
            'pair': '💱 COPPIA', 
            'dir': '🚀 TIPO',
            'price': '💰 ENTRATA', 
            'stake': '💶 STAKE',
            'params_bb': '↔️ BB (P/D)',
            'params_rsi': '📉 RSI (B/S)', 
            'mercato': '🌍 MERCATO', 
            'result': '🔍 ESITO', 
            'pnl_numeric': '📈 P&L'
        }

        df_visual = df_journal.iloc[::-1].copy()
        
        cols_to_keep = ['time', 'pair', 'dir', 'price', 'stake', 'params_bb', 'params_rsi', 'mercato', 'result', 'pnl_numeric']
        cols_presenti = [c for c in cols_to_keep if c in df_visual.columns]
        df_display = df_visual[cols_presenti].rename(columns=rename_map)

        try:
            st.dataframe(
                df_display.style
                .applymap(style_result, subset=['🔍 ESITO'] if '🔍 ESITO' in df_display.columns else [])
                .applymap(style_pnl, subset=['📈 P&L'] if '📈 P&L' in df_display.columns else [])
                .format({'💰 ENTRATA': "{:.5f}", '📈 P&L': "{:.2f} €"}, na_rep="-"),
                use_container_width=True, hide_index=True
            )
        except Exception:
            st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("⏳ Avvia lo Scanner e attendi il primo segnale...")

    # --- 8. REFRESH LOOP ---
    if st.session_state.scanner_on:
        time_module.sleep(5) 
        st.rerun()
