import streamlit as st
import pandas as pd
import pandas_ta as ta
import time as time_module
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import websocket

# --- 1. CONFIGURAZIONI GLOBALI ---
DERIV_APP_ID = "1089"
ALL_PAIRS = ["R_50", "R_75", "R_100", "1HZ50V", "1HZ75V", "1HZ100V"]

st.set_page_config(page_title="Sentinel AI - Synthetic Pro", layout="wide")

# Inizializzazione Session State
if 'scanner_on' not in st.session_state: 
    st.session_state.scanner_on = False
if 'active_contracts' not in st.session_state: 
    st.session_state.active_contracts = {}

# --- 2. FUNZIONI API DERIV (UNIFICATE) ---
def deriv_call(request, token=None):
    """Gestisce tutte le comunicazioni con Deriv aprendo una connessione sicura."""
    try:
        ws = websocket.create_connection(f"wss://ws.binaryws.com/websockets/v3?app_id={DERIV_APP_ID}", timeout=10)
        
        # Se serve l'autorizzazione (es. per trade o bilancio), invia prima il token
        if token:
            ws.send(json.dumps({"authorize": token}))
            auth_res = json.loads(ws.recv())
            if "error" in auth_res:
                ws.close()
                return {"error": auth_res["error"]["message"]}
        
        # Invia la richiesta principale (candele, buy, sell, ecc.)
        ws.send(json.dumps(request))
        response = json.loads(ws.recv())
        ws.close()
        return response
    except Exception as e:
        return {"error": str(e)}

# --- 3. LOGICA DI SEGNALE (TRIPLA CONVERGENZA) ---
def check_signal(df, rsi_b, rsi_s, bb_std):
    """Analizza le candele e restituisce BUY, SELL o WAIT."""
    if len(df) < 50: return "WAIT"
    
    # Calcolo Indicatori
    df['EMA_20'] = ta.ema(df['close'], length=20)
    df['EMA_50'] = ta.ema(df['close'], length=50)
    df['RSI'] = ta.rsi(df['close'], length=7)
    bb = ta.bbands(df['close'], length=20, std=bb_std)
    
    # Identificazione dinamica colonne Bollinger Bands
    bbl_col = bb.columns[0] # Lower Band
    bbu_col = bb.columns[2] # Upper Band
    
    last = df.iloc[-1]
    
    # Logica BUY: Trend UP (Sopra EMA50) + Prezzo tocca BB Lower + RSI Ipervenduto
    if (last['close'] > last['EMA_50']) and (last['close'] <= bb[bbl_col].iloc[-1]) and (last['RSI'] <= rsi_b):
        return "BUY"
    
    # Logica SELL: Trend DOWN (Sotto EMA50) + Prezzo tocca BB Upper + RSI Ipercomprato
    if (last['close'] < last['EMA_50']) and (last['close'] >= bb[bbu_col].iloc[-1]) and (last['RSI'] >= rsi_s):
        return "SELL"
        
    return "WAIT"

# --- 4. INTERFACCIA E SIDEBAR ---
with st.sidebar:
    st.header("🔑 Connessione API")
    token_input = st.text_input("Deriv API Token", type="password", help="Token con permessi 'Trading Control'")
    
    # Tasto per Test Connessione
    if st.button("🧪 Test Connessione", use_container_width=True):
        if not token_input:
            st.warning("Inserisci il token per testare.")
        else:
            res = deriv_call({"balance": 1}, token_input)
            if "error" in res:
                st.error(f"Errore: {res['error']}")
            else:
                st.success(f"✅ Connesso! Bilancio: {res['balance']['balance']} USD")

    st.divider()
    st.header("🎮 Trading Control Panel")
    if st.button("🚀 AVVIA SCANNER" if not st.session_state.scanner_on else "🛑 FERMA SCANNER", type="primary", use_container_width=True):
        st.session_state.scanner_on = not st.session_state.scanner_on
    
    auto_trade = st.toggle("🤖 Esecuzione Automatica", value=False)
    
    st.divider()
    st.subheader("💰 Gestione Rischio")
    stake = st.number_input("Stake ($)", value=10.0, step=1.0)
    multiplier = st.selectbox("Moltiplicatore", [10, 20, 30, 50, 100], index=2)
    tp_val = st.slider("Take Profit ($)", 1.0, 50.0, 5.0)
    sl_val = st.slider("Stop Loss ($)", 1.0, 10.0, 5.0)
    
    st.divider()
    st.subheader("📈 Sensibilità Algoritmo")
    rsi_b = st.number_input("RSI Buy Level", value=20)
    rsi_s = st.number_input("RSI Sell Level", value=80)
    bb_dev = st.number_input("BB Std Dev", value=2.2, step=0.1)


# --- 5. MAIN DASHBOARD ---
st.title("🛡️ Sentinel AI - Tripla Convergenza")
st.caption("Analisi Algoritmica H24 per Indici Sintetici (Deriv)")

if not token_input and st.session_state.scanner_on:
    st.warning("⚠️ Scanner avviato, ma Token API mancante. Le operazioni di trading non funzioneranno.")

if st.session_state.scanner_on:
    st.subheader("📡 Monitoraggio Live")
    cols = st.columns(len(ALL_PAIRS))
    
    # 5.1 CICLO DI SCANSIONE ASSET
    for i, pair in enumerate(ALL_PAIRS):
        # Nessun token richiesto per scaricare candele pubbliche
        res_candles = deriv_call({"ticks_history": pair, "count": 100, "end": "latest", "style": "candles", "granularity": 60})
        
        if "candles" in res_candles:
            df = pd.DataFrame(res_candles["candles"])
            signal = check_signal(df, rsi_b, rsi_s, bb_dev)
            
            with cols[i]:
                st.metric(pair, f"{df['close'].iloc[-1]}", delta=signal if signal != "WAIT" else None)
            
            # 5.2 ESECUZIONE TRADE (Se automatico, se c'è segnale, e se non abbiamo già posizioni aperte per questo asset)
            if signal != "WAIT" and auto_trade and token_input:
                if pair not in st.session_state.active_contracts:
                    st.info(f"Apertura {signal} su {pair}...")
                    
                    trade_req = {
                        "buy": 1, 
                        "price": float(stake),
                        "parameters": {
                            "amount": float(stake), 
                            "basis": "stake", 
                            "symbol": pair, 
                            "currency": "USD",
                            "multiplier": int(multiplier), 
                            "contract_type": "MULTUP" if signal == "BUY" else "MULTDOWN",
                            "limit_order": {"stop_loss": float(sl_val), "take_profit": float(tp_val)}
                        }
                    }
                    
                    trade_res = deriv_call(trade_req, token_input)
                    
                    if "buy" in trade_res:
                        contract_id = trade_res["buy"]["contract_id"]
                        st.session_state.active_contracts[pair] = contract_id
                        st.success(f"Trade Aperto! ID: {contract_id}")
                    elif "error" in trade_res:
                        st.error(f"Errore apertura: {trade_res['error']}")

    # 5.3 GESTIONE POSIZIONI APERTE
    if st.session_state.active_contracts:
        st.divider()
        st.subheader("📑 Posizioni Attive")
        
        # Trasformiamo il dizionario in lista per poterlo modificare durante l'iterazione
        for p, c_id in list(st.session_state.active_contracts.items()):
            c1, c2 = st.columns([4, 1])
            c1.info(f"Asset: **{p}** | ID Contratto: `{c_id}`")
            
            if c2.button("Chiudi Posizione", key=f"close_{c_id}"):
                close_res = deriv_call({"sell": c_id, "price": 0}, token_input)
                if "sell" in close_res:
                    profit = close_res["sell"]["profit"]
                    st.toast(f"Chiuso {p}! Profitto: {profit} USD")
                    del st.session_state.active_contracts[p]
                    st.rerun() # Forza l'aggiornamento dell'interfaccia dopo la chiusura
                elif "error" in close_res:
                    st.error(f"Errore chiusura: {close_res['error']}")

# --- 6. GRAFICO INTERATTIVO DETTAGLIATO ---
st.divider()
st.subheader("📊 Analisi Tecnica Dettagliata")
selected_pair = st.selectbox("Seleziona Asset da analizzare:", ALL_PAIRS)

# Scarichiamo i dati solo per il grafico
chart_data = deriv_call({"ticks_history": selected_pair, "count": 100, "end": "latest", "style": "candles", "granularity": 60})

if chart_data and "candles" in chart_data:
    df_plot = pd.DataFrame(chart_data["candles"])
    df_plot['EMA_20'] = ta.ema(df_plot['close'], length=20)
    df_plot['EMA_50'] = ta.ema(df_plot['close'], length=50)
    df_plot['RSI'] = ta.rsi(df_plot['close'], length=7)
    bb_plot = ta.bbands(df_plot['close'], length=20, std=bb_dev)
    
    bbl_plot_col = bb_plot.columns[0]
    bbu_plot_col = bb_plot.columns[2]

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
    
    # Prezzo e Medie/Bande
    fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['open'], high=df_plot['high'], low=df_plot['low'], close=df_plot['close'], name="Prezzo"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=bb_plot[bbu_plot_col], line=dict(color='rgba(173, 216, 230, 0.5)'), name="BB Upper"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=bb_plot[bbl_plot_col], line=dict(color='rgba(173, 216, 230, 0.5)'), fill='tonexty', name="BB Lower"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['EMA_50'], line=dict(color='orange', width=2), name="EMA 50 (Trend)"), row=1, col=1)
    
    # RSI
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['RSI'], line=dict(color='magenta'), name="RSI"), row=2, col=1)
    fig.add_hline(y=rsi_b, line_color="green", row=2, col=1)
    fig.add_hline(y=rsi_s, line_color="red", row=2, col=1)

    fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False, title=f"Analisi su {selected_pair} (Timeframe 1m)")
    st.plotly_chart(fig, use_container_width=True)


# --- 7. REFRESH AUTOMATICO (UNICO PUNTO DI LOOP) ---
if st.session_state.scanner_on:
    # Pausa di 10 secondi per evitare di superare i limiti API di Deriv
    time_module.sleep(10)
    st.rerun()
