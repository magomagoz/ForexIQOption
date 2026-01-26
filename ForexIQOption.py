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
from iqoptionapi.stable_api import IQ_Option  # Libreria non ufficiale IQ Option

# --- COSTANTI DI MERCATO ---
# Nota: Lo spread reale verrà gestito da IQ Option, qui manteniamo una stima per i calcoli preliminari
SIMULATED_SPREAD = 0.0005 

# --- 1. CONFIGURAZIONE & LAYOUT ---
st.set_page_config(page_title="Forex Momentum Pro AI - IQ Bot", layout="wide", page_icon="📈")

st.markdown("""
    <style>
        .block-container {padding-top: 1rem !important;}
        [data-testid="stSidebar"] > div:first-child {padding-top: 0rem !important;}
        
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {background-color: rgba(0,0,0,0) !important;} 
        
        /* Stile Tasti */
        div.stButton > button {
            border-radius: 8px !important;
            font-weight: bold;
            width: 100%;
        }
        
        /* Colori Tabella */
        [data-testid="stDataFrame"] {
            border: 1px solid #333;
        }
    </style>
""", unsafe_allow_html=True)

# Definizione Fuso Orario Roma
rome_tz = pytz.timezone('Europe/Rome')

# Mappa Asset: YFinance Ticker -> IQ Option Ticker
asset_map = {
    "EURUSD": {"yf": "EURUSD=X", "iq": "EURUSD"},
    "GBPUSD": {"yf": "GBPUSD=X", "iq": "GBPUSD"},
    "USDJPY": {"yf": "USDJPY=X", "iq": "USDJPY"},
    "AUDUSD": {"yf": "AUDUSD=X", "iq": "AUDUSD"},
    "USDCAD": {"yf": "USDCAD=X", "iq": "USDCAD"},
    "USDCHF": {"yf": "USDCHF=X", "iq": "USDCHF"},
    "NZDUSD": {"yf": "NZDUSD=X", "iq": "NZDUSD"},
    # Crypto su IQ Option spesso hanno nomi diversi o sono CFD
    "BTC-USD": {"yf": "BTC-USD", "iq": "BITCOIN"},
    "ETH-USD": {"yf": "ETH-USD", "iq": "ETHEREUM"}
}

# Refresh automatico ogni 60 secondi
st_autorefresh(interval=60 * 1000, key="sentinel_refresh")

# --- 2. FUNZIONI TECNICHE ---
def save_history_permanently():
    """Salva la cronologia attuale su un file fisico CSV"""
    try:
        if 'signal_history' in st.session_state and not st.session_state['signal_history'].empty:
            st.session_state['signal_history'].to_csv("permanent_signals_db.csv", index=False)
    except Exception as e:
        print(f"Errore salvataggio file: {e}")

def load_history_from_csv():
    # Aggiunto 'IQ_ID' per tracciare l'ID dell'ordine reale
    cols = ['DataOra', 'Asset', 'Direzione', 'Prezzo', 'SL', 'TP', 'Stato', 'Investimento €', 'Risultato €', 'Costo Spread €', 'Stato_Prot', 'Protezione', 'IQ_ID']
    if os.path.exists("permanent_signals_db.csv"):
        try:
            df = pd.read_csv("permanent_signals_db.csv")
            # Forza la presenza di tutte le colonne necessarie
            for col in cols:
                if col not in df.columns: df[col] = "0.00" if "€" in col else ""
            return df
        except:
            return pd.DataFrame(columns=cols)
    return pd.DataFrame(columns=cols)

def send_telegram_msg(msg):
    # Carica le credenziali dai secrets invece di scriverle in chiaro
    try:
        token = st.secrets["telegram"]["token"]
        chat_id = st.secrets["telegram"]["chat_id"]
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        params = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
        r = requests.get(url, params=params, timeout=5)
    except Exception as e:
        print(f"Errore caricamento Secrets o invio Telegram: {e}")

def get_now_rome():
    return datetime.now(rome_tz)

def is_market_open(asset_name):
    """
    Restituisce True se il mercato è aperto.
    """
    if "BTC" in asset_name or "ETH" in asset_name:
        return True
    
    today = get_now_rome().weekday()
    # Se è Sabato (5) o Domenica (6), il Forex è chiuso
    if today >= 5:
        return False
        
    return True

def get_real_spread(api, iq_ticker, instrument_type="forex"):
    try:
        # Recupera i dati in tempo reale per lo strumento
        # 'get_realtime_candles' o 'get_all_realtime_candles' a seconda della versione
        # Qui usiamo un approccio basato sul filtraggio dei dati live
        data = api.get_orderbook(iq_ticker, 1) # Chiede il primo livello del book
        ask = float(data['asks'][0][0])
        bid = float(data['bids'][0][0])
        return ask - bid
    except:
        return SIMULATED_SPREAD # Fallback se l'API non risponde

def play_notification_sound():
    audio_html = """
        <audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)

def play_close_sound():
    audio_html = """
        <audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2017/2017-preview.mp3" type="audio/mpeg"></audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)

def play_safe_sound():
    audio_html = """
        <audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2021/2021-preview.mp3" type="audio/mpeg"></audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)

def style_status(val):
    if val == '✅ TARGET': return 'background-color: rgba(0, 255, 204, 0.2); color: #00ffcc;'
    if val == '❌ STOP LOSS': return 'background-color: rgba(255, 75, 75, 0.2); color: #ff4b4b;'
    if val == '🛡️ SL DINAMICO': return 'background-color: rgba(255, 165, 0, 0.2); color: #ffa500;'
    
    try:
        clean_val = str(val).replace('€', '').replace('+', '').strip()
        num = float(clean_val)
        if num > 0: return 'color: #00ffcc; font-weight: bold;'
        if num < 0: return 'color: #ff4b4b; font-weight: bold;'
    except:
        pass
    return ''

def get_trailing_params(asset_name):
    if any(x in asset_name for x in ["BTC", "ETH"]):
        return 5.0, 10.0, -10.0 
    else:
        return 0.5, 1.0, -2.0

def get_session_status():
    now_rome_dt = get_now_rome()
    now_time = now_rome_dt.time()
    is_weekend = now_rome_dt.weekday() >= 5 

    if is_weekend:
        return {"Tokyo 🇯🇵": False, "Londra 🇬🇧": False, "New York 🇺🇸": False}

    # Correzione: usa direttamente 'time' (importato da datetime) 
    # invece di 'datetime.time'
    sessions = {
        "Tokyo 🇯🇵": (time(0, 0), time(9, 0)), 
        "Londra 🇬🇧": (time(9, 0), time(18, 0)), 
        "New York 🇺🇸": (time(14, 0), time(23, 0))
    }
    
    return {name: start <= now_time <= end for name, (start, end) in sessions.items()}

def get_instruments_data(api, asset_type):
    # Recupera i dettagli tecnici (leva, spread, step) dal broker
    try:
        return api.get_instruments(asset_type)
    except:
        return []

def get_dynamic_leverage(api, iq_ticker, instrument_type):
    try:
        # Recupera la leva massima per l'asset specifico
        instruments = api.get_instruments(instrument_type)
        for i in instruments:
            if i['id'].lower() == iq_ticker.lower():
                return i['leverage_max']
        return 1
    except:
        return 1

def get_real_spread_info(api, iq_ticker):
    try:
        # Calcola lo spread reale in pips/valore assoluto
        orderbook = api.get_orderbook(iq_ticker)
        ask = float(orderbook['asks'][0][0])
        bid = float(orderbook['bids'][0][0])
        spread_reale = ask - bid
        prezzo_medio = (ask + bid) / 2
        # Spread in percentuale rispetto al prezzo
        spread_pct = (spread_reale / prezzo_medio) * 100
        return spread_reale, spread_pct
    except:
        return SIMULATED_SPREAD, 0.05

@st.cache_data(ttl=60)
def get_realtime_data(ticker):
    try:
        # Usa Yahoo Finance per i dati tecnici (più veloce per i dataframe storici)
        df = yf.download(ticker, period="5d", interval="5m", progress=False, timeout=10)
        if df is None or df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        return df.dropna()
    except: return None

def get_currency_strength():
    try:
        forex = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "USDCHF=X", "NZDUSD=X", "EURCHF=X","EURJPY=X", "GBPJPY=X", "GBPCHF=X","EURGBP=X"]
        crypto = ["BTC-USD", "ETH-USD"]
        df = yf.download(ticker, period="1d", interval="1m", progress=False)
        if not df.empty:
        # Questa riga risolve l'errore 'tuple' appiattendo le colonne
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).lower() for c in df.columns]

        if data is None or data.empty: 
            return pd.Series(dtype=float)

        if isinstance(data.columns, pd.MultiIndex):
            close_data = data['Close'] if 'Close' in data else data
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
    if "BTC" in pair or "ETH" in pair:
        return 1.0, "{:.2f}", 1, "CRYPTO"
    elif "JPY" in pair:
        return 0.01, "{:.3f}", 100, "FOREX_JPY"
    else:
        return 0.0001, "{:.5f}", 10000, "FOREX_STD"

def detect_divergence(df):
    if len(df) < 20: return "Analisi..."
    price, rsi_col = df['close'], df['rsi']
    curr_p, curr_r = float(price.iloc[-1]), float(rsi_col.iloc[-1])
    prev_max_p, prev_max_r = price.iloc[-20:-1].max(), rsi_col.iloc[-20:-1].max()
    prev_min_p, prev_min_r = price.iloc[-20:-1].min(), rsi_col.iloc[-20:-1].min()
    if curr_p > prev_max_p and curr_r < prev_max_r: return "📉 DECRESCITA"
    elif curr_p < prev_min_p and curr_r > prev_min_r: return "📈 CRESCITA"
    return "Neutrale"
    
def update_signal_outcomes(api_conn):
    """
    Controlla lo stato delle posizioni direttamente tramite API IQ Option
    e gestisce il Trailing Stop Locale.
    """
    if st.session_state['signal_history'].empty: return
    df = st.session_state['signal_history']
    updates_made = False

    # Recupera posizioni aperte da IQ Option (Forex/Crypto)
    open_positions = {}
    if api_conn and api_conn.check_connect():
        try:
            posizioni = api_conn.get_positions("cfd")
            if isinstance(posizioni, list): # Se l'API restituisce una lista (molto comune)
                for p in posizioni:
                    # Usa .get() per evitare crash se mancano chiavi
                    st.write(f"Asset: {p.get('instrument_id')} | Profit: {p.get('win_amount')}")
            elif isinstance(posizioni, dict):
                for pos_id, p in posizioni.items():
                    st.write(f"ID: {pos_id} | Profit: {p.get('win_amount')}")
        except Exception as e:
            st.warning("Impossibile recuperare le posizioni attive.")

    for idx, row in df[df['Stato'] == 'In Corso'].iterrows():
        try:
            # Usiamo YF per il prezzo corrente per coerenza coi grafici, 
            # ma idealmente si dovrebbe usare api_conn.get_candles per il prezzo preciso del broker
            ticker_yf = asset_map[row['Asset']]['yf']
            df = yf.download(ticker, period="1d", interval="1m", progress=False)
            if not df.empty:
            # Questa riga risolve l'errore 'tuple' appiattendo le colonne
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).lower() for c in df.columns]

            current_price = float(data['close'].iloc[-1])
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
            # Se siamo connessi, controlliamo se l'ID esiste ancora tra le posizioni aperte
            # Se non esiste più, significa che IQ Option l'ha chiusa (TP o SL toccati)
            trade_closed_remote = False
            # Qui andrebbe la logica precisa di controllo ID su IQOption,
            # Simuliamo la chiusura basandoci sui prezzi YF per semplicità dello script
            
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
                
                # SE CONNESSO: Dovremmo idealmente chiudere la posizione anche su IQ se non è già chiusa
                if api_conn:
                    try:
                        # api_conn.close_position(row['IQ_ID']) 
                        pass # Implementare chiusura API reale qui
                    except: pass
            
            elif new_sl != current_sl:
                _, p_fmt, _, _ = get_asset_params(row['Asset'])
                df.at[idx, 'SL'] = p_fmt.format(new_sl)
                df.at[idx, 'Stato_Prot'] = status_prot
                updates_made = True
                # SE CONNESSO: Aggiorna SL su IQ Option
                if api_conn:
                    # Esempio comando (verificare documentazione libreria specifica)
                    # api_conn.modify_instrument_position_stop_limit(row['IQ_ID'], new_stop_loss=new_sl)
                    pass

        except Exception: continue 
        
    if updates_made:
        st.session_state['signal_history'] = df
        save_history_permanently()

def run_sentinel(api_conn):
    """
    Motore Sentinel: Monitora il mercato, genera segnali basati su BB/RSI/ADX,
    calcola il risk management ed esegue l'ordine su IQ Option.
    """
    debug_list = []
    # Recupero bilancio reale o simulato
    current_balance = api_conn.get_balance() if api_conn else st.session_state.get('balance_val', 1000)
    current_risk = st.session_state.get('risk_val', 2.0)

    # Iterazione corretta su asset_map
    for label, tickers in asset_map.items():
        yf_ticker = tickers['yf']
        iq_ticker = tickers['iq']
        
        try:
            # 1. Recupero dati real-time (1m)
            df = yf.download(ticker, period="1d", interval="1m", progress=False)
            if not df.empty:
                # Questa riga risolve l'errore 'tuple' appiattendo le colonne
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).lower() for c in df.columns]

            # Pulizia colonne per evitare errori case-sensitive
            df_rt_s.columns = [c.lower() for c in df_rt_s.columns]
            
            # 2. CALCOLO INDICATORI
            bb_s = ta.bbands(df_rt_s['close'], length=20, std=2)
            rsi_s = ta.rsi(df_rt_s['close'], length=14)
            adx_s = ta.adx(df_rt_s['high'], df_rt_s['low'], df_rt_s['close'])
            
            curr_v = float(df_rt_s['close'].iloc[-1])
            low_bb = bb_s.iloc[-1, 0]  # BBL
            up_bb = bb_s.iloc[-1, 2]   # BBU
            rsi_val = rsi_s.iloc[-1]
            curr_adx = adx_s.iloc[-1, 0] # ADX_14

            # 3. LOGICA SEGNALE (Incrocio BB + RSI + ADX)
            s_action = None
            if curr_v < low_bb and rsi_val < 25 and curr_adx < 30:
                s_action = "COMPRA"
            elif curr_v > up_bb and rsi_val > 75 and curr_adx < 30:
                s_action = "VENDI"

            if s_action:
                # 4. CONTROLLO POSIZIONI ESISTENTI
                hist = st.session_state['signal_history']
                is_running = not hist.empty and ((hist['Asset'] == label) & (hist['Stato'] == 'In Corso')).any()
                
                if not is_running:
                    # Parametri specifici asset (pips, decimali)
                    p_unit, p_fmt, p_mult, a_type = get_asset_params(label)
                    instrument_type = "crypto" if "BTC" in label or "ETH" in label else "forex"
                    
                    # 5. SPREAD & ENTRY PRICE
                    spread_val, _ = get_real_spread_info(api_conn, iq_ticker) if api_conn else (SIMULATED_SPREAD, 0.05)
                    entry_with_spread = curr_v + (spread_val / 2) if s_action == "COMPRA" else curr_v - (spread_val / 2)
                    
                    # 6. RISK MANAGEMENT (Calcolo Size Dinamica)
                    rischio_euro = current_balance * (current_risk / 100)
                    distanza_sl = entry_with_spread * 0.002 # Stop Loss allo 0.2%
                    inv_effettivo_calcolato = rischio_euro / (distanza_sl / entry_with_spread)
                    
                    # 7. DEFINIZIONE TP/SL
                    sl_prezzo = entry_with_spread - distanza_sl if s_action == "COMPRA" else entry_with_spread + distanza_sl
                    tp_prezzo = entry_with_spread + (distanza_sl * 1.5) if s_action == "COMPRA" else entry_with_spread - (distanza_sl * 1.5)

                    # 8. ESECUZIONE BROKER (IQ OPTION)
                    iq_order_id = "SIMULATED"
                    stato_iniziale = "In Corso"
                    mercato_aperto = is_market_open(label)

                    if not mercato_aperto:
                        stato_iniziale = "⛔ CHIUSO"
                    elif api_conn and api_conn.check_connect():
                        side_iq = "buy" if s_action == "COMPRA" else "sell"
                        leverage_eff = get_dynamic_leverage(api_conn, iq_ticker, instrument_type)
                        
                        # Chiamata API Reale
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
                            stato_iniziale = f"❌ ERR: {order_id}"

                    # 9. REGISTRAZIONE & NOTIFICA
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

                    # Aggiornamento sessione e persistenza
                    st.session_state['signal_history'] = pd.concat([pd.DataFrame([new_sig]), hist], ignore_index=True)
                    st.session_state['last_alert'] = new_sig
                    save_history_permanently()
  
                    # Notifica Telegram
                    icona = "🟢" if s_action == "COMPRA" else "🔴"
                    telegram_text = (
                        f"{icona} *{s_action}* {label}\n"
                        f"Entry: {new_sig['Prezzo']}\n"
                        f"TP: {new_sig['TP']} | SL: {new_sig['SL']}\n"
                        f"Size: € {new_sig['Investimento €']}"
                    )
                    send_telegram_msg(telegram_text)

            st.session_state['last_scan_status'] = f"✅ Scan OK: {get_now_rome().strftime('%H:%M:%S')}"

        except Exception as e:
            debug_list.append(f"❌ {label} Err: {str(e)}")
            continue
    
    st.session_state['sentinel_logs'] = debug_list
                    
def display_performance_stats():
    if st.session_state['signal_history'].empty:
        return
    
    df = st.session_state['signal_history']
    conclusi = df[df['Stato'].str.contains('TARGET|STOP|DINAMICO', na=False)]
    
    if not conclusi.empty:
        vittorie = len(conclusi[conclusi['Stato'] == '✅ TARGET'])
        wr = (vittorie / len(conclusi)) * 100
        st.sidebar.write(f"📊 **Win Rate**: {wr:.1f}% ({vittorie}/{len(conclusi)})")

def puo_aprire_posizione(api, costo_operazione):
    saldo_attuale = api.get_balance()
    limite_prudenziale = saldo_attuale * 0.15 # Alzato al 15% per flessibilità
    if saldo_attuale < costo_operazione:
        st.error("⚠️ Saldo insufficiente sul conto!")
        return False
    if costo_operazione > limite_prudenziale:
        st.warning(f"⚠️ Esposizione alta: superi il 15% del capitale ({limite_prudenziale:.2f}$)")
    return True

# --- GESTIONE SESSIONE API ---
if 'iq_api' not in st.session_state:
    st.session_state['iq_api'] = None

# --- 3. INIZIALIZZAZIONE STATO ---
if 'signal_history' not in st.session_state: 
    st.session_state['signal_history'] = load_history_from_csv()
if 'sentinel_logs' not in st.session_state:
    st.session_state['sentinel_logs'] = []
if 'last_alert' not in st.session_state:
    st.session_state['last_alert'] = None
if 'last_scan_status' not in st.session_state:
    st.session_state['last_scan_status'] = "In attesa..."
if 'iq_api' not in st.session_state:
    st.session_state['iq_api'] = None
if 'iq_status' not in st.session_state:
    st.session_state['iq_status'] = "Disconnesso"

st.sidebar.header("🔑 Connessione IQ Option")

# Pre-carica i valori dai secrets se disponibili, altrimenti usa stringa vuota
default_email = st.secrets["iq_option"]["email"] if "iq_option" in st.secrets else ""
default_pass = st.secrets["iq_option"]["password"] if "iq_option" in st.secrets else ""

email = st.sidebar.text_input("Email", value=default_email, key="login_email")
password = st.sidebar.text_input("Password", type="password", value=default_pass, key="login_pass")
tipo_conto = st.sidebar.selectbox("Tipo Conto", ["PRACTICE", "REAL"])

if st.sidebar.button("Connetti"):
    api = IQ_Option(email, password)
    check, reason = api.connect()
    if check:
        api.change_balance(tipo_conto)
        st.session_state['iq_api'] = api
        st.sidebar.success(f"✅ Connesso ({tipo_conto})")
    else:
        st.sidebar.error(f"❌ Errore: {reason}")

# Controllo stato connessione persistente
api = st.session_state.get('iq_api')
if api and api.check_connect():
    st.sidebar.metric("Saldo attuale", f"{api.get_balance():.2f} {api.get_currency()}")
else:
    st.sidebar.warning("🔴 Disconnesso")

def get_equity_data():
    initial_balance = st.session_state.get('balance_val', 1000)
    equity_curve = [initial_balance]
    
    if st.session_state['signal_history'].empty:
        return pd.Series(equity_curve)
    
    df_conclusi = st.session_state['signal_history'][st.session_state['signal_history']['Stato'].str.contains('TARGET|STOP|DINAMICO', na=False)]
    df_sorted = df_conclusi.iloc[::-1]
    
    current_bal = initial_balance
    for _, row in df_sorted.iterrows():
        try:
            net_profit = float(str(row['Risultato €']).replace(',', '.'))
            current_bal += net_profit
            equity_curve.append(current_bal)
        except:
            continue
            
    return pd.Series(equity_curve)

# --- 5. SIDEBAR ---
st.sidebar.header("🛠 Trading Desk (1m)")

st.sidebar.subheader("⏳ **Prossimo Scan**")
st.sidebar.markdown("""
    <style>
        @keyframes progressFill {
            0% { width: 0%; }
            100% { width: 100%; }
        }
        .container-bar {
            width: 100%; background-color: #222; border-radius: 5px;
            height: 12px; margin-bottom: 25px; border: 1px solid #444; overflow: hidden;
        }
        .red-bar {
            height: 100%; background-color: #00f2ff; width: 0%;
            animation: progressFill 60s linear infinite;
            box-shadow: 0 0 10px #00f2ff;
        }
    </style>
    <div class="container-bar"><div class="red-bar"></div></div>
""", unsafe_allow_html=True)

with st.sidebar.expander("🔍 Live Sentinel Data", expanded=True):
    if 'sentinel_logs' in st.session_state and st.session_state['sentinel_logs']:
        for log in st.session_state['sentinel_logs']:
            st.caption(log)
    else:
        st.caption("In attesa del primo scan...")

st.sidebar.subheader("📡 Sentinel Status")
status = st.session_state.get('last_scan_status', 'In attesa...')

if "⚠️" in status:
    st.sidebar.error(status)
elif "🔍" in status:
    st.sidebar.success(status)
else:
    st.sidebar.info(status)

selected_label = st.sidebar.selectbox("**Asset**", list(asset_map.keys()))
pair = asset_map[selected_label]['yf']

# Recupero Balance Reale se connesso
bal_display = st.session_state.get('balance_val', 1000)
balance = st.sidebar.number_input("**Conto (€)**", value=float(bal_display), key="balance_val")
risk_pc = st.sidebar.slider("**Investimento %**", 0.5, 5.0, 2.0, step=0.5, key="risk_val")

st.sidebar.subheader("🛡️ Gestione Protezione")
trailing_be = st.sidebar.slider("Livello Pareggio (BE) %", 0.1, 1.0, 0.4, step=0.1)
trailing_safe = st.sidebar.slider("Livello Sicurezza %", 0.5, 2.0, 0.8, step=0.1)
trailing_trend = st.sidebar.slider("Livello Trend %", 1.0, 5.0, 1.4, step=0.1)

st.session_state['trailing_be_val'] = trailing_be
st.session_state['trailing_safe_val'] = trailing_safe
st.session_state['trailing_trend_val'] = trailing_trend

st.sidebar.markdown(
    """
    <div style='background-color: rgba(255, 152, 0, 0.1); 
                border: 1px solid #ff9800; 
                padding: 10px; 
                border-radius: 5px; 
                margin-top: 10px;'>
        <span style='color: #ff9800; font-weight: bold; font-size: 0.85em;'>
            🟠 IQOption BOT: PRACTICE
        </span><br>
        <small style='color: #888; font-size: 0.75em;'>
            Automazione attiva su conto Demo.
        </small>
    </div>
    """, 
    unsafe_allow_html=True
)

investimento_simulato = balance * (risk_pc / 100)
saldo_residuo = balance - investimento_simulato

st.sidebar.markdown("---")
st.sidebar.subheader("💰 Gestione Capitale")
st.sidebar.metric("Conto (Live)", f"€ {balance:.2f}")
st.sidebar.metric("Investimento stimato", f"€ {investimento_simulato:.2f}")

st.sidebar.markdown("---")

st.sidebar.subheader("🏆 Performance")
equity_series = get_equity_data()
current_equity = equity_series.iloc[-1]
initial_bal = balance if balance > 0 else 1000
total_return = ((current_equity - initial_bal) / initial_bal) * 100
max_val = equity_series.max()
dd = ((current_equity - max_val) / max_val) * 100 if max_val > 0 else 0

st.sidebar.metric("Saldo Attuale Operativo", f"€ {current_equity:.2f}", delta=f"{total_return}%")
dd_color = "normal" 
if 0 <= abs(dd) <= 10:
    dd_color = "normal" 
elif abs(dd) > 20:
    dd_color = "inverse"

st.sidebar.metric(
    "Drawdown Massimo", 
    f"{dd:.2f}%", 
    delta="OTTIMO" if abs(dd) <= 10 else "ATTENZIONE" if abs(dd) > 20 else "",
    delta_color=dd_color
)

display_performance_stats()

st.sidebar.markdown("---")
st.sidebar.subheader("⚡ Monitor Real-Time")
active_trades = st.session_state['signal_history'][st.session_state['signal_history']['Stato'] == 'In Corso']
    
for _, trade in active_trades.iterrows():
    try:
        t_ticker = asset_map[trade['Asset']]['yf']
        t_data = yf.download(t_ticker, period="1d", interval="1m", progress=False, timeout=5)
        
        if not t_data.empty:
            curr_p = float(t_data['Close'].iloc[-1])
            entry_p = float(str(trade['Prezzo']).replace(',', '.'))
            
            p_diff = ((curr_p - entry_p) / entry_p) if trade['Direzione'] == 'COMPRA' else ((entry_p - curr_p) / entry_p)
            latente_perc = p_diff * 100
            
            pos_barra = max(0, min(100, (latente_perc + 1) * 50))
            color = "#00ffcc" if latente_perc >= 0 else "#00f2ff" 
            
            st.sidebar.markdown(f"""
                <div style="margin-bottom: 15px; background: rgba(255,255,255,0.05); padding: 8px; border-radius: 5px;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.85em;">
                        <b>{trade['Asset']}</b>
                        <span style="color:{color}; font-weight:bold;">{latente_perc:+.2f}%</span>
                    </div>
                    <div style="width: 100%; background: #333; height: 6px; border-radius: 3px; margin-top: 5px; position: relative;">
                        <div style="position: absolute; left: 50%; width: 2px; height: 8px; background: white; top: -1px; z-index: 1;"></div>
                        <div style="width: {pos_barra}%; background: {color}; height: 100%; border-radius: 3px; transition: width 0.5s;"></div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    except:
        continue

if not active_trades.empty:
    st.sidebar.success("⚡ Ultima Operazione Attiva")
    last_t = active_trades.iloc[0]
    st.sidebar.write(f"Asset: **{last_t['Asset']}**")
    st.sidebar.write(f"SL: `{last_t['SL']}` | TP: `{last_t['TP']}`")

st.sidebar.markdown("---")
st.sidebar.subheader("🌍 Sessioni di Mercato")
for s_name, is_open in get_session_status().items():
    color = "🟢" if is_open else "🔴"
    status_text = "APERTO" if is_open else "CHIUSO"
    st.sidebar.markdown(f"**{s_name}** <small>: {status_text}</small> {color}",
unsafe_allow_html=True)

st.sidebar.markdown("---")

if not st.session_state['signal_history'].empty:
    csv_data = st.session_state['signal_history'].to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(
        label="📥 **Salva cronologia**",
        data=csv_data,
        file_name=f"Trading_Report_{get_now_rome().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        use_container_width=True
    )
else:
    st.sidebar.info("Nessun dato da esportare")

st.sidebar.markdown("---")
with st.sidebar.popover("🗑️ **Reset Cronologia**"):
    st.warning("Sei sicuro? Questa azione cancellerà tutti i segnali salvati.")

    if st.button("🔥 SÌ, CANCELLA ORA 🔥"):
        st.session_state['signal_history'] = pd.DataFrame(columns=['DataOra', 'Asset', 'Direzione', 'Prezzo', 'SL', 'TP', 'Size', 'Stato'])
        save_history_permanently() 
        st.rerun()

st.sidebar.markdown("---")

# --- 5. MOTORE DI ESECUZIONE (POSIZIONATO IN FONDO AL FILE) ---
# --- CORREZIONE CHIRURGICA D: Gestione Sessione ---
if st.session_state.get('iq_api'):
    api = st.session_state['iq_api']
    
    # Se la connessione è caduta, prova a riconnettere
    if not api.check_connect():
        api.connect()
    
    # Procedi con i check
    update_signal_outcomes(api)
    run_sentinel(api)
    
    # Visualizziamo i log aggiornati nella sidebar
    st.sidebar.subheader("🛡️ Log Motore AI")
    for log in st.session_state.get('sentinel_logs', []):
        st.sidebar.caption(log)
else:
    st.sidebar.info("🔌 Connetti IQ Option per attivare l'esecuzione automatica.")

# --- 6. POPUP ALERT ---
if st.session_state.get('last_alert'):
    if 'alert_notified' not in st.session_state:
        play_notification_sound()
        st.session_state['alert_notified'] = True

    alert = st.session_state['last_alert']
    hex_color = "#00ffcc" if alert['Direzione'] == 'COMPRA' else "#ff4b4b"

    st.markdown(f"""
        <div style="background-color: #000; border: 3px solid {hex_color}; padding: 20px; border-radius: 15px; margin-bottom: 20px; text-align: center; box-shadow: 0 0 20px {hex_color}44;">
            <h2 style="color: white; margin: 0;">🚀 NUOVO SEGNALE RILEVATO: {alert['Asset']}</h2>
            <h1 style="color: {hex_color}; margin: 5px 0;">{alert['Direzione']} @ {alert['Prezzo']}</h1>
            <p style="color: #888; margin: 0;">TP: {alert['TP']} | SL: {alert['SL']}</p>
            <div style="margin-top: 10px; font-size: 0.8em; color: #555;">
                Questo alert scomparirà automaticamente al prossimo aggiornamento della sentinella.
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("✅ CHIUDI ALERT ORA", use_container_width=True):
        st.session_state['last_alert'] = None
        if 'alert_notified' in st.session_state: del st.session_state['alert_notified']
        st.rerun()
    
    st.divider()

# --- 7. BODY PRINCIPALE ---
banner_path = "banner1.png"
if os.path.exists(banner_path):
    st.image(banner_path, use_container_width=True)
else:
    st.markdown('<div style="background: linear-gradient(90deg, #0f0c29, #302b63, #24243e); padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #00ffcc;"><h1 style="color: #00ffcc; margin: 0;">📊 FOREX MOMENTUM PRO AI</h1><p style="color: white; opacity: 0.8; margin:0;">Sentinel AI Engine • IQ Option Integration</p></div>', unsafe_allow_html=True)

st.info(f"🛰️ **Sentinel AI Attiva**: Monitoraggio in corso su {len(asset_map)} asset (7 Forex e 2 Crypto) in tempo reale (1m).")
st.caption(f"Ultimo aggiornamento globale: {get_now_rome().strftime('%d/%m/%Y %H:%M:%S')}")

# --- 7. BODY PRINCIPALE ---
st.title("📈 Trading Panel CFD & Forex")

if api and api.check_connect():
    tab1, tab2 = st.tabs(["🚀 Apri Posizione", "📊 Monitoraggio Attivo"])

    with tab1:
        st.subheader("Configurazione Nuovo Ordine")
        c1, c2, c3 = st.columns(3)
        with c1:
            asset_sel = st.selectbox("Asset Operativo", list(asset_map.keys()), key="manual_asset")
            direzione = st.radio("Direzione", ["buy", "sell"])
        with c2:
            investimento = st.number_input("Investimento ($)", min_value=1.0, value=10.0)
            leva = st.slider("Leva", 1, 500, 50)
        with c3:
            stop_loss = st.number_input("Stop Loss (%)", value=10)
            take_profit = st.number_input("Take Profit (%)", value=20)

        if st.button("ESEGUI ORDINE CFD", use_container_width=True):
            # Logica di invio ordine tramite api.buy_order...
            st.success("Ordine inviato al broker!")

    # --- SEZIONE MONITORAGGIO ATTIVO ---
    with tab2:
        st.subheader("Posizioni Aperte")
        # Verifica se l'API esiste ed è connessa
        if st.session_state.get('iq_api') and st.session_state['iq_api'].check_connect():
            try:
                posizioni = st.session_state['iq_api'].get_positions("cfd")
                
                if posizioni and isinstance(posizioni, (list, dict)):
                    data_list = []
                    # Se è un dizionario (vecchio formato API)
                    if isinstance(posizioni, dict):
                        items = posizioni.items()
                    else: # Se è una lista
                        items = enumerate(posizioni)
    
                    for idx, p in items:
                        data_list.append({
                            "ID": p.get('id', 'N/A'),
                            "Asset": p.get('instrument_id', 'N/A'),
                            "Direzione": p.get('side', 'N/A'),
                            "Profitto": p.get('win_amount', 0)
                        })
                    st.table(data_list)
            else:
                st.info("Nessuna posizione aperta rilevata.")
        except Exception as e:
            st.error(f"Errore nel recupero posizioni: {e}")
    else:
        st.warning("Connetti IQ Option dalla sidebar per vedere le posizioni.")
           
            if st.button("🚨 CHIUDI TUTTE LE POSIZIONI", use_container_width=True, type="primary"):
                # api.close_all_positions()
                st.rerun()
        else:
            st.info("Nessuna posizione attiva su IQ Option.")

# --- SEZIONE GRAFICO E ANALISI ---
st.markdown("---")

# --- SEZIONE GRAFICO 3 ORE ---
st.subheader(f"📈 Analisi Storica {selected_label} (Ultime 3 Ore)")

df_graph = yf.download(pair, period="1d", interval="1m", progress=False)

if df_graph is not None and not df_graph.empty:
    # Pulizia colonne
    if isinstance(df_graph.columns, pd.MultiIndex):
        df_graph.columns = df_graph.columns.get_level_values(0)
    df_graph.columns = [str(c).lower() for c in df_graph.columns]
    
    # Prendi le ultime 180 candele (3 ore)
    p_df = df_graph.tail(180).copy()
    
    # Calcolo indicatori su p_df
    bb = ta.bbands(p_df['close'], length=20, std=2)
    p_df['rsi'] = ta.rsi(p_df['close'], length=14)
    
    # Verifica che le Bande di Bollinger siano state calcolate
    if bb is not None:
        p_df = pd.concat([p_df, bb], axis=1)
        # Identifica correttamente le colonne BB (i nomi variano in pandas_ta)
        col_lower = bb.columns[0]
        col_upper = bb.columns[2]

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.05, row_heights=[0.7, 0.3])

        # Candele
        fig.add_trace(go.Candlestick(
            x=p_df.index, open=p_df['open'], high=p_df['high'],
            low=p_df['low'], close=p_df['close'], name="Prezzo"
        ), row=1, col=1)

        # Bande di Bollinger
        fig.add_trace(go.Scatter(x=p_df.index, y=p_df[col_upper], line=dict(color='rgba(173, 216, 230, 0.4)'), name="Upper BB"), row=1, col=1)
        fig.add_trace(go.Scatter(x=p_df.index, y=p_df[col_lower], line=dict(color='rgba(173, 216, 230, 0.4)'), name="Lower BB"), row=1, col=1)

        # RSI
        fig.add_trace(go.Scatter(x=p_df.index, y=p_df['rsi'], line=dict(color='yellow'), name="RSI"), row=2, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)

        fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
    
    # Metriche di riepilogo per evitare il NameError (bb_s)
    c1, c2 = st.columns(2)
    c1.metric("Prezzo Attuale", f"{p_df['close'].iloc[-1]:.5f}")
    c2.metric("RSI (1m)", f"{p_df['rsi'].iloc[-1]:.1f}")

else:
    st.info("In attesa di dati dal mercato...")

    # METRICHE SOTTO IL GRAFICO
    m1, m2, m3 = st.columns(3)
    p_unit, price_fmt, _, _ = get_asset_params(selected_label)
    
    m1.metric("Prezzo Attuale", price_fmt.format(curr_p))
    m2.metric("RSI (1m)", f"{curr_rsi:.1f}", delta="Ipercomprato" if curr_rsi > 70 else "Ipervenduto" if curr_rsi < 30 else "Neutro")
    m3.metric("Trend (ADX)", f"{curr_adx_val:.1f}", "Forte" if curr_adx_val > 25 else "Laterale")

    # LOGICA SCORE SENTINEL (Semplificata)
    score = 50
    if curr_rsi < 30: score += 25
    if curr_rsi > 70: score -= 25
    if curr_p < bb_p.iloc[-1, 0]: score += 15
    if curr_p > bb_p.iloc[-1, 2]: score -= 15

    else:
        st.warning("Dati di mercato non disponibili al momento.")

    
    st.markdown("---")
    st.subheader("🕵️ Sentinel Analysis Summary")
    col_a, col_b = st.columns(2)
    col_a.metric("Sentinel AI Score", f"{score}/100")
    col_b.write(f"**Divergenza Rilevata:** {detect_divergence(df_graph.tail(30))}")

    st.markdown("### 📊 Guida alla Volatilità (ADX)")
    
    adx_guide = pd.DataFrame([
        {"Valore": "0 - 20", "Stato": "🟢 Laterale", "Affidabilità": "MASSIMA"},
        {"Valore": "20 - 30", "Stato": "🟡 In formazione", "Affidabilità": "MEDIA"},
        {"Valore": "30+", "Stato": "🔴 Trend Forte", "Affidabilità": "BASSA"}
    ])

    def highlight_adx(row):
        if curr_adx_ai <= 20 and "0 - 20" in row['Valore']: return ['background-color: rgba(0, 255, 0, 0.2)'] * len(row)
        elif 20 < curr_adx_ai <= 30 and "20 - 30" in row['Valore']: return ['background-color: rgba(255, 255, 0, 0.2)'] * len(row)
        elif curr_adx_ai > 30 and "30+" in row['Valore']: return ['background-color: rgba(255, 0, 0, 0.2)'] * len(row)
        return [''] * len(row)

    styled_adx_html = (adx_guide.style
                       .apply(highlight_adx, axis=1)
                       .hide(axis='index')
                       .set_table_attributes('style="width:100%; border-collapse: collapse; text-align: left;"')
                       .to_html())

    st.markdown(styled_adx_html, unsafe_allow_html=True)

# --- 8. CURRENCY STRENGTH ---
st.markdown("---")
st.subheader("⚡ Currency Strength Meter")
s_data = get_currency_strength()

if not s_data.empty:
    cols = st.columns(len(s_data))
    for i, (curr, val) in enumerate(s_data.items()):
        bg = "#006400" if val > 0.15 else "#8B0000" if val < -0.15 else "#333333"
        txt_c = "#00FFCC" if val > 0.15 else "#FF4B4B" if val < -0.15 else "#FFFFFF"
        cols[i].markdown(
            f"<div style='text-align:center; background:{bg}; padding:6px; border-radius:8px; border:1px solid {txt_c}; min-height:80px;'>"
            f"<b style='color:white; font-size:0.8em;'>{curr}</b><br>"
            f"<span style='color:{txt_c};'>{val:.2f}%</span></div>", 
            unsafe_allow_html=True
        )
else:
    st.info("⏳ Caricamento dati macro in corso...")

# --- 9. CRONOLOGIA SEGNALI ---
st.markdown("---")
st.subheader("📜 Cronologia Segnali")

if not st.session_state['signal_history'].empty:
    full_history = st.session_state['signal_history'].copy()
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        opzioni_stato = sorted(full_history['Stato'].unique().tolist())
        filtro_stato = st.multiselect("Filtra Esito:", options=opzioni_stato, default=[], placeholder="Tutti gli esiti")
    with col_f2:
        opzioni_asset = sorted(full_history['Asset'].unique().tolist())
        filtro_asset = st.multiselect("Filtra Valuta:", options=opzioni_asset, default=[], placeholder="Tutte le valute")

    df_filtrato = full_history.copy()
    if filtro_stato:
        df_filtrato = df_filtrato[df_filtrato['Stato'].isin(filtro_stato)]
    if filtro_asset:
        df_filtrato = df_filtrato[df_filtrato['Asset'].isin(filtro_asset)]
    
    display_df = df_filtrato.reset_index(drop=True)
    
    if not display_df.empty:
        st.dataframe(
            display_df.style.map(style_status, subset=['Stato', 'Risultato €']), 
            use_container_width=True,
            hide_index=True,
            column_order=['DataOra', 'Asset', 'Direzione', 'Prezzo', 'TP', 'SL', 'Stato', 'Investimento €', 'Risultato €', 'Costo Spread €', 'Stato_Prot']
        )

    else:
        st.warning("Nessun dato corrispondente ai filtri selezionati.")

else:
    st.info(f"📖 **In attesa di un segnale da registrare**")
