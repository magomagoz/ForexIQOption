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
DERIV_APP_ID = "1089"  # ID Pubblico per bypassare blocchi EU
INITIAL_STAKE = 100.0
MARTINGALE_MULTIPLIERS = [1.0, 2.1, 4.5] # Base, Step 1, Step 2

ALL_PAIRS = ["EURUSD", "AUDUSD", "USDCAD", "USDCHF", "USDJPY"]
icons = {"EURUSD": "🇪🇺🇺🇸", "AUDUSD": "🇦🇺🇺🇸", "USDCAD": "🇺🇸🇨🇦", "USDCHF": "🇺🇸🇨🇭", "USDJPY": "🇺🇸🇯🇵"}

fuso_roma = pytz.timezone('Europe/Rome')
now_roma = datetime.now(fuso_roma)
giorno_settimana = now_roma.weekday() 
is_weekend_reale = giorno_settimana >= 5  
now_cet = now_roma.time()
ora_attuale = now_roma.hour

# Inizializzazione Session State per Martingala
if 'mtg_step' not in st.session_state:
    st.session_state.mtg_step = 0
if 'last_result' not in st.session_state:
    st.session_state.last_result = "WIN"

# --- 1. MAPPATURA SINTETICI ---
def to_deriv_symbol(symbol):
    mapping = {
        "V50": "R_50",
        "V75": "R_75",
        "V100": "R_100",
        "V75s": "1HZ75V",
        "V100s": "1HZ100V"
    }
    return mapping.get(symbol, symbol)

# --- 2. LOGICA SEGNALI OTTIMIZZATA ---
def get_signals(df):
    df['RSI'] = ta.rsi(df['close'], length=7)
    bb = ta.bbands(df['close'], length=20, std=2.5)
    df['BB_Upper'] = bb['BBU_20_2.5']
    df['BB_Lower'] = bb['BBL_20_2.5']
    
    last = df.iloc[-1]
    
    if last['close'] < last['BB_Lower'] and last['RSI'] < 20:
        return "BUY"
    elif last['close'] > last['BB_Upper'] and last['RSI'] > 80:
        return "SELL"
    return "WAIT"

# --- 3. GESTIONE NOTIFICHE E STAKE ---
def handle_martingale_ui():
    step = st.session_state.mtg_step
    stake = INITIAL_STAKE * MARTINGALE_MULTIPLIERS[step]
    
    if step == 0:
        st.sidebar.success(f"✅ Operatività Normale - Stake: {stake}€")
    elif step == 1:
        st.sidebar.warning(f"⚠️ RECUPERO STEP 1 - Stake: {stake}€")
        st.components.v1.html('<audio autoplay src="https://www.soundjay.com/buttons/beep-07a.mp3"></audio>', height=0)
    elif step == 2:
        st.sidebar.error(f"🚨 ULTIMO TENTATIVO STEP 2 - Stake: {stake}€")
        st.components.v1.html('<audio autoplay src="https://www.soundjay.com/buttons/beep-01a.mp3"></audio>', height=0)
    
    return stake

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

# --- 4. ESECUZIONE TRADE (CONVERTITO A MULTIPLIERS x30) ---
def execute_deriv_trade(token, symbol, direction, stake):
    try:
        ws = websocket.create_connection(f"wss://ws.binaryws.com/websockets/v3?app_id={DERIV_APP_ID}")
        ws.send(json.dumps({"authorize": token}))
        auth = json.loads(ws.recv())
        
        if "error" in auth: return False, auth["error"]["message"]
        
        # SL hard iniziale fissato al -50%
        stop_loss_amount = float(stake) * 0.50
        
        req = {
            "buy": 1,
            "price": float(stake),
            "parameters": {
                "amount": float(stake),
                "basis": "stake",
                "contract_type": "MULTUP" if direction == "BUY" else "MULTDOWN",
                "currency": "USD",
                "multiplier": 30, # LEVA X30
                "symbol": to_deriv_symbol(symbol),
                "limit_order": {
                    "stop_loss": stop_loss_amount
                }
            }
        }
        ws.send(json.dumps(req))
        res = json.loads(ws.recv())
        ws.close()
        
        if "error" in res: return False, res["error"]["message"]
        return True, res["buy"]["contract_id"]
    except Exception as e:
        return False, str(e)

def check_multiplier_contract(token, contract_id):
    """Controlla lo stato corrente e il profitto del contratto aperto"""
    try:
        ws = websocket.create_connection(f"wss://ws.binaryws.com/websockets/v3?app_id={DERIV_APP_ID}", timeout=5)
        ws.send(json.dumps({"authorize": token}))
        ws.recv()
        ws.send(json.dumps({"proposal_open_contract": 1, "contract_id": contract_id}))
        res = json.loads(ws.recv())
        ws.close()
        if "proposal_open_contract" in res:
            return res["proposal_open_contract"]
    except:
        pass
    return None

def close_multiplier_contract(token, contract_id):
    """Vende il contratto a mercato forzatamente (attivazione Trailing SL)"""
    try:
        ws = websocket.create_connection(f"wss://ws.binaryws.com/websockets/v3?app_id={DERIV_APP_ID}", timeout=5)
        ws.send(json.dumps({"authorize": token}))
        ws.recv()
        ws.send(json.dumps({"sell": contract_id, "price": 0}))
        res = json.loads(ws.recv())
        ws.close()
        if "sell" in res:
            return float(res["sell"]["sold_for"])
    except:
        pass
    return None

current_stake = handle_martingale_ui()

def get_market_status():
    fuso_roma = pytz.timezone('Europe/Rome')
    now_time = datetime.now(fuso_roma).time()
    tokyo = (time(0,0), time(9,0))
    londra = (time(9,0), time(18,0))
    new_york = (time(14,0), time(23,0))
    
    if is_weekend_reale: return "⚠️ **WEEKEND OTC**"
    if (londra[0] <= now_time <= londra[1]) and (new_york[0] <= now_time <= new_york[1]): return "🔥 **OVERLAP EU+USA**\n\nAlta Volatilità"
    if londra[0] <= now_time <= londra[1]: return "🇪🇺 **SESSIONE LONDRA**"
    if new_york[0] <= now_time <= new_york[1]: return "🇺🇸 **SESSIONE NEW YORK**"
    if tokyo[0] <= now_time <= tokyo[1]: return "🐌 **SESSIONE ASIATICA**"
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
    alerts = []
    news_events = [
        {"ora": "14:30", "evento": "🇺🇸 Non-Farm Payrolls / CPI (USA)", "impatto": "ALTO"},
        {"ora": "16:00", "evento": "🇺🇸 Indici ISM / Fiducia Consumatori", "impatto": "MEDIO"},
        {"ora": "20:00", "evento": "🇺🇸 FOMC / Decisioni Tassi FED", "impatto": "CRITICO"}
    ]
    for event in news_events:
        alerts.append(f"⚠️ **Ore {event['ora']}**: {event['evento']} - Impatto: {event['impatto']}")
    return alerts

def send_morning_report():
    history = load_journal()
    if not history: return "Buongiorno! ☕️ Nessun trade registrato ieri."
    df = pd.DataFrame(history)
    df['time'] = pd.to_datetime(df['time'])
    ieri = (datetime.now(fuso_roma) - timedelta(days=1)).date()
    df_ieri = df[df['time'].dt.date == ieri]

    if df_ieri.empty:
        msg = f"☀️ **MORNING REPORT ({ieri})**\n\nIeri non sono stati eseguiti trade."
    else:
        wins = df_ieri['result'].astype(str).str.contains("WIN").sum()
        losses = df_ieri['result'].astype(str).str.contains("LOSS").sum()
        pnl = df_ieri['pnl_numeric'].sum()
        wr = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        msg = (f"☀️ **MORNING REPORT ({ieri})**\n\n📊 **Performance di Ieri:**\n✅ Win: {wins} | ❌ Loss: {losses}\n🏁 Win Rate: {wr:.1f}%\n💰 P&L Totale: {pnl:.2f}€\n\n📅 **News Critiche di Oggi:**\n")
        news = get_daily_economic_alerts()
        for n in news: msg += f"{n}\n"
    msg += "\n🚀 *Sistema pronto. Avviare lo scanner dalla dashboard?*"
    invia_telegram(msg)

def invia_telegram(messaggio):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": messaggio, "parse_mode": "Markdown"}, timeout=5)
    except: pass

def send_telegram_signal(signal_type, pair, price, rsi, trade_id, stake, tipo_mercato): 
    timestamp = datetime.now(fuso_roma).strftime("%H:%M:%S")
    message = (f"🚀 *NUOVO TRADE (MULTIPLIER x30)*\n🔔 *Segnale:* {signal_type}\n🆔 ID: `{trade_id}`\n"
               f"💱 Asset: {pair}\n🌍 Market: {tipo_mercato}\n💵 Stake: `{stake:.0f} €` \n" 
               f"💰 Prezzo: `{price:.5f}`\n📈 RSI: `{rsi:.1f}`\n⏰ Ora: {timestamp}")
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

ora_attuale_report = now_roma.time()
if time(8, 30) <= ora_attuale_report <= time(9, 30) and not st.session_state.report_sent:
    send_morning_report()
    st.session_state.report_sent = True

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("⚙️ AI TRADING (Multipliers)")
    
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
        st.subheader("🛠️ PARAMETRI TRADING")
        st.session_state.stake = st.number_input("💶 INVESTIMENTO (€)", value=100.0)
        timeframe = st.selectbox("⏱️ TIMEFRAME SCAN (s)", [60, 120], index=0) # Mantenuto per compatibilità di loop

        st.divider()
        st.subheader("🖥️ TEST DASHBOARD")
        
        if st.button("🔔 **TEST AUDIO & TELEGRAM**", use_container_width=True):
            play_trade_sound("buy")
            invia_telegram("✅ **SENTINEL AI: SYSTEM CHECK**\nBot online e pronto 🚀")
            st.toast("Test completato!", icon="📲")

        if st.button("🗑️ **PULISCI SEGNALI**", use_container_width=True):
            st.session_state.signal_history = []
            st.session_state.session_pnl = 0.0  
            st.session_state.local_balance = 10000.0 
            save_journal([]) 
            st.success("Memoria pulita e PNL resettato!")
            time_module.sleep(1)
            st.rerun()

        trading_autorizzato = True

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

        st.divider()

# --- 4. MAIN DASHBOARD ---
if st.session_state.connected:
    ora_attuale_time = now_roma.time()
    is_night_session = time(0, 0) <= ora_attuale_time < time(7, 0)

    st.divider()
    st.subheader("🌍 Live Market Flow 24h")
    
    st.plotly_chart(draw_market_map_inverted(trading_autorizzato), use_container_width=True)

    if st.session_state.scanner_on:
        st.success("SISTEMA LIVE IN SCANSIONE ATTIVA 🔥", icon="📡")
        
    st.divider()
    st.subheader("🕵️ Coppie di valute osservate")
    cols = st.columns(5)
    for i, pair in enumerate(ALL_PAIRS):
        with cols[i % 5]: st.code(f"{icons.get(pair, '🔍')} {pair}")

    for pair ALL_PAIRS:
        try:
            candles, source = get_candles(pair, timeframe, 100) 
            if not candles or len(candles) < 20: continue
                
            df = pd.DataFrame(candles)

            if st.session_state.weekend_mode and not stress_test:
                r_buy, r_sell, b_period, b_std = 20, 80, 20, 2.20
            elif stress_test:
                r_buy, r_sell, b_period, b_std = 45, 55, 20, 2.20
            else:
                r_buy, r_sell, b_period, b_std = custom_rsi_buy, custom_rsi_sell, bb_period, bb_std

            df['RSI'] = ta.rsi(df['close'], length=7)
            bb = ta.bbands(df['close'], length=b_period, std=b_std)

            if bb is None or bb.empty: continue

            price = df['close'].iloc[-1] 
            curr_rsi = df['RSI'].iloc[-2]
            curr_bb_low = float(bb.filter(like='BBL').iloc[-2].iloc[0])
            curr_bb_up = float(bb.filter(like='BBU').iloc[-2].iloc[0])
            chiusura_prec = df['close'].iloc[-2]
            
            cond_rsi_buy = (curr_rsi < r_buy) if use_rsi else True
            cond_bb_buy = (chiusura_prec <= curr_bb_low) if use_bb else True
            cond_rsi_sell = (curr_rsi > r_sell) if use_rsi else True
            cond_bb_sell = (chiusura_prec >= curr_bb_up) if use_bb else True
            
            is_consecutive = check_consecutive_candles(df.iloc[:-1], count=3)

            is_buy = (cond_rsi_buy and cond_bb_buy) and (use_rsi or use_bb) and not is_consecutive
            is_sell = (cond_rsi_sell and cond_bb_sell) and (use_rsi or use_bb) and not is_consecutive

            current_time = time_module.time()
            trade_attivi_ora = len(st.session_state.active_trades)
            minuti_passati = (current_time - st.session_state.last_trade_time) / 60

            if (is_buy or is_sell) and pair not in st.session_state.active_trades:
                if trade_attivi_ora >= 2: continue 
                if minuti_passati < st.session_state.cooldown_minutes: continue

                direction = "BUY" if is_buy else "SELL"
                t_id = genera_trade_id()
                tipo_mercato = "OTC" if st.session_state.weekend_mode else "LIVE"
                
                # Esecuzione Ordine Multiplier
                success, contract_id_or_err = execute_deriv_trade(DERIV_TOKEN, pair, direction, st.session_state.stake)
                
                if success:
                    st.session_state.last_trade_time = current_time
                
                    st.session_state.active_trades[pair] = {
                        'id': t_id, 
                        'contract_id': contract_id_or_err, # ID per monitorare PnL
                        'entry_price': float(price), 
                        'entry_time': current_time, 
                        'direction': direction, 
                        'stake_num': float(st.session_state.stake),
                        'sl_level': -50 # Stop loss interno tracciato (-50%)
                    }
                    
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
                else:
                    st.error(f"Errore apertura: {contract_id_or_err}")

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

            if st.session_state.weekend_mode and not stress_test: r_buy_graf, r_sell_graf, b_period_graf, b_std_graf = 20, 80, 20, 2.20
            elif stress_test: r_buy_graf, r_sell_graf, b_period_graf, b_std_graf = 45, 55, 20, 2.20
            else: r_buy_graf, r_sell_graf, b_period_graf, b_std_graf = custom_rsi_buy, custom_rsi_sell, bb_period, bb_std

            bb_ta = ta.bbands(df_raw['close'], length=b_period_graf, std=b_std_graf)

            if bb_ta is not None and not bb_ta.empty:
                bb_ta.columns = ['BBL', 'BBM', 'BBU', 'BBB', 'BBP'] 
                df_final = pd.concat([df_raw, bb_ta[['BBL', 'BBM', 'BBU']]], axis=1).tail(100)

                df_final['buy_sig'] = float('nan')
                df_final['sell_sig'] = float('nan')
                df_final['is_consecutive'] = False

                is_green = df_final['close'] > df_final['open']
                is_red = df_final['close'] < df_final['open']
                df_final['is_consecutive'] = (is_green.rolling(3).sum() == 3) | (is_red.rolling(3).sum() == 3)

                df_final['buy_sig'] = df_final.apply(lambda x: (x['close'] * 0.9998) if (((x['RSI'] < r_buy_graf) if use_rsi else True) and ((x['close'] <= x['BBL']) if use_bb else True) and not x['is_consecutive']) else float('nan'), axis=1)
                df_final['sell_sig'] = df_final.apply(lambda x: (x['close'] * 1.0002) if (((x['RSI'] > r_sell_graf) if use_rsi else True) and ((x['close'] >= x['BBU']) if use_bb else True) and not x['is_consecutive']) else float('nan'), axis=1)
                
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
    
    # --- 6. GESTIONE MULTIPLIERS E TRAILING STOP ---
    trades_pendenti = list(st.session_state.active_trades.items())

    for pair, trade in trades_pendenti:
        contract_id = trade.get('contract_id')
        t_id = trade['id']
        if not contract_id: continue

        res_contract = check_multiplier_contract(DERIV_TOKEN, contract_id)
        if not res_contract: continue

        is_sold = res_contract.get('is_sold', 0)
        profit = float(res_contract.get('profit', 0.0))
        stake = trade['stake_num']
        profit_pct = (profit / stake) * 100

        chiusa_ora = False
        motivo_chiusura = "Stop Loss -50%" # Se is_sold=1 dal broker

        if is_sold == 0:
            current_sl = trade.get('sl_level', -50)

            # 1. Sposta l'SL logico interno verso l'alto se il PNL tocca i target
            if profit_pct >= 10 and current_sl < 10:
                st.session_state.active_trades[pair]['sl_level'] = 10
            elif profit_pct >= 5 and current_sl < 5:
                st.session_state.active_trades[pair]['sl_level'] = 5

            # 2. Controllo se il prezzo ritraccia colpendolo
            nuovo_sl = st.session_state.active_trades[pair]['sl_level']
            if nuovo_sl == 10 and profit_pct <= 10:
                chiusa_ora = True
                motivo_chiusura = "Trailing SL 10%"
            elif nuovo_sl == 5 and profit_pct <= 5:
                chiusa_ora = True
                motivo_chiusura = "Trailing SL 5%"

            # 3. Esecuzione Chiusura forzata
            if chiusa_ora:
                sold_for = close_multiplier_contract(DERIV_TOKEN, contract_id)
                if sold_for is not None:
                    is_sold = 1
                    profit = float(sold_for) - stake # Nuovo profit ricalcolato

        # --- SE IL TRADE E' STATO CHIUSO ---
        if is_sold == 1:
            win = profit > 0
            res_status = "WIN" if win else "LOSS"
            icona_esito = "✅" if win else "❌"

            # AGGIORNAMENTO STORICO E JOURNAL
            for s in st.session_state.signal_history:
                if s.get('id') == t_id and s.get('result') == "⏳ In corso...":
                    s['result'] = f"{icona_esito} {res_status}"
                    # Riutilizziamo la colonna check_120s per mostrare il motivo chiusura (SL/Target)
                    s['check_120s'] = motivo_chiusura if profit > 0 else "SL -50%"
                    s['pnl_numeric'] = float(profit)
                    
                    rsi_ingresso = s.get('rsi_val', 'N/D')
                    st.session_state.session_pnl += profit
                    save_journal(st.session_state.signal_history)

                    tipo_mercato = "OTC" if st.session_state.weekend_mode else "LIVE"
                    
                    msg = (f"🏁 *ESITO MULTIPLIER* {'💰' if win else '💀'} {res_status}\n"
                           f"🆔 ID: `{t_id}`\n"
                           f"💱 Asset: {pair}\n"
                           f"🌍 Market: {tipo_mercato}\n"
                           f"📈 RSI Ingresso: `{rsi_ingresso}`\n"
                           f"💵 P&L: `{profit:.2f}€` ({motivo_chiusura})\n"
                           f"📅 P&L Sessione: `{st.session_state.session_pnl:.2f}€` ")
                    invia_telegram(msg)

                    if res_status == "WIN": play_trade_sound("win")
                    
                    if pair in st.session_state.active_trades:
                        del st.session_state.active_trades[pair]
                    
    st.divider()

    # --- 7. TABELLA JOURNAL E FILTRI DINAMICI ---
    st.subheader("📋 Trading Journal & Performance Hub")

    if st.session_state.signal_history:
        df_journal = pd.DataFrame(st.session_state.signal_history)
        colonne_critiche = ['result', 'check_120s', 'rsi_val', 'pnl_numeric']
        for col in colonne_critiche:
            if col not in df_journal.columns:
                df_journal[col] = 0.0 if col == 'pnl_numeric' else "-"
    else:
        df_journal = pd.DataFrame(columns=['id', 'time', 'pair', 'dir', 'price', 'rsi_val', 'stake', 'params_bb', 'params_rsi', 'mercato', 'result', 'check_120s', 'pnl_numeric'])

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

    st.markdown("<hr style='border:1px dashed #555; margin: 10px 0; opacity: 0.5;'>", unsafe_allow_html=True)

    f1, f2, f3, f4 = st.columns(4)
    with f1: filtro_mercato = st.selectbox("🌍 Mercato:", ["TUTTI", "OTC", "LIVE"], index=0)
    with f2: filtro_coppia = st.selectbox("💱 Coppia di valute:", ["TUTTE"] + ALL_PAIRS, index=0)
    with f3: time_start = st.time_input("🟢 Orario Inizio:", value=time(0, 0))
    with f4: time_end = st.time_input("🛑 Orario Fine:", value=time(23, 59))

    df_filtered = df_journal.copy()
    if not df_filtered.empty:
        if filtro_mercato != "TUTTI": df_filtered = df_filtered[df_filtered['mercato'].astype(str).str.contains(filtro_mercato, na=False)]
        if filtro_coppia != "TUTTE": df_filtered = df_filtered[df_filtered['pair'] == filtro_coppia]
        try:
            orari_df = pd.to_datetime(df_filtered['time']).dt.time
            df_filtered = df_filtered[(orari_df >= time_start) & (orari_df <= time_end)]
        except Exception: pass 

    total_trades = len(df_filtered)
    wins, losses, total_pnl = 0, 0, 0.0
    best_pairs_str = "-"
    
    if total_trades > 0:
        wins = df_filtered['result'].astype(str).str.contains("WIN").sum()
        losses = df_filtered['result'].astype(str).str.contains("LOSS").sum()
        total_pnl = df_filtered['pnl_numeric'].sum()
        profit_by_pair = df_filtered.groupby('pair')['pnl_numeric'].sum()
        best_pairs_str = ", ".join(profit_by_pair[profit_by_pair == profit_by_pair.max()].index.tolist()) if not profit_by_pair.empty and profit_by_pair.max() > 0 else "-"

    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0.0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🎯 W/L Totali", f"{wins}W - {losses}L")
    c2.metric("💰 P&L Netto", f"{total_pnl:.2f} €")
    c3.metric("🏁 Win Rate", f"{win_rate:.1f}%")
    c4.metric("🏆 Top Asset", best_pairs_str)

    if not df_filtered.empty:
        # check_120s convertita in MOTIVO CHIUSURA
        rename_map = {'id': '🆔 ID', 'time': '⏰ DATA', 'pair': '💱 VALUTE', 'dir': '🚀 TIPO', 'price': '💰 PRICE', 'rsi_val': '📈 RSI IN', 'stake': '💶 STAKE', 'mercato': '🌍 MARKET', 'result': '🎯 ESITO', 'check_120s': '⏱️ MOTIVO', 'pnl_numeric': '📈 P&L'}
        cols_to_use = ['id', 'time', 'pair', 'dir', 'price', 'rsi_val', 'stake', 'mercato', 'result', 'check_120s', 'pnl_numeric']
        
        df_display = df_filtered.iloc[::-1].copy()[[c for c in cols_to_use if c in df_filtered.columns]].rename(columns=rename_map)
        df_display['📈 P&L'] = df_display['📈 P&L'].apply(lambda x: f"{x:.2f}€")
        try:
            st.dataframe(df_display.style.applymap(style_result, subset=['🎯 ESITO', '⏱️ MOTIVO']).applymap(style_pnl, subset=['📈 P&L']), use_container_width=True, hide_index=True)
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
        time_module.sleep(5) 
        st.rerun()
