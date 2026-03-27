import streamlit as st
import pandas_ta as ta
import websocket
import json
import time

# --- CONFIGURAZIONE CORE ---
DERIV_APP_ID = "1089"  # ID Pubblico per bypassare blocchi EU
INITIAL_STAKE = 100.0
MARTINGALE_MULTIPLIERS = [1.0, 2.1, 4.5] # Base, Step 1, Step 2

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

# --- 2. LOGICA SEGNALI OTTIMIZZATA (2.5 Std Dev) ---
def get_signals(df):
    # Parametri aggressivi per Sintetici
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

# --- 4. ESECUZIONE TRADE ---
def execute_deriv_trade(token, symbol, direction, stake, duration=60):
    try:
        ws = websocket.create_connection(f"wss://ws.binaryws.com/websockets/v3?app_id={DERIV_APP_ID}")
        ws.send(json.dumps({"authorize": token}))
        auth = json.loads(ws.recv())
        
        if "error" in auth: return False, auth["error"]["message"]
        
        req = {
            "buy": 1,
            "price": float(stake),
            "parameters": {
                "amount": float(stake),
                "basis": "stake",
                "contract_type": "CALL" if direction == "BUY" else "PUT",
                "currency": "USD",
                "duration": int(duration),
                "duration_unit": "s",
                "symbol": to_deriv_symbol(symbol)
            }
        }
        ws.send(json.dumps(req))
        res = json.loads(ws.recv())
        ws.close()
        
        if "error" in res: return False, res["error"]["message"]
        return True, res["buy"]["contract_id"]
    except Exception as e:
        return False, str(e)

# --- NELLA TUA DASHBOARD STREAMLIT ---
current_stake = handle_martingale_ui()

# Esempio di gestione esito (da inserire nel tuo loop di controllo)
# if trade_perso:
#     st.session_state.mtg_step = min(st.session_state.mtg_step + 1, 2)
# elif trade_vinto:
#     st.session_state.mtg_step = 0
