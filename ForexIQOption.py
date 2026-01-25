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
    token = "8235666467:AAGCsvEhlrzl7bH537bJTjsSwQ3P3PMRW10" 
    chat_id = "7191509088" 
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        params = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
        r = requests.get(url, params=params, timeout=5)
        if r.status_code != 200:
            st.toast(f"Errore Telegram: {r.status_code}", icon="⚠️")
    except Exception as e:
        print(f"Errore: {e}")

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

    sessions = {
        "Tokyo 🇯🇵": (datetime.time(0,0), datetime.time(9,0)), 
        "Londra 🇬🇧": (datetime.time(9,0), datetime.time(18,0)), 
        "New York 🇺🇸": (datetime.time(14,0), datetime.time(23,0))
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
        data = yf.download(forex + crypto, period="5d", interval="1d", progress=False, timeout=15)
        
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
    if api_conn:
        try:
            # Nota: questa chiamata potrebbe variare in base alla versione della lib iqoptionapi
            # Cerchiamo di ottenere le posizioni aperte
            orders = api_conn.get_positions("forex") 
            # Mappa orders per ID per accesso veloce
            # open_positions = {str(o['id']): o for o in orders} # Semplificazione
        except:
            pass

    for idx, row in df[df['Stato'] == 'In Corso'].iterrows():
        try:
            # Usiamo YF per il prezzo corrente per coerenza coi grafici, 
            # ma idealmente si dovrebbe usare api_conn.get_candles per il prezzo preciso del broker
            ticker_yf = asset_map[row['Asset']]['yf']
            data = yf.download(ticker_yf, period="1d", interval="1m", progress=False)
            if data.empty: continue
            
            if isinstance(data.columns, pd.MultiIndex): 
                data.columns = data.columns.get_level_values(0)
            data.columns = [c.lower() for c in data.columns]
            
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
    if not st.session_state['signal_history'].empty:
        if len(st.session_state['signal_history']) > 50:
            st.session_state['signal_history'] = st.session_state['signal_history'].head(50)
            save_history_permanently()

    st.session_state['last_alert'] = None
    if 'alert_notified' in st.session_state: 
        del st.session_state['alert_notified']
    
    current_balance = st.session_state.get('balance_val', 1000)
    current_risk = st.session_state.get('risk_val', 2.0)
    
    # Se connesso a IQ, prova a leggere il saldo reale
    if api_conn:
        try:
            current_balance = api_conn.get_balance()
            st.session_state['balance_val'] = current_balance
        except: pass

    debug_list = []    
    assets = list(asset_map.items())
    
    for label, tickers in assets:
        yf_ticker = tickers['yf']
        iq_ticker = tickers['iq']
        
        try:
            df_rt_s = yf.download(yf_ticker, period="2d", interval="1m", progress=False)
            df_d_s = yf.download(yf_ticker, period="1y", interval="1d", progress=False)
            
            if df_rt_s.empty or df_d_s.empty: 
                debug_list.append(f"🔴 {label}: No Data")
                continue
            
            if isinstance(df_rt_s.columns, pd.MultiIndex): df_rt_s.columns = df_rt_s.columns.get_level_values(0)
            if isinstance(df_d_s.columns, pd.MultiIndex): df_d_s.columns = df_d_s.columns.get_level_values(0)
            
            df_rt_s.columns = [c.lower() for c in df_rt_s.columns]
            df_d_s.columns = [c.lower() for c in df_d_s.columns]

            bb_s = ta.bbands(df_rt_s['close'], length=20, std=2)
            if bb_s is None: continue

            c_low = [c for c in bb_s.columns if "BBL" in c.upper()][0]
            c_up = [c for c in bb_s.columns if "BBU" in c.upper()][0]
            
            curr_v = float(df_rt_s['close'].iloc[-1])
            low_bb = float(bb_s[c_low].iloc[-1])
            up_bb = float(bb_s[c_up].iloc[-1])
            
            rsi_d = ta.rsi(df_d_s['close'], length=14).iloc[-1]
            rsi_fast = ta.rsi(df_rt_s['close'], length=5).iloc[-1]
            avg_volume = df_rt_s['volume'].rolling(window=20).mean().iloc[-1]
            curr_volume = df_rt_s['volume'].iloc[-1]
            
            adx_df = ta.adx(df_rt_s['high'], df_rt_s['low'], df_rt_s['close'], length=14)
            curr_adx = adx_df['ADX_14'].iloc[-1] if adx_df is not None else 0

            s_action = None
            
            if curr_v < low_bb:
                if rsi_d < 60 and rsi_fast < 25 and curr_volume > (avg_volume * 0.8):
                    if curr_adx < 30: 
                        s_action = "COMPRA"
            
            elif curr_v > up_bb:
                if rsi_d > 40 and rsi_fast > 75 and curr_volume > (avg_volume * 0.8):
                    if curr_adx < 30:
                        s_action = "VENDI"

            if s_action:
                hist = st.session_state['signal_history']
                is_running = not hist.empty and ((hist['Asset'] == label) & (hist['Stato'] == 'In Corso')).any()
                
                recent_signals = False
                if not hist.empty:
                    asset_hist = hist[hist['Asset'] == label]
                    if not asset_hist.empty:
                        last_sig = asset_hist.iloc[0]['DataOra']
                        if last_sig > (get_now_rome().replace(minute=get_now_rome().minute - 30)).strftime("%H:%M:%S"):
                           recent_signals = True
              
                if not is_running and not recent_signals:
                    p_unit, p_fmt, p_mult, a_type = get_asset_params(label)
                    rischio_euro = current_balance * (current_risk / 100) 

                    # Calcolo spread reale se connesso
                    current_spread = SIMULATED_SPREAD

                    if api_conn:
                        current_spread = get_real_spread(api_conn, iq_ticker, instrument_type)

                    if s_action == "COMPRA":
                        entry_with_spread = curr_v + current_spread
                        distanza_sl = entry_with_spread * 0.002 
                        sl_prezzo = entry_with_spread - distanza_sl
                        tp_prezzo = entry_with_spread + (distanza_sl * 1.5)
                        side_iq = "buy"
                    else:
                        entry_with_spread = curr_v - current_spread
                        distanza_sl = entry_with_spread * 0.002
                        sl_prezzo = entry_with_spread + distanza_sl
                        tp_prezzo = entry_with_spread - (distanza_sl * 1.5)
                        side_iq = "sell"
                    
                    costo_spread_apertura = inv_effettivo_calcolato * (current_spread / entry_with_spread)

                    percentuale_distanza_sl = (distanza_sl / entry_with_spread)
                    inv_effettivo_calcolato = rischio_euro / percentuale_distanza_sl
                    costo_spread_apertura = inv_effettivo_calcolato * SIMULATED_SPREAD

                    mercato_aperto = is_market_open(label)

                    if check:
                        iq_order_id = str(order_id) # Salva l'ID reale ricevuto dal broker
                        debug_list.append(f"✅ Ordine IQ Eseguito: {iq_order_id}")
                    else:
                        iq_order_id = "ERROR" # Evita che resti "DEMO-ID"
                        stato_iniziale = '❌ ERRORE API'

                    if not mercato_aperto:
                        stato_iniziale = '⛔ CHIUSO'
                        inv_effettivo = "0.00"
                        res_effettivo = "0.00"
                        prot_status = 'Non Attiva'
                        icona_stato = "⛔"
                        txt_validita = "NON OPERARE (Market Closed)"
                    else:
                        stato_iniziale = 'In Corso'
                        inv_effettivo = f"{inv_effettivo_calcolato:.2f}"
                        res_effettivo = "0.00"
                        prot_status = 'Iniziale'
                        icona_stato = "✅"
                        txt_validita = "SEGNALE VALIDO & ESEGUITO"

                        # --- ESECUZIONE REALE SU IQ OPTION ---
                        if api_conn:
                            try:
                                # Parametri ordine
                                # Nota: "leverage" dipende dall'asset e dall'account. 
                                # Usiamo un valore standard o quello massimo disponibile
                                # --- PARAMETRI DINAMICI ---
                            if s_action:
                                # --- CONTROLLO FILTRI REALI ---
                                instrument_type = "crypto" if "BTC" in label or "ETH" in label else "forex"
                                leverage_effettiva = 1
                                spread_val, spread_pct = SIMULATED_SPREAD, 0.05
                                
                                if api_conn:
                                    leverage_effettiva = get_dynamic_leverage(api_conn, iq_ticker, instrument_type)
                                    spread_val, spread_pct = get_real_spread_info(api_conn, iq_ticker)
                                
                                # SOGLIA DI BLOCCO: Se lo spread è > 0.1% del prezzo, il segnale è pericoloso
                                MAX_SPREAD_ALLOWED_PCT = 0.12 
                                
                                if spread_pct > MAX_SPREAD_ALLOWED_PCT:
                                    debug_list.append(f"⚠️ {label} Saltato: Spread troppo alto ({spread_pct:.3f}%)")
                                    s_action = None # Annulla l'operazione
                                
                                if s_action:
                                    # Procedi con il calcolo dei prezzi usando spread_val reale
                                    if s_action == "COMPRA":
                                        entry_with_spread = curr_v + (spread_val / 2)
                                        # ... resto dei calcoli ...
                            
                                # --- ESECUZIONE REALE ---
                                if api_conn:
                                    check, order_id = api_conn.buy_order(
                                        instrument_type=instrument_type, 
                                        instrument_id=iq_ticker.lower(),
                                        side=side_iq,
                                        amount=inv_effettivo_calcolato,
                                        leverage=leverage_effettiva, # Ora è dinamica!
                                        type="market",
                                        stop_loss_price=sl_prezzo,
                                        take_profit_price=tp_prezzo
                                    )
                                
                                if check:
                                    iq_order_id = str(order_id)
                                    debug_list.append(f"✅ Ordine IQ Eseguito: {iq_order_id}")
                                else:
                                    debug_list.append(f"❌ Errore Ordine IQ: {order_id}")
                                    stato_iniziale = '❌ ERRORE API'
                            except Exception as e:
                                debug_list.append(f"❌ Eccezione API: {e}")
                        else:
                            txt_validita = "SIMULAZIONE (API NON CONNESSA)"

                    new_sig = {
                        'DataOra': get_now_rome().strftime("%H:%M:%S"),
                        'Asset': label, 
                        'Direzione': s_action, 
                        'Prezzo': p_fmt.format(entry_with_spread), 
                        'TP': p_fmt.format(tp_prezzo), 
                        'SL': p_fmt.format(sl_prezzo), 
                        'Stato': stato_iniziale,
                        'Protezione': 'Trailing Step',
                        'Investimento €': f"{inv_effettivo_calcolato:.2f}",
                        'Risultato €': res_effettivo,
                        'Costo Spread €': f"{costo_spread_apertura:.3f}",
                        'Stato_Prot': prot_status,
                        'IQ_ID': iq_order_id
                    }
                    
                    st.session_state['signal_history'] = pd.concat([pd.DataFrame([new_sig]), hist], ignore_index=True)
                    st.session_state['last_alert'] = new_sig
                    save_history_permanently()
  
                    telegram_text = (
                        f"{icona_stato} *{s_action}* {label}\n"
                        f"Entry: {new_sig['Prezzo']}\n"
                        f"TP: {new_sig['TP']}\n"
                        f"SL: {new_sig['SL']}\n"
                        f"Investimento: € {new_sig['Investimento €']}\n"
                        f"------------------\n"
                        f"ℹ️ *{txt_validita}*"
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

# --- SIDEBAR: LOGIN E STATO ---
st.sidebar.header("🔑 Connessione IQ Option")
email = st.sidebar.text_input("Email", key="login_email")
password = st.sidebar.text_input("Password", type="password", key="login_pass")
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

# --- 5. MOTORE DI ESECUZIONE ---
if st.session_state.get('iq_api'):
    # 1. Monitoraggio posizioni aperte (Trailing Stop)
    # Lo facciamo prima per assicurarci di chiudere o proteggere trade esistenti
    update_signal_outcomes(st.session_state['iq_api'])
    
    # 2. Ricerca nuovi segnali (Sentinel)
    run_sentinel(st.session_state['iq_api'])
    
    # Visualizzazione log di debug in sidebar
    with st.sidebar.expander("🛠 Sentinel Engine Logs", expanded=False):
        for log in st.session_state.get('sentinel_logs', []):
            st.caption(log)

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

st.title("📈 Trading Panel CFD & Forex")

if api and api.check_connect():
    tab1, tab2 = st.tabs(["🚀 Apri Posizione", "📊 Monitoraggio Attivo"])

    with tab1:
        st.subheader("Configurazione Nuovo Ordine")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            asset = st.selectbox("Asset", ["EURUSD", "GBPUSD", "BTCUSD", "ETHUSD"])
            direzione = st.radio("Direzione", ["buy", "sell"])
        
        with c2:
            investimento = st.number_input("Investimento ($)", min_value=1.0, value=10.0)
            leva = st.slider("Leva", 1, 500, 50)
            
        with c3:
            stop_loss = st.number_input("Stop Loss (%)", value=10)
            take_profit = st.number_input("Take Profit (%)", value=20)

        if st.button("ESEGUI ORDINE CFD", use_container_width=True):
            if puo_aprire_posizione(api, investimento):
                # Pulizia nome asset per API
                iq_asset = asset.replace("=", "").upper()
                
                check, order_id = api.buy_order(
                    instrument_type="cfd", # Usiamo CFD come richiesto
                    instrument_id=iq_asset.lower(),
                    side=direzione,
                    amount=investimento,
                    leverage=leva,
                    type="market",
                    stop_lose_kind="percent",
                    stop_lose_value=stop_loss,
                    take_profit_kind="percent",
                    take_profit_value=take_profit
                )
                
                if check:
                    st.success(f"✅ Ordine eseguito! ID: {order_id}")
                else:
                    st.error(f"❌ Errore API: {order_id}")

    with tab2:
        st.subheader("Posizioni Aperte")
        posizioni = api.get_positions("cfd")
        
        if posizioni:
            # Creazione tabella per visualizzazione pulita
            data_list = []
            for pos_id, p in posizioni.items():
                data_list.append({
                    "ID": pos_id,
                    "Asset": p['item_id'],
                    "Direzione": p['side'],
                    "Profitto ($)": p['win_amount']
                })
            st.table(data_list)

            if st.button("🚨 CHIUDI TUTTE LE POSIZIONI", color="red", use_container_width=True):
                for pos_id in posizioni.keys():
                    api.close_order(pos_id)
                st.success("Comando di chiusura inviato a tutte le posizioni.")
                st.rerun()
        else:
            st.info("Nessuna posizione attiva.")

else:
    st.info("💡 Effettua il login dalla sidebar per iniziare a fare trading.")

st.markdown("---")
st.subheader(f"📈 Grafico {selected_label} (1m) con BB e RSI")

p_unit, price_fmt, p_mult, a_type = get_asset_params(pair)
df_rt = get_realtime_data(pair) 
df_d = yf.download(pair, period="1y", interval="1d", progress=False)

if df_rt is not None and not df_rt.empty and df_d is not None and not df_d.empty:
    
    if isinstance(df_d.columns, pd.MultiIndex): df_d.columns = df_d.columns.get_level_values(0)
    df_d.columns = [c.lower() for c in df_d.columns]
    
    bb = ta.bbands(df_rt['close'], length=20, std=2)
    df_rt = pd.concat([df_rt, bb], axis=1)
    df_rt['rsi'] = ta.rsi(df_rt['close'], length=14)
    df_d['rsi'] = ta.rsi(df_d['close'], length=14)
    df_d['atr'] = ta.atr(df_d['high'], df_d['low'], df_d['close'], length=14)
          
    c_up = [c for c in df_rt.columns if "BBU" in c.upper()][0]
    c_mid = [c for c in df_rt.columns if "BBM" in c.upper()][0]
    c_low = [c for c in df_rt.columns if "BBL" in c.upper()][0]
    
    curr_p = float(df_rt['close'].iloc[-1])
    curr_rsi = float(df_rt['rsi'].iloc[-1])
    rsi_val = float(df_d['rsi'].iloc[-1]) 
    last_atr = float(df_d['atr'].iloc[-1])
    
    score = 50 + (20 if curr_p < df_rt[c_low].iloc[-1] else -20 if curr_p > df_rt[c_up].iloc[-1] else 0)

    p_df = df_rt.tail(60)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.75, 0.25])
    
    fig.add_trace(go.Candlestick(
        x=p_df.index, open=p_df['open'], high=p_df['high'], 
        low=p_df['low'], close=p_df['close'], name='Prezzo'
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=p_df.index, y=p_df[c_up], line=dict(color='rgba(0, 191, 255, 0.6)', width=1), name='Upper BB'), row=1, col=1)
    fig.add_trace(go.Scatter(x=p_df.index, y=p_df[c_mid], line=dict(color='rgba(0, 0, 0, 0.3)', width=1), name='BBM'), row=1, col=1)
    fig.add_trace(go.Scatter(x=p_df.index, y=p_df[c_low], line=dict(color='rgba(0, 191, 255, 0.6)', width=1), fill='tonexty', fillcolor='rgba(0, 191, 255, 0.15)', name='Lower BB'), row=1, col=1)

    fig.add_trace(go.Scatter(x=p_df.index, y=p_df['rsi'], line=dict(color='#ffcc00', width=2), name='RSI'), row=2, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#00ff00", row=2, col=1)

    for t in p_df.index:
        if t.minute % 10 == 0:
            fig.add_vline(x=t, line_width=0.5, line_dash="solid", line_color="rgba(0, 0, 0, 0.3)", layer="below")

    fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=30,b=0), legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig, use_container_width=True)

    c_met1, c_met2 = st.columns(2)
    c_met1.metric(label=f"Prezzo {selected_label}", value=price_fmt.format(curr_p))
    c_met2.metric(label="RSI (5m)", value=f"{curr_rsi:.1f}", delta="Ipercomprato" if curr_rsi > 70 else "Ipervenduto" if curr_rsi < 30 else "Neutro", delta_color="inverse")
    
    st.caption(f"📢 RSI Daily: {rsi_val:.1f} | Divergenza: {detect_divergence(df_d)}")

    adx_df_ai = ta.adx(df_rt['high'], df_rt['low'], df_rt['close'], length=14)
    curr_adx_ai = adx_df_ai['ADX_14'].iloc[-1]

    st.markdown("---")
    st.subheader("🕵️ Sentinel Market Analysis")
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("RSI Daily", f"{rsi_val:.1f}", detect_divergence(df_d))
    col_b.metric("Sentinel Score", f"{score}/100")
    adx_emoji = "🔴" if curr_adx_ai > 30 else "🟡" if curr_adx_ai > 20 else "🟢"
    col_c.metric("Forza Trend (ADX)", f"{curr_adx_ai:.1f}", adx_emoji)

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
