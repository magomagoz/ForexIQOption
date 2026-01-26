import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime, time
import pytz
import time as time_lib
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import os

# Tenta l'importazione di IQ Option API (gestione errore se non installata)
try:
    from iqoptionapi.stable_api import IQ_Option
except ImportError:
    st.error("Libreria 'iqoptionapi' non trovata. Assicurati di averla installata.")
    IQ_Option = None

# --- COSTANTI DI MERCATO ---
SIMULATED_SPREAD = 0.0005 

# --- 1. CONFIGURAZIONE & LAYOUT ---
st.set_page_config(page_title="Forex Momentum Pro AI - IQ Bot", layout="wide", page_icon="📈")

st.markdown("""
    <style>
        .block-container {padding-top: 1rem !important;}
        [data-testid="stSidebar"] > div:first-child {padding-top: 0rem !important;}
        footer {visibility: hidden;}
        header {background-color: rgba(0,0,0,0) !important;} 
        div.stButton > button {border-radius: 8px !important; font-weight: bold; width: 100%;}
        [data-testid="stDataFrame"] {border: 1px solid #333;}
    </style>
""", unsafe_allow_html=True)

# Definizione Fuso Orario Roma
rome_tz = pytz.timezone('Europe/Rome')

# Mappa Asset
asset_map = {
    "EURUSD": {"yf": "EURUSD=X", "iq": "EURUSD"},
    "GBPUSD": {"yf": "GBPUSD=X", "iq": "GBPUSD"},
    "USDJPY": {"yf": "USDJPY=X", "iq": "USDJPY"},
    "AUDUSD": {"yf": "AUDUSD=X", "iq": "AUDUSD"},
    "USDCAD": {"yf": "USDCAD=X", "iq": "USDCAD"},
    "USDCHF": {"yf": "USDCHF=X", "iq": "USDCHF"},
    "NZDUSD": {"yf": "NZDUSD=X", "iq": "NZDUSD"},
    "BTC-USD": {"yf": "BTC-USD", "iq": "BITCOIN"},
    "ETH-USD": {"yf": "ETH-USD", "iq": "ETHEREUM"}
}

# Refresh automatico ogni 60 secondi
st_autorefresh(interval=60 * 1000, key="sentinel_refresh")

# --- 2. FUNZIONI TECNICHE ---

def save_history_permanently():
    try:
        if 'signal_history' in st.session_state and not st.session_state['signal_history'].empty:
            st.session_state['signal_history'].to_csv("permanent_signals_db.csv", index=False)
    except Exception as e:
        print(f"Errore salvataggio file: {e}")

def load_history_from_csv():
    cols = ['DataOra', 'Asset', 'Direzione', 'Prezzo', 'SL', 'TP', 'Stato', 'Investimento €', 'Risultato €', 'Costo Spread €', 'Stato_Prot', 'IQ_ID']
    if os.path.exists("permanent_signals_db.csv"):
        try:
            df = pd.read_csv("permanent_signals_db.csv")
            for col in cols:
                if col not in df.columns: df[col] = "0.00" if "€" in col else ""
            return df
        except:
            return pd.DataFrame(columns=cols)
    return pd.DataFrame(columns=cols)

def send_telegram_msg(msg):
    try:
        # Recupera token dai secrets o usa stringa vuota per evitare crash
        if "telegram" in st.secrets:
            token = st.secrets["telegram"]["token"]
            chat_id = st.secrets["telegram"]["chat_id"]
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            params = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
            requests.get(url, params=params, timeout=5)
    except Exception as e:
        print(f"Errore Telegram: {e}")

def get_now_rome():
    return datetime.now(rome_tz)

def is_market_open(asset_name):
    if "BTC" in asset_name or "ETH" in asset_name: return True
    today = get_now_rome().weekday()
    if today >= 5: return False # Sabato/Domenica Forex chiuso
    return True

def play_notification_sound():
    st.markdown("""<audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>""", unsafe_allow_html=True)

def play_close_sound():
    st.markdown("""<audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2017/2017-preview.mp3" type="audio/mpeg"></audio>""", unsafe_allow_html=True)

def play_safe_sound():
    st.markdown("""<audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2021/2021-preview.mp3" type="audio/mpeg"></audio>""", unsafe_allow_html=True)

def style_status(val):
    if val == '✅ TARGET': return 'background-color: rgba(0, 255, 204, 0.2); color: #00ffcc;'
    if val == '❌ STOP LOSS': return 'background-color: rgba(255, 75, 75, 0.2); color: #ff4b4b;'
    if val == '🛡️ SL DINAMICO': return 'background-color: rgba(255, 165, 0, 0.2); color: #ffa500;'
    try:
        if float(str(val).replace('€', '').replace('+', '').strip()) > 0: return 'color: #00ffcc; font-weight: bold;'
        if float(str(val).replace('€', '').replace('+', '').strip()) < 0: return 'color: #ff4b4b; font-weight: bold;'
    except: pass
    return ''

def get_session_status():
    now_time = get_now_rome().time()
    is_weekend = get_now_rome().weekday() >= 5 
    if is_weekend: return {"Tokyo 🇯🇵": False, "Londra 🇬🇧": False, "New York 🇺🇸": False}
    sessions = {
        "Tokyo 🇯🇵": (time(0, 0), time(9, 0)), 
        "Londra 🇬🇧": (time(9, 0), time(18, 0)), 
        "New York 🇺🇸": (time(14, 0), time(23, 0))
    }
    return {name: start <= now_time <= end for name, (start, end) in sessions.items()}

def get_dynamic_leverage(api, iq_ticker, instrument_type):
    try:
        instruments = api.get_instruments(instrument_type)
        for i in instruments:
            if i['id'].lower() == iq_ticker.lower(): return i['leverage_max']
        return 1
    except: return 1

def get_real_spread_info(api, iq_ticker):
    try:
        orderbook = api.get_orderbook(iq_ticker)
        ask = float(orderbook['asks'][0][0])
        bid = float(orderbook['bids'][0][0])
        spread_reale = ask - bid
        prezzo_medio = (ask + bid) / 2
        spread_pct = (spread_reale / prezzo_medio) * 100
        return spread_reale, spread_pct
    except:
        return SIMULATED_SPREAD, 0.05

def get_currency_strength():
    try:
        forex = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "USDCHF=X", "NZDUSD=X", "EURCHF=X", "EURJPY=X", "GBPJPY=X", "GBPCHF=X", "EURGBP=X"]
        crypto = ["BTC-USD", "ETH-USD"]
        all_tickers = forex + crypto
        data = yf.download(all_tickers, period="1d", interval="1m", progress=False)

        if data is None or data.empty: return pd.Series(dtype=float)

        if isinstance(data.columns, pd.MultiIndex):
            close_data = data['Close']
        else:
            close_data = data['Close'] if 'Close' in data else data

        close_data = close_data.ffill().dropna()
        if len(close_data) < 2: return pd.Series(dtype=float)

        returns = close_data.pct_change().iloc[-1] * 100
        
        strength = {
            "USD 🇺🇸": (-returns.get("EURUSD=X",0) - returns.get("GBPUSD=X",0) + returns.get("USDJPY=X",0) - returns.get("AUDUSD=X",0) + returns.get("USDCAD=X",0) + returns.get("USDCHF=X",0) - returns.get("NZDUSD=X",0)) / 7,
            "EUR 🇪🇺": (returns.get("EURUSD=X",0) + returns.get("EURJPY=X",0) + returns.get("EURGBP=X",0) + returns.get("EURCHF=X", 0)) / 4,
            "GBP 🇬🇧": (returns.get("GBPUSD=X",0) + returns.get("GBPJPY=X",0) - returns.get("EURGBP=X",0) + returns.get("GBPCHF=X", 0)) / 4,
            "JPY 🇯🇵": (-returns.get("USDJPY=X",0) - returns.get("EURJPY=X",0) - returns.get("GBPJPY=X",0)) / 3,
            "CHF 🇨🇭": (-returns.get("USDCHF=X",0) - returns.get("EURCHF=X",0) - returns.get("GBPCHF=X",0)) / 3,
            "AUD 🇦🇺": returns.get("AUDUSD=X", 0),
            "CAD 🇨🇦": -returns.get("USDCAD=X", 0),
            "BTC ₿": returns.get("BTC-USD", 0),
            "ETH 💎": returns.get("ETH-USD", 0)
        }
        return pd.Series(strength).sort_values(ascending=False)
    except Exception:
        return pd.Series(dtype=float)

def get_asset_params(pair):
    if "BTC" in pair or "ETH" in pair: return 1.0, "{:.2f}", 1, "CRYPTO"
    elif "JPY" in pair: return 0.01, "{:.3f}", 100, "FOREX_JPY"
    else: return 0.0001, "{:.5f}", 10000, "FOREX_STD"

def detect_divergence(df):
    try:
        if len(df) < 20: return "Analisi..."
        price, rsi_col = df['close'], df['rsi']
        curr_p, curr_r = float(price.iloc[-1]), float(rsi_col.iloc[-1])
        prev_max_p = price.iloc[-20:-1].max()
        prev_max_r = rsi_col.iloc[-20:-1].max()
        prev_min_p = price.iloc[-20:-1].min()
        prev_min_r = rsi_col.iloc[-20:-1].min()
        if curr_p > prev_max_p and curr_r < prev_max_r: return "📉 DECRESCITA"
        elif curr_p < prev_min_p and curr_r > prev_min_r: return "📈 CRESCITA"
    except: pass
    return "Neutrale"

def update_signal_outcomes(api_conn):
    if st.session_state['signal_history'].empty: return
    df = st.session_state['signal_history']
    updates_made = False

    for idx, row in df[df['Stato'] == 'In Corso'].iterrows():
        try:
            ticker_yf = asset_map[row['Asset']]['yf']
            df_temp = yf.download(ticker_yf, period="1d", interval="1m", progress=False)
            if df_temp.empty: continue
            
            if isinstance(df_temp.columns, pd.MultiIndex):
                df_temp.columns = df_temp.columns.get_level_values(0)
            df_temp.columns = [str(c).lower() for c in df_temp.columns]

            current_price = float(df_temp['close'].iloc[-1])
            entry_v = float(str(row['Prezzo']).replace(',', '.'))
            current_sl = float(str(row['SL']).replace(',', '.'))
            investimento = float(str(row['Investimento €']).replace(',', '.'))
            costo_spread_euro = float(str(row.get('Costo Spread €', '0.00')).replace(',', '.'))
            
            direzione = row['Direzione']
            status_prot = row.get('Stato_Prot', 'Iniziale')

            if direzione == 'COMPRA':
                percent_gain = ((current_price - entry_v) / entry_v) * 100
            else:
                percent_gain = ((entry_v - current_price) / entry_v) * 100

            # --- LOGICA TRAILING ---
            new_sl = current_sl
            be_level = st.session_state.get('trailing_be_val', 0.4)
            safe_level = st.session_state.get('trailing_safe_val', 0.8)
            trend_level = st.session_state.get('trailing_trend_val', 1.4)
        
            if percent_gain >= be_level and 'Iniziale' in status_prot:
                new_sl = entry_v
                status_prot = f'BE ({be_level}%)'
                play_safe_sound()
            elif percent_gain >= safe_level and ('Iniziale' in status_prot or 'BE' in status_prot):
                new_sl = entry_v * 1.005 if direzione == 'COMPRA' else entry_v * 0.995
                status_prot = 'Safe (+0.5%)'
                play_safe_sound()
            elif percent_gain >= trend_level and 'Safe' in status_prot:
                new_sl = entry_v * 1.012 if direzione == 'COMPRA' else entry_v * 0.988
                status_prot = 'Trend (+1.0%)'
                play_safe_sound()

            # --- VERIFICA CHIUSURA ---
            tp_v = float(str(row['TP']).replace(',', '.'))
            target_hit = (direzione == 'COMPRA' and current_price >= tp_v) or (direzione == 'VENDI' and current_price <= tp_v)
            stop_hit = (direzione == 'COMPRA' and current_price <= new_sl) or (direzione == 'VENDI' and current_price >= new_sl)

            if target_hit or stop_hit:
                esito = '✅ TARGET' if target_hit else ('🛡️ SL DINAMICO' if 'Iniziale' not in status_prot else '❌ STOP LOSS')
                profitto_lordo = investimento * (percent_gain / 100)
                final_net_profit = profitto_lordo - costo_spread_euro
                
                df.at[idx, 'Stato'] = esito
                df.at[idx, 'Risultato €'] = f"{final_net_profit:+.2f}"
                updates_made = True
                play_close_sound()
                send_telegram_msg(f"🏁 CHIUSO: {row['Asset']}\nNetto: {final_net_profit:+.2f}€")
            
            elif new_sl != current_sl:
                _, p_fmt, _, _ = get_asset_params(row['Asset'])
                df.at[idx, 'SL'] = p_fmt.format(new_sl)
                df.at[idx, 'Stato_Prot'] = status_prot
                updates_made = True

        except Exception: continue 
        
    if updates_made:
        st.session_state['signal_history'] = df
        save_history_permanently()

def run_sentinel(api_conn):
    """
    Motore Sentinel: Monitora il mercato, genera segnali basati su BB/RSI/ADX.
    """
    debug_list = []
    current_balance = api_conn.get_balance() if api_conn else st.session_state.get('balance_val', 1000)
    current_risk = st.session_state.get('risk_val', 2.0)

    for label, tickers in asset_map.items():
        yf_ticker = tickers['yf']
        iq_ticker = tickers['iq']
        
        try:
            # 1. Recupero dati
            df = yf.download(yf_ticker, period="1d", interval="1m", progress=False)
            if df.empty or len(df) < 20: continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).lower() for c in df.columns]
            
            # 2. CALCOLO INDICATORI
            bb_s = ta.bbands(df['close'], length=20, std=2)
            rsi_s = ta.rsi(df['close'], length=14)
            adx_s = ta.adx(df['high'], df['low'], df['close'], length=14)
            
            if bb_s is None or rsi_s is None or adx_s is None: continue

            # Variabili chiave
            curr_v = float(df['close'].iloc[-1])
            low_bb = float(bb_s.iloc[-1, 0])  # Lower BB
            up_bb = float(bb_s.iloc[-1, 2])   # Upper BB
            rsi_val = float(rsi_s.iloc[-1])
            # ADX è la prima colonna (indice 0) del dataframe restituito da ta.adx
            curr_adx = float(adx_s.iloc[-1, 0]) 

            # Aggiungi al log
            debug_list.append(f"🔍 {label}: RSI {rsi_val:.1f} | ADX {curr_adx:.1f}")

            # 3. LOGICA SEGNALE (Mean Reversion in Range)
            s_action = None
            # Buy: Prezzo sotto banda inferiore, ipervenduto, trend debole (range)
            if curr_v < low_bb and rsi_val < 30 and curr_adx < 30:
                s_action = "COMPRA"
            # Sell: Prezzo sopra banda superiore, ipercomprato, trend debole
            elif curr_v > up_bb and rsi_val > 70 and curr_adx < 30:
                s_action = "VENDI"

            if s_action:
                # 4. CONTROLLO POSIZIONI ESISTENTI
                hist = st.session_state['signal_history']
                is_running = not hist.empty and ((hist['Asset'] == label) & (hist['Stato'] == 'In Corso')).any()
                
                if not is_running:
                    p_unit, p_fmt, p_mult, a_type = get_asset_params(label)
                    instrument_type = "crypto" if "BTC" in label or "ETH" in label else "forex"
                    
                    # 5. SPREAD & ENTRY
                    spread_val, _ = get_real_spread_info(api_conn, iq_ticker) if api_conn else (SIMULATED_SPREAD, 0.05)
                    entry_with_spread = curr_v + (spread_val / 2) if s_action == "COMPRA" else curr_v - (spread_val / 2)
                    
                    # 6. RISK MANAGEMENT
                    rischio_euro = current_balance * (current_risk / 100)
                    distanza_sl = entry_with_spread * 0.002 # Stop Loss fisso 0.2%
                    inv_effettivo_calcolato = rischio_euro / (distanza_sl / entry_with_spread)
                    
                    sl_prezzo = entry_with_spread - distanza_sl if s_action == "COMPRA" else entry_with_spread + distanza_sl
                    tp_prezzo = entry_with_spread + (distanza_sl * 1.5) if s_action == "COMPRA" else entry_with_spread - (distanza_sl * 1.5)

                    # 7. ESECUZIONE
                    iq_order_id = "SIMULATED"
                    stato_iniziale = "In Corso"
                    mercato_aperto = is_market_open(label)

                    if not mercato_aperto:
                        stato_iniziale = "⛔ CHIUSO"
                    elif api_conn and api_conn.check_connect():
                        side_iq = "buy" if s_action == "COMPRA" else "sell"
                        leverage_eff = get_dynamic_leverage(api_conn, iq_ticker, instrument_type)
                        
                        check, order_id = api_conn.buy_order(
                            instrument_type=instrument_type, 
                            instrument_id=iq_ticker.upper(),
                            side=side_iq,
                            amount=inv_effettivo_calcolato,
                            leverage=leverage_eff,
                            type="market",
                            stop_loss_price=sl_prezzo,
                            take_profit_price=tp_prezzo
                        )
                        if check:
                            iq_order_id = str(order_id)
                        else:
                            stato_iniziale = f"❌ ERR API"

                    # 8. REGISTRAZIONE
                    new_sig = {
                        'DataOra': get_now_rome().strftime("%H:%M:%S"),
                        'Asset': label, 
                        'Direzione': s_action, 
                        'Prezzo': p_fmt.format(entry_with_spread), 
                        'TP': p_fmt.format(tp_prezzo), 
                        'SL': p_fmt.format(sl_prezzo), 
                        'Stato': stato_iniziale,
                        'Investimento €': f"{inv_effettivo_calcolato:.2f}",
                        'Risultato €': "0.00",
                        'Costo Spread €': f"{spread_val:.5f}",
                        'Stato_Prot': "Iniziale",
                        'IQ_ID': iq_order_id
                    }

                    st.session_state['signal_history'] = pd.concat([pd.DataFrame([new_sig]), hist], ignore_index=True)
                    st.session_state['last_alert'] = new_sig
                    save_history_permanently()
  
                    telegram_text = f"{'🟢' if s_action == 'COMPRA' else '🔴'} *{s_action}* {label}\nPrice: {new_sig['Prezzo']}\nTP: {new_sig['TP']}"
                    send_telegram_msg(telegram_text)

        except Exception as e:
            debug_list.append(f"❌ {label} Err: {str(e)}")
            continue

    st.session_state['sentinel_logs'] = debug_list
    st.session_state['last_scan_status'] = f"✅ Scan OK: {get_now_rome().strftime('%H:%M:%S')}"

def display_performance_stats():
    if st.session_state['signal_history'].empty: return
    df = st.session_state['signal_history']
    conclusi = df[df['Stato'].str.contains('TARGET|STOP|DINAMICO', na=False)]
    if not conclusi.empty:
        vittorie = len(conclusi[conclusi['Stato'] == '✅ TARGET'])
        wr = (vittorie / len(conclusi)) * 100
        st.sidebar.write(f"📊 **Win Rate**: {wr:.1f}% ({vittorie}/{len(conclusi)})")

def get_equity_data():
    initial_balance = st.session_state.get('balance_val', 1000)
    equity_curve = [initial_balance]
    if st.session_state['signal_history'].empty: return pd.Series(equity_curve)
    
    df_conclusi = st.session_state['signal_history'][st.session_state['signal_history']['Stato'].str.contains('TARGET|STOP|DINAMICO', na=False)]
    df_sorted = df_conclusi.iloc[::-1]
    
    current_bal = initial_balance
    for _, row in df_sorted.iterrows():
        try:
            net_profit = float(str(row['Risultato €']).replace(',', '.'))
            current_bal += net_profit
            equity_curve.append(current_bal)
        except: continue
    return pd.Series(equity_curve)

# --- INIZIALIZZAZIONE SESSION STATE ---
if 'signal_history' not in st.session_state: st.session_state['signal_history'] = load_history_from_csv()
if 'sentinel_logs' not in st.session_state: st.session_state['sentinel_logs'] = []
if 'last_alert' not in st.session_state: st.session_state['last_alert'] = None
if 'last_scan_status' not in st.session_state: st.session_state['last_scan_status'] = "In attesa..."
if 'iq_api' not in st.session_state: st.session_state['iq_api'] = None

# --- SIDEBAR LOGIN ---
st.sidebar.header("🔑 IQ Option Login")
default_email = st.secrets.get("iq_option", {}).get("email", "")
default_pass = st.secrets.get("iq_option", {}).get("password", "")
email = st.sidebar.text_input("Email", value=default_email)
password = st.sidebar.text_input("Password", type="password", value=default_pass)
tipo_conto = st.sidebar.selectbox("Tipo Conto", ["PRACTICE", "REAL"])

if st.sidebar.button("Connetti IQ Option"):
    if IQ_Option:
        api = IQ_Option(email, password)
        check, reason = api.connect()
        if check:
            api.change_balance(tipo_conto)
            st.session_state['iq_api'] = api
            st.sidebar.success("✅ Connesso")
        else:
            st.sidebar.error(f"❌ Errore: {reason}")
    else:
        st.sidebar.error("Libreria API non disponibile")

# --- SIDEBAR SETTINGS ---
st.sidebar.subheader("🛠 Configurazione")
selected_label = st.sidebar.selectbox("**Asset Analisi**", list(asset_map.keys()))
pair = asset_map[selected_label]['yf']
balance = st.sidebar.number_input("**Conto Start (€)**", value=float(st.session_state.get('balance_val', 1000.0)), key="balance_val")
risk_pc = st.sidebar.slider("**Rischio %**", 0.5, 5.0, 2.0, step=0.5, key="risk_val")

st.sidebar.subheader("🛡️ Trailing Stop")
st.session_state['trailing_be_val'] = st.sidebar.slider("Pareggio (BE) %", 0.1, 1.0, 0.4)
st.session_state['trailing_safe_val'] = st.sidebar.slider("Sicurezza %", 0.5, 2.0, 0.8)
st.session_state['trailing_trend_val'] = st.sidebar.slider("Trend %", 1.0, 5.0, 1.4)

st.sidebar.markdown("---")
equity_series = get_equity_data()
current_equity = equity_series.iloc[-1]
st.sidebar.metric("Equity Attuale", f"€ {current_equity:.2f}")
display_performance_stats()

# LOGS SIDEBAR
with st.sidebar.expander("🔍 Sentinel Logs", expanded=True):
    for log in st.session_state.get('sentinel_logs', []):
        st.caption(log)

# RESET
with st.sidebar.popover("🗑️ Reset Dati"):
    if st.button("🔥 CANCELLA TUTTO"):
        st.session_state['signal_history'] = pd.DataFrame(columns=['DataOra', 'Asset', 'Direzione', 'Prezzo', 'SL', 'TP', 'Stato', 'Investimento €', 'Risultato €', 'Costo Spread €', 'Stato_Prot', 'IQ_ID'])
        save_history_permanently() 
        st.rerun()

# --- ESECUZIONE SENTINEL ---
if st.session_state.get('iq_api'):
    api = st.session_state['iq_api']
    if not api.check_connect(): api.connect()
    update_signal_outcomes(api)
    run_sentinel(api)
else:
    st.sidebar.warning("⚠️ Sentinel in pausa (API disconnessa)")

# --- ALERT POPUP ---
if st.session_state.get('last_alert'):
    if 'alert_notified' not in st.session_state:
        play_notification_sound()
        st.session_state['alert_notified'] = True
    alert = st.session_state['last_alert']
    color = "#00ffcc" if alert['Direzione'] == 'COMPRA' else "#ff4b4b"
    st.markdown(f"""
        <div style="border: 2px solid {color}; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
            <h2 style="color:{color}; margin:0;">{alert['Direzione']} {alert['Asset']}</h2>
            <p>Prezzo: {alert['Prezzo']} | TP: {alert['TP']}</p>
        </div>
    """, unsafe_allow_html=True)
    if st.button("Chiudi Alert"):
        st.session_state['last_alert'] = None
        st.rerun()

# --- MAIN DASHBOARD ---
st.title("📈 Forex Momentum AI")
st.info(f"Monitoraggio attivo su {len(asset_map)} asset.")

# CURRENCY STRENGTH
st.subheader("⚡ Currency Strength")
s_data = get_currency_strength()
if not s_data.empty:
    cols = st.columns(len(s_data))
    for i, (curr, val) in enumerate(s_data.items()):
        color = "#00ffcc" if val > 0.1 else ("#ff4b4b" if val < -0.1 else "white")
        cols[i].markdown(f"<h4 style='text-align:center; color:{color}'>{curr}<br>{val:.2f}%</h4>", unsafe_allow_html=True)

st.markdown("---")

# GRAFICO ASSET SELEZIONATO
st.subheader(f"📊 Analisi {selected_label}")
df_graph = yf.download(pair, period="1d", interval="1m", progress=False)

if not df_graph.empty:
    if isinstance(df_graph.columns, pd.MultiIndex): df_graph.columns = df_graph.columns.get_level_values(0)
    df_graph.columns = [str(c).lower() for c in df_graph.columns]
    
    p_df = df_graph.tail(150).copy()
    bb = ta.bbands(p_df['close'], length=20, std=2)
    p_df['rsi'] = ta.rsi(p_df['close'], length=14)
    adx_df = ta.adx(p_df['high'], p_df['low'], p_df['close'])
    
    # Unione dati per plot
    if bb is not None: 
        p_df = pd.concat([p_df, bb], axis=1)
        col_upper = bb.columns[2]
        col_lower = bb.columns[0]
    
    # Grafico
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=p_df.index, open=p_df['open'], high=p_df['high'], low=p_df['low'], close=p_df['close'], name="Price"), row=1, col=1)
    if bb is not None:
        fig.add_trace(go.Scatter(x=p_df.index, y=p_df[col_upper], line=dict(color='rgba(255,255,255,0.3)'), name="BB Up"), row=1, col=1)
        fig.add_trace(go.Scatter(x=p_df.index, y=p_df[col_lower], line=dict(color='rgba(255,255,255,0.3)'), name="BB Low"), row=1, col=1)
    fig.add_trace(go.Scatter(x=p_df.index, y=p_df['rsi'], line=dict(color='yellow'), name="RSI"), row=2, col=1)
    fig.add_hline(y=70, row=2, col=1, line_dash="dot", line_color="red")
    fig.add_hline(y=30, row=2, col=1, line_dash="dot", line_color="green")
    
    fig.update_layout(height=500, xaxis_rangeslider_visible=False, template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

    # METRICHE IN BASSO (CORRETTO IL BUG PRECEDENTE)
    curr_p = p_df['close'].iloc[-1]
    curr_rsi = p_df['rsi'].iloc[-1]
    curr_adx = adx_df.iloc[-1, 0] if adx_df is not None else 0

    m1, m2, m3 = st.columns(3)
    _, p_fmt, _, _ = get_asset_params(selected_label)
    m1.metric("Prezzo", p_fmt.format(curr_p))
    m2.metric("RSI (14)", f"{curr_rsi:.1f}")
    m3.metric("ADX Trend", f"{curr_adx:.1f}")
    
    st.caption(f"Divergenza: {detect_divergence(p_df)}")

# TABELLA STORICO
st.markdown("---")
st.subheader("📜 Operazioni")
if not st.session_state['signal_history'].empty:
    st.dataframe(st.session_state['signal_history'].style.map(style_status, subset=['Stato', 'Risultato €']), use_container_width=True, hide_index=True)
else:
    st.info("Nessuna operazione registrata.")
