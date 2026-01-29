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
from iq_bot import IQHandler # Importa la classe che abbiamo creato
import threading
import time

# --- INIZIALIZZAZIONE UNIFICATA ---
if 'iq_bot' not in st.session_state:
    st.session_state['iq_bot'] = None
    st.session_state['trading_attivo'] = True
    st.session_state['signal_history'] = load_history_from_csv()

if st.session_state['iq_bot'] is None:
    bot = IQHandler(IQ_EMAIL, IQ_PASS)
    if bot.connetti():
        st.session_state['iq_bot'] = bot
        sincronizza_posizioni_aperte()

# Recupero dai Secrets
TELE_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELE_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

def invia_telegram(messaggio):
    """Funzione rapida per inviare notifiche"""
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELE_CHAT_ID,
        "text": messaggio,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Errore Telegram: {e}")

def get_advanced_stats():
    df = st.session_state['signal_history'].copy()
    
    # Filtriamo solo i trade conclusi
    df = df[df['Stato'].isin(['✅ TARGET', '❌ STOP LOSS', '🖐️ CHIUSO MAN.'])]
    
    if df.empty:
        return None

    # Pulizia dati monetari
    df['Risultato €'] = df['Risultato €'].str.replace('€', '').astype(float)
    df['DataOra_dt'] = pd.to_datetime(df['DataOra'], format='%Y-%m-%d %H:%M:%S') # Nota: aggiungi la data reale se disponibile
    
    stats = {}
    # 1. Profitto Totale e Settimanale (Simulato sulla cronologia attuale)
    stats['total_pnl'] = df['Risultato €'].sum()
    
    # 2. Miglior e Peggior Asset
    asset_perf = df.groupby('Asset')['Risultato €'].sum().sort_values(ascending=False)
    stats['best_asset'] = asset_perf.index[0] if not asset_perf.empty else "N/A"
    stats['worst_asset'] = asset_perf.index[-1] if not asset_perf.empty else "N/A"
    
    # 3. Analisi Oraria (Peggior orario per fare trading)
    df['Ora'] = df['DataOra_dt'].dt.hour
    hourly_perf = df.groupby('Ora')['Risultato €'].sum()
    stats['worst_hour'] = f"{hourly_perf.idxmin()}:00" if not hourly_perf.empty else "N/A"
    
    # 4. Win Rate Effettivo
    wins = len(df[df['Risultato €'] > 0])
    stats['win_rate'] = (wins / len(df)) * 100
    
    return stats, asset_perf, hourly_perf

# --- CONFIGURAZIONE CREDENZIALI (NON HARDCODARE LA PASSWORD SE PUOI) ---
# Usa st.secrets o variabili d'ambiente per sicurezza
# Recupero dai Secrets
IQ_EMAIL = st.secrets["IQ_EMAIL"]
IQ_PASS = st.secrets["IQ_PASS"]
TELE_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELE_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

# Inizializzazione IQ Option
if 'iq_bot' not in st.session_state:
    # Passiamo le credenziali dei secrets alla classe
    bot = IQHandler(IQ_EMAIL, IQ_PASS) 
    if bot.connetti():
        st.session_state['iq_bot'] = bot
    else:
        st.session_state['iq_bot'] = None

if 'trading_attivo' not in st.session_state:
    st.session_state['trading_attivo'] = True # Il bot parte attivo di default

# Filtra solo i trade degli ultimi 7 giorni
sette_giorni_fa = (datetime.now() - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
df = df[df['DataOra'] >= sette_giorni_fa]

# --- 1. CONFIGURAZIONE & LAYOUT ---
st.set_page_config(page_title="Forex Momentum Pro AI", layout="wide", page_icon="📈")

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

# 1. Recupero credenziali dai Secrets (vedremo dopo come impostarli)
IQ_EMAIL = st.secrets["IQ_EMAIL"]
IQ_PASS = st.secrets["IQ_PASS"]

# Avvio del Thread di Background (Analisi Continua)
if st.session_state.get('iq_bot') and 'bot_thread_started' not in st.session_state:
    import threading
    # Assicurati che bot_loop sia definito sopra o importato
    thread = threading.Thread(target=bot_loop, daemon=True)
    thread.start()
    st.session_state['bot_thread_started'] = True
    st.sidebar.success("🚀 Motore di Trading Demo Attivo")

# Definizione Fuso Orario Roma
rome_tz = pytz.timezone('Europe/Rome')
asset_map = {"EURUSD": "EURUSD", "GBPUSD": "GBPUSD", "USDCHF": "USDCHF", "USDJPY": "USDJPY", "AUDUSD": "AUDUSD", "USDCAD": "USDCAD", "NZDUSD": "NZDUSD",
            "EURGBP": "EURGBP", "GBPJPY": "GBPJPY", "EURJPY": "EURJPY"}

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
    if os.path.exists("permanent_signals_db.csv"):
        try:
            df = pd.read_csv("permanent_signals_db.csv")
            # Lista aggiornata con le nuove colonne monetarie e di protezione
            expected_cols = ['DataOra', 'Asset', 'Direzione', 'Prezzo', 'SL', 'TP', 
                             'Stato', 'Investimento €', 'Risultato €', 'Stato_Prot', 'Protezione']
            for col in expected_cols:
                if col not in df.columns: 
                    df[col] = "0.00" if "€" in col else "Standard"
            return df
        except:
            return pd.DataFrame(columns=['DataOra', 'Asset', 'Direzione', 'Prezzo', 'SL', 'TP', 'Stato', 'Investimento €', 'Risultato €', 'Stato_Prot', 'Protezione'])
    return pd.DataFrame(columns=['DataOra', 'Asset', 'Direzione', 'Prezzo', 'SL', 'TP', 'Stato', 'Investimento €', 'Risultato €', 'Stato_Prot', 'Protezione'])

def connetti(self):
    check, reason = self.api.connect()
    if check:
        # FORZA IL CONTO DEMO (PRACTICE)
        self.api.change_balance("PRACTICE") 
        saldo = self.api.get_balance()
        print(f"✅ Connesso! Saldo Demo attuale: {saldo}€")
        self.connected = True
    else:
        self.connected = False
    return self.connected

def get_now_rome():
    return datetime.now(rome_tz).strftime("%Y-%m-%d %H:%M:%S")

def get_last_price_iq(asset_name):
    if st.session_state.get('iq_bot') and st.session_state['iq_bot'].connected:
        api = st.session_state['iq_bot'].api
        asset_iq = asset_name.replace("=X", "") # Pulisce il nome se necessario
        
        # Chiediamo l'ultima candela da 1 secondo per avere il prezzo real-time
        candles = api.get_candles(asset_iq, 60, 1, time.time())
        if candles:
            return float(candles[-1]['close'])
    return None

def style_protection(val):
    # Se il capitale è blindato in profitto, usiamo un verde brillante
    if 'Blindato' in str(val) or 'Garantito' in str(val):
        return 'background-color: #2ecc71; color: white; font-weight: bold;'
    # Se siamo al pareggio (Break-Even), usiamo un blu o arancio
    elif 'Pareggio' in str(val):
        return 'background-color: #3498db; color: white;'
    # Se è lo stop loss iniziale (-10%)
    elif 'Standard' in str(val):
        return 'color: #e74c3c; font-weight: bold;'
    return ''

def play_notification_sound():
    audio_html = """
        <audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)

def play_close_sound():
    # Un suono più breve e "cash register" per le chiusure
    audio_html = """
        <audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2017/2017-preview.mp3" type="audio/mpeg"></audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)

def play_safe_sound():
    # Un suono tipo "scatto metallico" o "ding" per indicare la messa in sicurezza
    audio_html = """
        <audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2021/2021-preview.mp3" type="audio/mpeg"></audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)

def style_status(val):
    if val == '✅ TARGET': return 'background-color: rgba(0, 255, 204, 0.2); color: #00ffcc;'
    if val == '❌ STOP LOSS': return 'background-color: rgba(255, 75, 75, 0.2); color: #ff4b4b;'
    if val == 'Garantito': return 'color: #FFA500; font-weight: bold;' # Arancione per protezione attiva
    return ''

def genera_segnali_iq():
    if not st.session_state.get('iq_bot') or not st.session_state['iq_bot'].connected:
        return
    
    api = st.session_state['iq_bot'].api
    
    for label, asset_iq in asset_map.items():
        # Recuperiamo le ultime 50 candele da 1 minuto (60 secondi)
        # Il parametro 60 è la size, 50 è la quantità
        candles = api.get_candles(asset_iq, 60, 50, time.time())
        
        if candles:
            df_candles = pd.DataFrame(candles)
            
            # --- CALCOLO INDICATORI (Esempio Momentum) ---
            # Calcoliamo la variazione percentuale degli ultimi 3 minuti
            current_price = df_candles['close'].iloc[-1]
            old_price = df_candles['close'].iloc[-3]
            variazione = ((current_price - old_price) / old_price) * 100
            
            # Logica di ingresso (es. se variazione > 0.05% in 3 min)
            if variazione > 0.05:
                esegui_ordine_completo(label, "COMPRA", current_price)
            elif variazione < -0.05:
                esegui_ordine_completo(label, "VENDI", current_price)

def calcola_pnl_protetto(prezzo_entrata, prezzo_attuale, direzione, investimento):
    # Calcolo base della variazione percentuale
    if direzione == "COMPRA":
        variazione = (prezzo_attuale - prezzo_entrata) / prezzo_entrata
    else:
        variazione = (prezzo_entrata - prezzo_attuale) / prezzo_entrata
    
    perc = variazione * 100
    
    # --- FILTRO ANTI-FOLLIA ---
    # Se la variazione è assurda (es. > 50% nel Forex in pochi minuti), 
    # ignoriamo il dato per evitare glitch grafici o chiusure errate.
    if abs(perc) > 50: 
        return 0.0, 0.0, True # Ritorna 'True' per indicare un glitch rilevato
        
    profitto_euro = investimento * variazione
    return perc, profitto_euro, False

def sincronizza_posizioni_aperte():
    """Recupera i trade attivi dal broker e aggiorna il database locale"""
    if not st.session_state.get('iq_bot'):
        return

    bot = st.session_state['iq_bot']
    # Recupera le posizioni aperte (CFD/Forex/Digital)
    # Nota: la chiamata esatta dipende dalla versione della libreria iqoptionapi
    posizioni_reali = bot.api.get_positions("forex") 
    
    if posizioni_reali[0]: # Se la chiamata ha successo
        df_hist = st.session_state['signal_history']
        
        for pos in posizioni_reali[1]:
            iq_id = pos['external_id'] # O l'ID univoco della posizione
            
            # Controlla se abbiamo già questo ID in memoria
            if iq_id not in df_hist['IQ_ID'].values:
                # Creiamo un record di "recupero"
                new_sig = {
                    'DataOra': get_now_rome().strftime("%Y-%m-%d %H:%M:%S"),
                    'Asset': pos['active_id'], # Va convertito in nome stringa se necessario
                    'Direzione': 'COMPRA' if pos['side'] == 'buy' else 'VENDI',
                    'Prezzo': pos['open_quote'],
                    'TP': pos['take_profit_price'],
                    'SL': pos['stop_loss_price'],
                    'Stato': 'In Corso',
                    'IQ_ID': iq_id,
                    'Investimento €': pos['pnl_realized'], # O il valore investito
                    'Risultato €': "0.00",
                    'Protezione': 'Recuperato da Broker'
                }
                st.session_state['signal_history'] = pd.concat([pd.DataFrame([new_sig]), df_hist], ignore_index=True)
                st.toast(f"🔄 Recuperata posizione attiva: {iq_id}")

def get_session_status():
    now_rome = get_now_rome().time()
    sessions = {
        "Tokyo 🇯🇵": (time(0,0), time(9,0)), 
        "Londra 🇬🇧": (time(9,0), time(18,0)), 
        "New York 🇺🇸": (time(14,0), time(23,0))
    }
    return {name: start <= now_rome <= end for name, (start, end) in sessions.items()}

@st.cache_data(ttl=60)
def get_realtime_data(ticker):
    try:
        df = yf.download(ticker, period="5d", interval="5m", progress=False, timeout=10)
        if df is None or df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        return df.dropna()
    except: return None

def invia_report_settimanale():
    """Genera e invia il riepilogo delle performance via Telegram"""
    data = get_advanced_stats()
    if not data:
        invia_telegram("📊 **Report Settimanale**: Nessuna operazione conclusa questa settimana.")
        return

    stats, asset_perf, _ = data
    
    # Costruiamo il messaggio
    msg = (
        "📊 **SENTINEL: REPORT SETTIMANALE** 📈\n"
        "----------------------------------\n"
        f"💰 **Profitto Netto:** € {stats['total_pnl']:.2f}\n"
        f"🏆 **Win Rate:** {stats['win_rate']:.1f}%\n"
        f"🚀 **Miglior Asset:** {stats['best_asset']}\n"
        f"⚠️ **Ora Critica:** {stats['worst_hour']}\n"
        "----------------------------------\n"
        "✅ Mercati in chiusura. Buon weekend!"
    )
    
    invia_telegram(msg)

def get_currency_strength():
    try:
        forex = ["EURUSD", "GBPUSD", "USDCHF", "USDCHF", "AUDUSD", "NZDUSD", "EURCHF","EURJPY", "GBPJPY","EURGBP"]
        data = yf.download(forex, period="5d", interval="1d", progress=False, timeout=15)
        
        if data is None or data.empty: 
            return pd.Series(dtype=float)

        if isinstance(data.columns, pd.MultiIndex):
            if 'Close' in data.columns.get_level_values(0): close_data = data['Close']
            else: close_data = data['Close'] if 'Close' in data else data
        else:
            close_data = data['Close'] if 'Close' in data else data

        close_data = close_data.ffill().dropna()
        if len(close_data) < 2: return pd.Series(dtype=float)

        returns = close_data.pct_change().iloc[-1] * 100
        
        strength = {
            "USD 🇺🇸": (-returns.get("EURUSD=X",0) - returns.get("GBPUSD=X",0) + returns.get("USDJPY=X",0) - returns.get("AUDUSD=X",0) + returns.get("USDCAD=X",0) + returns.get("USDCHF=X",0) - returns.get("NZDUSD=X",0) + returns.get("USDCNY=X",0) + returns.get("USDRUB=X",0) + returns.get("USDCOP=X",0) + returns.get("USDARS=X",0) + returns.get("USDBRL=X",0)) / 12,
            "EUR 🇪🇺": (returns.get("EURUSD=X",0) + returns.get("EURJPY=X",0) + returns.get("EURGBP=X",0) + returns.get("EURCHF=X", 0) + returns.get("EURGBP=X", 0) + returns.get("EURJPY=X", 0)) / 6,
            "GBP 🇬🇧": (returns.get("GBPUSD=X",0) + returns.get("GBPJPY=X",0) - returns.get("EURGBP=X",0) + returns.get("GBPCHF=X", 0) + returns.get("GBPJPY=X", 0)) / 5,
            "JPY 🇯🇵": (-returns.get("USDJPY=X",0) - returns.get("EURJPY=X",0) - returns.get("GBPJPY=X",0)) / 3,
            "CHF 🇨🇭": (-returns.get("USDCHF=X",0) - returns.get("EURCHF=X",0) - returns.get("GBPCHF=X",0)) / 3,
            "AUD 🇦🇺": returns.get("AUDUSD=X", 0),
            "NZD 🇳🇿": returns.get("NZDUSD=X", 0),
            "CAD 🇨🇦": -returns.get("USDCAD=X", 0)
            #"CNY 🇨🇳": -returns.get("CNY=X", 0),
            #"RUB 🇷🇺": -returns.get("RUB=X", 0),
            #"COP 🇨🇴": -returns.get("COP=X", 0),
            #"ARS 🇦🇷": -returns.get("ARS=X", 0),
            #"BRL 🇧🇷": -returns.get("BRL=X", 0),
            #"MXN 🇲🇽": -returns.get("MXN=X", 0)
            #"BTC ₿": returns.get("BTC-USD", 0),
            #"ETH 💎": returns.get("ETH-USD", 0)
        }
        return pd.Series(strength).sort_values(ascending=False)
    except Exception:
        return pd.Series(dtype=float)

def get_asset_params(pair):
    """
    Restituisce: (unità_minima, formato_prezzo, moltiplicatore_reale, tipo)
    """
    if "BTC" in pair or "ETH" in pair:
        # Per Crypto: 1 punto = 1 Dollaro
        return 1.0, "{:.2f}", 1, "CRYPTO"
    elif "JPY" in pair:
        # Per JPY: 0.01 = 1 punto
        return 0.01, "{:.3f}", 100, "FOREX_JPY"
    else:
        # Per Forex standard (EURUSD ecc): 0.0001 = 1 punto (PIP)
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
    
# --- 2. FUNZIONI TECNICHE (AGGIORNATE) ---

# ... (le altre funzioni save_history, send_telegram rimangono uguali, incolla da qui in giù) ...

def update_signal_outcomes():
    if st.session_state['signal_history'].empty: 
        return
        
    df = st.session_state['signal_history']
    updates_made = False
    
    # Filtriamo solo i trade "In Corso"
    active_rows = df[df['Stato'] == 'In Corso']
    
    for idx, row in active_rows.iterrows():
        try:
            # 1. Recupero Prezzo Real-Time da IQ Option
            curr_p = get_last_price_iq(row['Asset'])
            
            if curr_p is None:
                continue
                
            entry_p = float(str(row['Prezzo']).replace(',', '.'))
            sl_p = float(str(row['SL']).replace(',', '.'))
            tp_p = float(str(row['TP']).replace(',', '.'))
            inv = float(str(row['Investimento €']).replace(',', '.'))

            # 2. Calcolo PNL e Controllo Glitch
            perc, euro, is_glitch = calcola_pnl_protetto(entry_p, curr_p, row['Direzione'], inv)
            
            if is_glitch:
                continue # Salta il calcolo se il dato è sporco

            # 3. Logica di Uscita (Target o Stop Loss)
            new_status = None
            if row['Direzione'] == 'COMPRA':
                if curr_p >= tp_p: new_status = '✅ TARGET'
                elif curr_p <= sl_p: new_status = '❌ STOP LOSS'
            else: # VENDI
                if curr_p <= tp_p: new_status = '✅ TARGET'
                elif curr_p >= sl_p: new_status = '❌ STOP LOSS'

            # 4. Chiusura Posizione su IQ Option
            if new_status:
                iq_id = row.get('IQ_ID')
                chiusura_effettiva = False
                
                if st.session_state.get('iq_bot') and iq_id:
                    # Inviamo il comando di chiusura al broker
                    chiusura_effettiva = st.session_state['iq_bot'].chiudi_posizione(iq_id)
                
                # Aggiorniamo il database locale
                df.at[idx, 'Stato'] = new_status
                df.at[idx, 'Risultato €'] = f"{euro:+.2f}"
                updates_made = True
                
                # Feedback Audio e Notifica
                play_close_sound()
                msg = f"🔔 **CHIUSURA {new_status}**\nAsset: {row['Asset']}\nNetto: {euro:+.2f}€"
                send_telegram_msg(msg)

        except Exception as e:
            print(f"Errore update {row['Asset']}: {e}")
            continue 
        
    if updates_made:
        st.session_state['signal_history'] = df
        save_history_permanently()

def esegui_ordine_reale(label, direzione, prezzo, tp, sl, inv):
    bot = st.session_state['iq_bot']
    # Esegue l'ordine tramite il modulo IQHandler
    id_ordine = bot.apri_posizione(label, inv, direzione.lower(), tp, sl)
    
    if id_ordine:
        nuovo_trade = {
            'DataOra': datetime.now(rome_tz).strftime("%H:%M:%S"),
            'Asset': label,
            'Direzione': direzione,
            'Prezzo': prezzo,
            'SL': sl,
            'TP': tp,
            'Stato': 'In Corso',
            'IQ_ID': id_ordine,
            'Investimento €': f"{inv:.2f}",
            'Risultato €': "0.00",
            'Protezione': 'Standard'
        }
        st.session_state['signal_history'] = pd.concat([pd.DataFrame([nuovo_trade]), st.session_state['signal_history']], ignore_index=True)
        save_history_permanently()
        invia_telegram(f"🚀 **ORDINE ESEGUITO**\nAsset: {label}\nTipo: {direzione}\nInvestimento: €{inv}")

def run_sentinel_optimized():
    if not st.session_state.get('trading_attivo', True):
        return

    bot = st.session_state.get('iq_bot')
    if not bot or not bot.connected:
        return

    api = bot.api
    debug_list = []
    balance_real = api.get_balance()

    for label, asset_iq in asset_map.items():
        try:
            candles = api.get_candles(asset_iq, 60, 100, time_lib.time())
            if not candles: continue
            
            df = pd.DataFrame(candles)
            bb = ta.bbands(df['close'], length=20, std=2)
            df['rsi'] = ta.rsi(df['close'], length=14)
            adx = ta.adx(df['high'], df['low'], df['close'], length=14)
            
            curr_p = df['close'].iloc[-1]
            curr_rsi = df['rsi'].iloc[-1]
            curr_adx = adx['ADX_14'].iloc[-1]
            upper_bb = bb['BBU_20_2.0'].iloc[-1]
            lower_bb = bb['BBL_20_2.0'].iloc[-1]

            decision = None
            if curr_p <= lower_bb and curr_rsi < 35 and curr_adx < 30:
                decision = "COMPRA"
            elif curr_p >= upper_bb and curr_rsi > 65 and curr_adx < 30:
                decision = "VENDI"

            if decision:
                # Evita duplicati
                hist = st.session_state['signal_history']
                if hist[(hist['Asset'] == label) & (hist['Stato'] == 'In Corso')].empty:
                    inv = balance_real * (st.session_state.get('risk_val', 2) / 100)
                    # Calcolo semplificato TP/SL (puoi usare ATR se disponibile)
                    dist = curr_p * 0.001 
                    tp_val = curr_p + dist if decision == "COMPRA" else curr_p - dist
                    sl_val = curr_p - dist if decision == "COMPRA" else curr_p + dist
                    
                    esegui_ordine_reale(label, decision, curr_p, tp_val, sl_val, inv)
            
            debug_list.append(f"🔍 {label}: {curr_p:.5f} | RSI: {curr_rsi:.1f}")
        except Exception as e:
            debug_list.append(f"⚠️ {label}: Error")
            
    st.session_state['sentinel_logs'] = debug_list
                    
def get_win_rate():
    if st.session_state['signal_history'].empty:
        return "Nessun dato"
    df = st.session_state['signal_history']
    # Consideriamo conclusi solo quelli che non sono "In Corso"
    closed_trades = df[df['Stato'] != 'In Corso']
    total = len(closed_trades)
    
    if total == 0: return "In attesa di chiusure..."
    
    wins = len(closed_trades[closed_trades['Stato'] == '✅ TARGET'])
    wr = (wins / total) * 100
    return f"Win Rate: {wr:.1f}% ({wins}/{total})"

# --- INIZIALIZZAZIONE STATO (Session State) ---
if 'signal_history' not in st.session_state: 
    st.session_state['signal_history'] = load_history_from_csv()
if 'sentinel_logs' not in st.session_state:
    st.session_state['sentinel_logs'] = []
if 'last_alert' not in st.session_state:
    st.session_state['last_alert'] = None
if 'last_scan_status' not in st.session_state:
    st.session_state['last_scan_status'] = "In attesa..."

def get_equity_data():
    """Calcola l'andamento del saldo sommando i risultati reali registrati"""
    # 1. Partiamo dal saldo iniziale impostato nella sidebar
    initial_balance = st.session_state.get('balance_val', 1000)
    equity_curve = [initial_balance]
    
    if st.session_state['signal_history'].empty:
        return pd.Series(equity_curve)
    
    # 2. Ordiniamo dal più vecchio al più recente per costruire la curva
    # Nota: Assumiamo che i trade più vecchi siano in fondo, quindi invertiamo se necessario
    # Nel tuo script salvi i nuovi in cima (concat), quindi per la curva temporale dobbiamo invertire (`iloc[::-1]`)
    df_sorted = st.session_state['signal_history'].iloc[::-1]
    
    current_bal = initial_balance
    
    for _, row in df_sorted.iterrows():
        # Prendiamo il valore dalla colonna 'Risultato €'
        val_str = str(row['Risultato €'])
        
        # Puliamo la stringa (rimuoviamo simbolo € o spazi se presenti)
        val_clean = val_str.replace('€', '').replace(',', '.').strip()
        
        try:
            val_float = float(val_clean)
        except:
            val_float = 0.0
            
        # 3. Sommiamo SOLO se il trade è concluso (quindi ha un risultato diverso da 0 o vuoto)
        # Consideriamo validi tutti gli stati di chiusura
        if row['Stato'] in ['✅ TARGET', '❌ STOP LOSS', '🖐️ CHIUSURA MANUALE', '🛡️ SL DINAMICO']:
            current_bal += val_float
            
        equity_curve.append(current_bal)
        
    return pd.Series(equity_curve)

# --- LOGICA DI ESECUZIONE CICLICA ---
if st.session_state.get('trading_attivo'):
    # Questo viene eseguito ogni volta che la pagina si aggiorna (ogni 60s)
    run_sentinel_optimized() 
    update_signal_outcomes() # Controlla se i trade aperti hanno toccato TP o SL

    # --- CONTROLLO REPORT VENERDÌ (Friday Report) ---
    now = get_now_rome()
    # Controlliamo se è Venerdì (weekday 4), ore 22:00, e non l'abbiamo già inviato
    if now.weekday() == 4 and now.hour == 22 and now.minute == 0:
        if st.session_state.get('last_report_sent') != now.strftime("%Y-%m-%d"):
            invia_report_settimanale()
            st.session_state['last_report_sent'] = now.strftime("%Y-%m-%d")


st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ Sicurezza Sistema")

# Tasto dinamico per attivare/disattivare
if st.session_state['trading_attivo']:
    if st.sidebar.button("🛑 STOP TOTALE BOT", use_container_width=True, type="primary"):
        st.session_state['trading_attivo'] = False
        send_telegram_msg("⚠️ **SISTEMA SOSPESO**: Kill-switch attivato manualmente.")
        st.rerun()
else:
    if st.sidebar.button("🚀 RIATTIVA SISTEMA", use_container_width=True):
        st.session_state['trading_attivo'] = True
        send_telegram_msg("✅ **SISTEMA RIATTIVATO**: Il bot riprende l'analisi.")
        st.rerun()

# Stato visivo
status_color = "green" if st.session_state['trading_attivo'] else "red"
st.sidebar.markdown(f"<p style='text-align:center; color:{status_color}; font-weight:bold;'>Stato: {'OPERATIVO' if st.session_state['trading_attivo'] else 'SOSPESO'}</p>", unsafe_allow_html=True)

st.sidebar.markdown("---")

st.sidebar.header("🛠 Trading Desk (1m)")
balance = st.sidebar.number_input("**Conto (€)**", value=1000, key="balance_val")
risk_pc = st.sidebar.slider("**Investimento %**", 0.5, 5.0, 2.0, step=0.5, key="risk_val")

# --- 5. SIDEBAR ---

# Countdown Testuale e Barra Rossa Animata
st.sidebar.markdown("⏳ **Prossimo Scan**")

# CSS per la barra che si riempie in 60 secondi
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
            height: 100%; background-color: #ff4b4b; width: 0%;
            animation: progressFill 60s linear infinite;
            box-shadow: 0 0 10px #ff4b4b;
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

# Usiamo un contenitore con colore dinamico
if "⚠️" in status:
    st.sidebar.error(status)
elif "🔍" in status:
    st.sidebar.success(status)
else:
    st.sidebar.info(status)

# Parametri Input
selected_label = st.sidebar.selectbox("**Asset**", list(asset_map.keys()))
pair = asset_map[selected_label]

# --- Sotto il widget risk_pc ---
st.sidebar.markdown(
    """
    <div style='background-color: rgba(255, 152, 0, 0.1); 
                border: 1px solid #ff9800; 
                padding: 10px; 
                border-radius: 5px; 
                margin-top: 10px;'>
        <span style='color: #ff9800; font-weight: bold; font-size: 0.85em;'>
            🟠 IQOption Mode: ATTIVA
        </span><br>
        <small style='color: #888; font-size: 0.75em;'>
            Commissioni e Spread simulati inclusi.
        </small>
    </div>
    """, 
    unsafe_allow_html=True
)

# --- CALCOLO INVESTIMENTO SIMULATO ---
investimento_simulato = balance * (risk_pc / 100)
saldo_residuo = balance - investimento_simulato

st.sidebar.markdown("---")
st.sidebar.subheader("💰 Gestione Capitale")
#col_cap1, col_cap2 = st.sidebar.columns(2)
#col_cap1.metric("Conto", f"€ {balance:.2f}")
#col_cap2.metric("Investimento", f"€ {investimento_simulato:.2f}")

st.sidebar.metric("Conto iniziale", f"€ {balance:.2f}")
st.sidebar.metric("Investimento per operazione", f"€ {investimento_simulato:.2f}")


#st.sidebar.info(f"💳 **Saldo Attuale Operativo**: € {saldo_residuo:.2f}")

st.sidebar.markdown("---")

# --- LOGICA DINAMICA ANALISI OPERATIVA ---
st.sidebar.subheader("📊 Analisi Operativa")

# Recuperiamo il DataFrame della cronologia
df_hist = st.session_state.get('signal_history', pd.DataFrame())

if not df_hist.empty:
    # 1. Conta i trade con stato 'In Corso' o 'APERTO'
    pendenti = len(df_hist[df_hist['Stato'].isin(['In Corso', 'APERTO'])])
    
    # 2. Conta i trade già conclusi (Target, Stop Loss o Chiusi manualmente)
    chiusi = len(df_hist[df_hist['Stato'].isin(['✅ TARGET', '❌ STOP LOSS', '🖐️ CHIUSO MAN.'])])
    
    # 3. Conta i trade vinti per il calcolo veloce (opzionale)
    vinti = len(df_hist[df_hist['Stato'] == '✅ TARGET'])
else:
    pendenti = 0
    chiusi = 0
    vinti = 0

# Visualizzazione Dinamica
st.sidebar.write(f"⏳ **Trade Pendenti:** {pendenti}")
st.sidebar.write(f"✅ **Trade Chiusi:** {chiusi}")

# Un piccolo tocco extra: mostriamo quanti ne abbiamo vinti sul totale dei chiusi
if chiusi > 0:
    st.sidebar.caption(f"🏆 Successi: {vinti} su {chiusi}")

st.sidebar.markdown("---")

# --- SIDEBAR PERFORMANCE ---
st.sidebar.subheader("🏆 Performance")

equity_series = get_equity_data()
current_equity = equity_series.iloc[-1]
initial_bal = balance if balance > 0 else 1000
total_return = ((current_equity - initial_bal) / initial_bal) * 100

# Calcolo Drawdown
max_val = equity_series.max()
dd = ((current_equity - max_val) / max_val) * 100 if max_val > 0 else 0

# Visualizzazione Metriche
st.sidebar.metric("Saldo Attuale Operativo", f"€ {current_equity:.2f}", delta=f"{total_return}%")
st.sidebar.metric("Drawdown Massimo", f"{dd:.2f}%", delta_color="inverse")

# Grafico Equity (Piccolo e pulito)
#fig_equity = go.Figure()
#fig_equity.add_trace(go.Scatter(y=equity_series, mode='lines', fill='tozeroy', line=dict(color='#00ffcc')))
#fig_equity.update_layout(height=100, margin=dict(l=0,r=0,t=0,b=0), xaxis_visible=False, yaxis_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
#st.sidebar.plotly_chart(fig_equity, use_container_width=True, config={'displayModeBar': False})

# Dettagli operazione selezionata (se presente)
active_trades = st.session_state['signal_history'][st.session_state['signal_history']['Stato'] == 'In Corso']
if not active_trades.empty:
    st.sidebar.warning("⚡ Ultima Operazione Attiva")
    last_t = active_trades.iloc[0]
    st.sidebar.write(f"Asset: **{last_t['Asset']}**")
    st.sidebar.write(f"SL: `{last_t['SL']}` | TP: `{last_t['TP']}`")

# 1. Recupero trade attivi (Assicurati che lo Stato sia 'In Corso' come da tua immagine)
active_trades = st.session_state['signal_history'][st.session_state['signal_history']['Stato'] == 'In Corso']

st.sidebar.markdown("---")
st.sidebar.subheader("⚡ Monitor Real-Time")

if active_trades.empty:
    st.sidebar.info("💤 In attesa del primo trade")
else:
    # Sostituisci il ciclo for dei trade attivi nella sidebar con questo
    for index, trade in active_trades.iterrows():
        try:
            curr_p = get_last_price_iq(trade['Asset'])
            if curr_p is not None:
                entry_p = float(str(trade['Prezzo']).replace(',', '.').strip())
                inv = float(str(trade['Investimento €']).replace(',', '.').strip())
                
                diff_prezzo = curr_p - entry_p if trade['Direzione'] in ["BUY", "COMPRA"] else entry_p - curr_p
                latente_perc = (diff_prezzo / entry_p) * 100
                latente_euro = (inv * latente_perc) / 100
    
                color = "#00FFCC" if latente_euro >= 0 else "#FF4B4B"
                    
                st.sidebar.markdown(f"""
                    <div style="border-left: 4px solid {color}; padding: 8px; background: rgba(255,255,255,0.05); border-radius: 5px; margin-bottom: 5px;">
                        <b style="font-size: 0.85em;">{trade['Asset']} | {trade['Direzione']}</b><br>
                        <span style="color:{color}; font-size: 1.1em; font-weight: bold;">{latente_perc:+.2f}% ({latente_euro:+.2f}€)</span>
                    </div>
                """, unsafe_allow_html=True)
    
                if st.sidebar.button(f"✖ Chiudi {trade['Asset']}", key=f"close_{index}"):
                    iq_id = trade.get('IQ_ID')
                    if st.session_state['iq_bot'] and iq_id:
                        st.session_state['iq_bot'].chiudi_posizione(iq_id)
                    st.session_state['signal_history'].at[index, 'Stato'] = 'CHIUSO MAN.'
                    st.session_state['signal_history'].at[index, 'Risultato €'] = f"{latente_euro:+.2f}"
                    st.rerun()
        except Exception as e:
            st.sidebar.caption(f"⏳ Aggiornamento {trade['Asset']}...")

                if st.sidebar.button(f"✖ Chiudi {trade['Asset']}", key=f"close_{index}"):
                
                # CHIUSURA IQ
                iq_id = trade.get('IQ_ID')
                if st.session_state['iq_bot'] and iq_id:
                    st.session_state['iq_bot'].chiudi_posizione(iq_id)
                    st.toast("Chiusura manuale inviata a IQ")
                    
                st.session_state['signal_history'].at[index, 'Stato'] = 'CHIUSO MAN.'
                st.rerun()

st.sidebar.markdown("---")
# ... (restante codice sidebar: sessioni, win rate, reset)
st.sidebar.subheader("🌍 Sessioni di Mercato")
for s_name, is_open in get_session_status().items():
    color = "🟢" if is_open else "🔴"
    status_text = "APERTO" if is_open else "CHIUSO"
    st.sidebar.markdown(f"**{s_name}** <small>: {status_text}</small> {color}",
unsafe_allow_html=True)
   
# --- TASTO ESPORTAZIONE DATI ---
#st.sidebar.markdown("---")
#st.sidebar.subheader("💾 Backup Report")

#if not st.session_state['signal_history'].empty:
    #csv_data = st.session_state['signal_history'].to_csv(index=False).encode('utf-8')
    #st.sidebar.download_button(
        #label="📥 SCARICA CRONOLOGIA CSV",
        #data=csv_data,
        #file_name=f"Trading_Report_{get_now_rome().strftime('%Y%m%d_%H%M')}.csv",
        #mime="text/csv",
        #use_container_width=True
    #)
#else:
    #st.sidebar.info("Nessun dato da esportare")

# --- TASTO TEST TELEGRAM ---
st.sidebar.markdown("---")
if st.sidebar.button("✈️ TEST NOTIFICA TELEGRAM"):
    test_msg = "🔔 **SENTINEL TEST**\nIl sistema di notifiche è operativo! 🚀"
    send_telegram_msg(test_msg)
    st.sidebar.success("Segnale di test inviato!")

# --- TASTO TEST DINAMICO ---
if st.sidebar.button("🔊 TEST ALERT COMPLETO"):
    # Calcolo dinamico basato sui tuoi cursori attuali
    current_bal = st.session_state.get('balance_val', 1000)
    current_r = st.session_state.get('risk_val', 2.0)
    inv_test = current_bal * (current_r / 100)
    
    test_data = {
        'DataOra': get_now_rome().strftime("%Y-%m-%d %H:%M:%S"),
        'Asset': 'TEST/EUR', 
        'Direzione': 'VENDI', 
        'Prezzo': '1.0950', 
        'TP': '1.0900', 
        'SL': '1.0980', 
        'Stato': 'In Corso',
        'Investimento €': f"{inv_test:.2f}", # Ora legge il 2% di 1000 = 20.00
        'Risultato €': "0.00",
        'Costo Spread €': f"{(inv_test):.2f}",
        'Stato_Prot': 'Iniziale',
        'Protezione': 'Trailing 3/6%'
    }
    
    st.session_state['signal_history'] = pd.concat(
        [pd.DataFrame([test_data]), st.session_state['signal_history']], 
        ignore_index=True
    )
    st.session_state['last_alert'] = test_data
    if 'alert_notified' in st.session_state: del st.session_state['alert_notified']
    st.rerun()

# Reset Sidebar
st.sidebar.markdown("---")
with st.sidebar.popover("🗑️ **Reset Cronologia**"):
    st.warning("Sei sicuro? Questa azione cancellerà tutti i segnali salvati.")

    if st.button("SÌ, CANCELLA ORA"):
        st.session_state['signal_history'] = pd.DataFrame(columns=['DataOra', 'Asset', 'Direzione', 'Prezzo', 'SL', 'TP', 'Size', 'Stato'])
        save_history_permanently() # Questo sovrascrive il file CSV con uno vuoto
        st.rerun()

st.sidebar.markdown("---")

#if st.sidebar.button("TEST ALERT"):
    #st.session_state['last_alert'] = {'Asset': 'TEST/EUR', 'Direzione': 'COMPRA', 'Prezzo': '1.0000', 'TP': '1.0100', 'SL': '0.9900', 'Protezione': 'Standard'}
    #if 'alert_start_time' in st.session_state: del st.session_state['alert_start_time']
    #st.rerun()

#st.sidebar.markdown("---")

# --- 6. POPUP ALERT (VERSIONE NATIVA - NON BLOCCA SIDEBAR) ---
if st.session_state.get('last_alert'):
    # Inizializzazione Timer
    if 'alert_start_time' not in st.session_state:
        st.session_state['alert_start_time'] = time_lib.time()
        play_notification_sound()

    elapsed = time_lib.time() - st.session_state['alert_start_time']
    countdown = max(0, int(30 - elapsed))
    
    # Auto-chiusura
    if elapsed > 30:
        st.session_state['last_alert'] = None
        if 'alert_start_time' in st.session_state: del st.session_state['alert_start_time']
        st.rerun()

    if st.session_state.get('last_alert'):
        alert = st.session_state['last_alert']
        color = "success" if alert['Direzione'] == 'COMPRA' else "error"
        hex_color = "#00ffcc" if alert['Direzione'] == 'COMPRA' else "#ff4b4b"

        # Creiamo un contenitore in cima alla pagina
        with st.container():
            st.markdown(f"""
                <div style="background-color: #000; border: 3px solid {hex_color}; padding: 20px; border-radius: 15px; margin-bottom: 20px; text-align: center; box-shadow: 0 0 20px {hex_color}44;">
                    <h2 style="color: white; margin: 0;">🚀 NUOVO SEGNALE: {alert['Asset']}</h2>
                    <h1 style="color: {hex_color}; margin: 5px 0;">{alert['Direzione']} @ {alert['Prezzo']}</h1>
                    <p style="color: #888; margin: 0;">TP: {alert['TP']} | SL: {alert['SL']} | Auto-chiusura in {countdown}s</p>
                </div>
            """, unsafe_allow_html=True)
            
            # Tasto CHIUDI nativo di Streamlit
            if st.button("✅ HO VISTO, CHIUDI ALERT", key="close_manual", use_container_width=True):
                st.session_state['last_alert'] = None
                if 'alert_start_time' in st.session_state: del st.session_state['alert_start_time']
                st.rerun()
        
        st.divider() # Separa l'alert dal resto del grafico

# --- 7. BODY PRINCIPALE ---
# Banner logic
banner_path = "banner1.png"
if os.path.exists(banner_path):
    st.image(banner_path, use_container_width=True)
else:
    st.markdown('<div style="background: linear-gradient(90deg, #0f0c29, #302b63, #24243e); padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #00ffcc;"><h1 style="color: #00ffcc; margin: 0;">📊 FOREX MOMENTUM PRO AI</h1><p style="color: white; opacity: 0.8; margin:0;">Sentinel AI Engine • Forex & Crypto Analysis</p></div>', unsafe_allow_html=True)

if not st.session_state['trading_attivo']:
    st.warning("⚠️ **IL BOT È IN PAUSA**: Nessuna operazione verrà aperta o gestita finché non riattivi il sistema dalla sidebar.")

st.info(f"🛰️ **Sentinel AI Attiva**: Monitoraggio in corso su {len(asset_map)} asset Forex in tempo reale (1m).")
st.caption(f"Ultimo aggiornamento globale: {get_now_rome().strftime('%Y-%m-%d %H:%M:%S')}")

st.markdown("---")
#st.subheader("📈 Grafico in tempo reale")
st.subheader(f"📈 Grafico {selected_label} (1m) con BB e RSI")

p_unit, price_fmt, p_mult, a_type = get_asset_params(pair)
df_rt = get_realtime_data(pair) 
df_d = yf.download(pair, period="1y", interval="1d", progress=False)

if df_rt is not None and not df_rt.empty and df_d is not None and not df_d.empty:
    
    # Pulizia dati
    if isinstance(df_d.columns, pd.MultiIndex): df_d.columns = df_d.columns.get_level_values(0)
    df_d.columns = [c.lower() for c in df_d.columns]
    
    # Calcolo indicatori
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

    # --- COSTRUZIONE GRAFICO ---
    p_df = df_rt.tail(60)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.75, 0.25])
    
    # Candele
    fig.add_trace(go.Candlestick(
        x=p_df.index, open=p_df['open'], high=p_df['high'], 
        low=p_df['low'], close=p_df['close'], name='Prezzo'
    ), row=1, col=1)
    
    # Bande Bollinger
    fig.add_trace(go.Scatter(x=p_df.index, y=p_df[c_up], line=dict(color='rgba(0, 191, 255, 0.6)', width=1), name='Upper BB'), row=1, col=1)
    fig.add_trace(go.Scatter(x=p_df.index, y=p_df[c_mid], line=dict(color='rgba(0, 0, 0, 0.3)', width=1), name='BBM'), row=1, col=1)
    fig.add_trace(go.Scatter(x=p_df.index, y=p_df[c_low], line=dict(color='rgba(0, 191, 255, 0.6)', width=1), fill='tonexty', fillcolor='rgba(0, 191, 255, 0.15)', name='Lower BB'), row=1, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=p_df.index, y=p_df['rsi'], line=dict(color='#ffcc00', width=2), name='RSI'), row=2, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#00ff00", row=2, col=1)

    # --- AGGIUNTA GRIGLIA VERTICALE (OGNI 10 MINUTI) ---
    for t in p_df.index:
        if t.minute % 10 == 0:
            fig.add_vline(x=t, line_width=0.5, line_dash="solid", line_color="rgba(0, 0, 0, 0.3)", layer="below")

    # Layout Grafico
    fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=30,b=0), legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig, use_container_width=True)

    # 4. Metriche Base
    c_met1, c_met2 = st.columns(2)
    c_met1.metric(label=f"Prezzo {selected_label}", value=price_fmt.format(curr_p))
    c_met2.metric(label="RSI (5m)", value=f"{curr_rsi:.1f}", delta="Ipercomprato" if curr_rsi > 70 else "Ipervenduto" if curr_rsi < 30 else "Neutro", delta_color="inverse")
    
    st.caption(f"📢 RSI Daily: {rsi_val:.1f} | Divergenza: {detect_divergence(df_d)}")

    # --- VISUALIZZAZIONE METRICHE AVANZATE (ADX & AI) ---
    adx_df_ai = ta.adx(df_rt['high'], df_rt['low'], df_rt['close'], length=14)
    curr_adx_ai = adx_df_ai['ADX_14'].iloc[-1]

    st.markdown("---")
    st.subheader("🕵️ Sentinel Market Analysis")
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("RSI Daily", f"{rsi_val:.1f}", detect_divergence(df_d))
    col_b.metric("Sentinel Score", f"{score}/100")
    adx_emoji = "🔴" if curr_adx_ai > 30 else "🟡" if curr_adx_ai > 20 else "🟢"
    col_c.metric("Forza Trend (ADX)", f"{curr_adx_ai:.1f}", adx_emoji)

    # --- TABELLA GUIDA ADX COLORATA (FULL WIDTH) ---
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

    # 1. Applichiamo lo stile e nascondiamo l'indice
    # 2. Aggiungiamo 'set_table_attributes' per forzare la larghezza al 100%
    styled_adx_html = (adx_guide.style
                       .apply(highlight_adx, axis=1)
                       .hide(axis='index')
                       .set_table_attributes('style="width:100%; border-collapse: collapse; text-align: left;"')
                       .to_html())

    # Visualizziamo con unsafe_allow_html
    st.markdown(styled_adx_html, unsafe_allow_html=True)

# --- NEL CORPO PRINCIPALE (Sotto il grafico o le metriche ADX) ---

st.markdown("---")
tab_trading, tab_stats = st.tabs(["📈 Terminale Operativo", "📊 Statistiche Avanzate"])

with tab_trading:
    # Sposta qui la visualizzazione della Cronologia Segnali (Punto 9)
    # e le metriche real-time che avevi nel body.
    pass

with tab_stats:
    st.subheader("🕵️ Analisi Performance Sentinel")
    performance_data = get_advanced_stats()
    
    if performance_data:
        stats, asset_perf, hourly_perf = performance_data
        
        # Righe di metriche KPI
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Profitto Netto", f"€ {stats['total_pnl']:.2f}")
        c2.metric("Win Rate", f"{stats['win_rate']:.1f}%")
        c3.metric("Top Asset", stats['best_asset'])
        c4.metric("Ora Critica", stats['worst_hour'], delta="Peggior resa", delta_color="inverse")
        
        # Visualizzazione Grafica
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.write("**Performance per Asset (€)**")
            st.bar_chart(asset_perf) # Streamlit bar chart nativo
        with col_g2:
            st.write("**Profitto per Fascia Oraria**")
            st.line_chart(hourly_perf) # Utile per vedere quando il bot "soffre"
    else:
        st.info("📊 Dati insufficienti. Le statistiche appariranno dopo la chiusura del primo trade.")

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

# --- 9. CRONOLOGIA SEGNALI (CON COLORI DINAMICI) ---
st.markdown("---")
st.subheader("📜 Cronologia Segnali")

if not st.session_state['signal_history'].empty:
    display_df = st.session_state['signal_history'].copy()
    display_df = display_df.sort_values(by='DataOra', ascending=False)

    try:
        # Applichiamo gli stili a colonne diverse
        styled_df = display_df.style.map(
            style_status, subset=['Stato']
        ).map(
            style_protection, subset=['Protezione']
        )

        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
            column_order=[
                'DataOra', 'Asset', 'Direzione', 'Prezzo', 
                'TP', 'SL', 'Stato', 'Protezione', 
                'Investimento €', 'Risultato €'
            ]
        )
    except Exception as e:
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    # 4. Pulsante esportazione (Sempre dentro l'IF, ma fuori dal TRY/EXCEPT)
    st.write("") 
    csv_data = display_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Esporta Cronologia (CSV)",
        data=csv_data,
        file_name=f"trading_history_{datetime.now(rome_tz).strftime("%Y-%m-%d %H:%M:%S")}.csv",
        mime="text/csv",
        use_container_width=True
    )
    
# 5. Se la cronologia è vuota (allineato all'IF iniziale)
else:
    st.info("Nessun segnale registrato.")
