import streamlit as st
import pandas as pd
import pandas_ta as ta
import time as time_module
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from iqoptionapi.stable_api import IQ_Option
from PIL import Image
import requests
from datetime import datetime, time

# --- CONFIGURAZIONI E TELEGRAM (Tuo codice originale) ---
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")

def send_telegram_signal(signal_type, pair, price, rsi, macd):
    timestamp = datetime.now().strftime("%H:%M:%S")
    message = f"🚀 *SENTINEL AI*\n*{signal_type} - {pair}*\n💰 Prezzo: `{price:.5f}`\n📊 RSI: `{rsi:.1f}`\n⏰ Ora: {timestamp}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=5)
    except: pass

def play_trade_sound(sound_type="buy"):
    sounds = {
        "buy": "https://actions.google.com/sounds/v1/alarms/beep_short.ogg",
        "win": "https://actions.google.com/sounds/v1/cartoon/clink_vibrant.ogg"
    }
    placeholder = st.empty()
    try:
        with placeholder:
            # autoplay=True è fondamentale
            st.audio(sounds.get(sound_type, sounds["buy"]), autoplay=True)
        time_module.sleep(0.2) # Leggermente aumentato per dare tempo al buffer
    except:
        pass
    placeholder.empty()

st.set_page_config(page_title="Sentinel AI", page_icon="🚀", layout="wide")

# Logo
try:
    logo = Image.open("banner.png")
    st.image(logo, use_column_width=True, caption="IQ Signals PRO")
except:
    st.image("https://via.placeholder.com/800x100/0066cc/white?text=SENTINEL+AI", use_column_width=True)

# --- LOGICA DI CONNESSIONE ---
if 'connected' not in st.session_state: st.session_state.connected = False
if 'active_trades' not in st.session_state: st.session_state.active_trades = {}
if 'signal_history' not in st.session_state: st.session_state.signal_history = []
if 'local_balance' not in st.session_state: st.session_state.local_balance = 0

with st.sidebar:
    st.header("⚙️ IQ TRADING PLATFORM")
    if not st.session_state.connected:
        email = st.text_input("Email", value="mago_magoz@libero.it")
        password = st.text_input("Password", type="password")
        tipo_conto = st.radio("Conto", ["DEMO", "REALE"])
        
        if st.button("🔌 CONNETTI"):
            from iqoptionapi.stable_api import IQ_Option
            Iq_obj = IQ_Option(email, password)
            check, reason = Iq_obj.connect()
            
            if check:
                # Imposta Demo o Reale
                mode = "PRACTICE" if tipo_conto == "DEMO" else "REAL"
                Iq_obj.change_balance(mode)
                
                # Salva i dati importanti
                st.session_state.iq = Iq_obj 
                st.session_state.connected = True
                st.session_state.account_type = tipo_conto
                st.session_state.local_balance = Iq_obj.get_balance()
                st.rerun()
    else:
        st.success(f"🟢 {st.session_state.account_type} ATTIVO")
        st.session_state.stake = st.number_input("💰 Stake ($)", value=100.0)
        if st.button("🔴 SCOLLEGA"):
            st.session_state.connected = False
            st.rerun()

        st.divider()
        
        # --- SESSIONI DI MERCATO ---
        now_cet = datetime.now().time()
        st.subheader("🌍 SESSIONI DI MERCATO")
        
        for city, (start, end) in {"LONDRA 🇬🇧": (time(9,0), time(18,0)), "NEW YORK 🇺🇸": (time(14,0), time(23,0)), "SYDNEY 🇦🇺": (time(23,0), time(8,0)), "TOKYO 🇯🇵": (time(1,0), time(10,0))}.items():
            status = "🟢 Open: " if start <= now_cet <= end else "🔴 Closed: "
            st.write(f"{status} {city}")

# --- MAIN DASHBOARD ---
if st.session_state.connected:
    Iq = st.session_state.iq
    
    st.divider()

    st.subheader("👁️ Scanner FOREX")

    # 1. PARAMETRI AGGRESSIVI (MODIFICATI PER RILEVARE DI PIÙ)
    col1, col2, col3 = st.columns(3)
    with col1: 
        rsi_buy = st.number_input("🟢 RSI Buy (Soglia Alta = +Segnali)", value=35) # Alzato da 28
    with col2: 
        rsi_sell = st.number_input("🔴 RSI Sell (Soglia Bassa = +Segnali)", value=65) # Abbassato da 72
    with col3:
        timeframe = st.selectbox("Timeframe", [60, 300], index=0)

    # 2. SCANNER MULTI-PAIR
    st.session_state.scanner = st.toggle("🔍 Attiva Scansione", value=True)

    if st.session_state.scanner:
        ALL_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"]
        
        for pair in ALL_PAIRS:
            try:
                # Recupero dati
                candles = Iq.get_candles(pair, timeframe, 50, time_module.time())
                df = pd.DataFrame(candles)
                df['RSI'] = ta.rsi(df['close'], length=7)
                macd = ta.macd(df['close'], fast=8, slow=17, signal=9)
                
                curr_rsi = df['RSI'].iloc[-1]
                curr_macd = macd['MACD_8_17_9'].iloc[-1]
                curr_sig = macd['MACDs_8_17_9'].iloc[-1]
                price = df['close'].iloc[-1] # <--- Il prezzo viene preso qui

                is_buy = curr_rsi < rsi_buy and curr_macd > curr_sig
                is_sell = curr_rsi > rsi_sell and curr_macd < curr_sig

                # --- LOGICA TRIGGER (Dentro il ciclo for pair in ALL_PAIRS) ---
                if (is_buy or is_sell) and pair not in st.session_state.active_trades:
                    direction = "BUY" if is_buy else "SELL"
                    
                    # Salviamo i dati necessari per il calcolo futuro
                    st.session_state.active_trades[pair] = {
                        'entry_time': time_module.time(),
                        'entry_price': price,
                        'direction': direction
                    }
                    
                    # Primo inserimento nello storico (Esito in attesa)
                    st.session_state.signal_history.append({
                        'time': datetime.now().strftime("%H:%M:%S"),
                        'pair': pair, 
                        'dir': direction, 
                        'price': f"{price:.5f}",
                        'rsi': round(curr_rsi, 1),
                        'result': "⏳ In corso..."
                    })
                    
                    #st.error(f"SEGNALE {direction} su {pair}!", icon="🔥")
                    st.session_state.last_signal = f"🔥 SEGNALE {direction} su {pair}!"
                    send_telegram_signal(direction, pair, price, curr_rsi, 0)
                    play_trade_sound("buy")

            except: continue

    st.divider()
    st.subheader("📈 Grafico & RSI")
    
    # 3. GRAFICO (Il tuo Plotly originale)
    pair_display = st.selectbox("Seleziona valute", ALL_PAIRS)
    candles = Iq.get_candles(pair_display, 60, 80, time_module.time())
    df_plot = pd.DataFrame(candles)
    df_plot['RSI'] = ta.rsi(df_plot['close'], length=7)
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['open'], high=df_plot['max'], low=df_plot['min'], close=df_plot['close']), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['RSI'], line=dict(color='purple')), row=2, col=1)
    fig.add_hline(y=rsi_buy, line_color="green", row=2, col=1)
    fig.add_hline(y=rsi_sell, line_color="red", row=2, col=1)
    fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
    
    # --- LOGICA DI VERIFICA ESITI (Dopo lo scanner) ---
if st.session_state.connected:
    now = time_module.time()
    
    # Usiamo list() per evitare errori durante la rimozione di elementi dal dizionario
    for pair, trade in list(st.session_state.active_trades.items()):
        
        # 1. Verifica se è passata la scadenza (60 secondi)
        if now - trade['entry_time'] >= 60: 
            try:
                # Recupera il prezzo di chiusura
                res = Iq.get_candles(pair, 60, 1, now)
                exit_price = res[0]['close']
                
                # 2. Calcola se il trade è vincente o perdente
                if trade['direction'] == "BUY":
                    win = exit_price > trade['entry_price']
                else:
                    win = exit_price < trade['entry_price']
                
                # 3. Aggiorna il Saldo Locale (Virtuale)
                stake = st.session_state.get('stake', 100.0)
                if win:
                    st.session_state.local_balance += (stake * 0.85)
                    play_trade_sound("win")
                else:
                    st.session_state.local_balance -= stake
    
                # 4. Aggiorna lo stato nello storico (Tabella)
                for s in reversed(st.session_state.signal_history):
                    if s['pair'] == pair and s['result'] == "⏳ In corso...":
                        s['result'] = "✅ WIN" if win else "❌ LOSS"
                        break

                # 5. Rimuovi il trade dai monitorati per liberare la coppia
                del st.session_state.active_trades[pair]
                
            except Exception as e:
                # Se c'è un errore nell'API o nei dati, passa oltre
                continue

    # --- POSIZIONAMENTO NUOVO POPUP ---
    if 'last_signal' in st.session_state and st.session_state.last_signal:
        st.error(st.session_state.last_signal)
        # Puliamo il segnale dopo averlo mostrato per non farlo restare fisso
        st.session_state.last_signal = None 

    st.divider()

    # --- SEZIONE STATISTICHE E SALDO AGGIORNATO ---
    st.subheader("📋 Trading Journal")
    
    if st.session_state.signal_history:
        wins = sum(1 for s in st.session_state.signal_history if "✅" in str(s.get('result', '')))
        losses = sum(1 for s in st.session_state.signal_history if "❌" in str(s.get('result', '')))
        total = wins + losses
        rate = (wins / total * 100) if total > 0 else 0

        #st.metric("🏆 PERFORMANCE LIVE", f"Win Rate: {rate:.1f}%", f"W: {wins} | L: {losses}")

        # Creiamo 3 colonne per le metriche finali
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("🏆 Win Rate", f"{rate:.1f}%")
        with m2:
            st.metric("📊 Score", f"W: {wins} | L: {losses}")
        with m3:
            # Questo è il saldo che si aggiorna con i tuoi calcoli Win/Loss
            st.metric(f"💰 Saldo {st.session_state.account_type}", f"{st.session_state.local_balance:.2f} $")    
        
    # --- 4. TABELLA SEGNALI (ULTIMO IN ALTO) ---    
    if st.session_state.signal_history:
        # Creiamo il DataFrame
        df_journal = pd.DataFrame(st.session_state.signal_history)
        
        # Invertiamo l'ordine: l'ultimo aggiunto finisce in prima riga [::-1]
        df_reversed = df_journal.iloc[::-1].copy()
        
        # Assicuriamoci che tutte le colonne esistano (per evitare errori se il segnale è nuovo)
        for col in ['time', 'pair', 'dir', 'price', 'rsi', 'result']:
            if col not in df_reversed.columns:
                df_reversed[col] = "-" 
    
        # Rinominiamo per la visualizzazione
        rename_map = {
            'time': '⏰ ORA',
            'pair': '💱 COPPIA',
            'dir': '🚀 TIPO',
            'price': '💰 ENTRATA',
            'rsi': '📊 RSI',
            'result': '🔍 ESITO'
        }
        
        # Funzione per colorare l'esito
        def style_result(val):
            color = 'white'
            if '✅' in str(val): color = '#00ff00'
            elif '❌' in str(val): color = '#ff4b4b'
            elif '⏳' in str(val): color = '#ffa500'
            return f'color: {color}'
    
        # Visualizzazione della tabella invertita
        st.dataframe(
            df_reversed.rename(columns=rename_map).style.applymap(style_result, subset=['🔍 ESITO']),
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info("⏳ In attesa di segnali... Scanner attivo!")

    # --- LOGICA DI REFRESH AUTOMATICO ---
    
    # 1. Messaggio discreto di stato dello scanner
    st.caption(f"🔄 Scanner in esecuzione... Ultimo check: {datetime.now().strftime('%H:%M:%S')}")

    # 2. Pausa tecnica (fondamentale per non bloccare il browser)
    # Imposta 2 o 3 secondi: è il tempo perfetto per l'API di IQ Option
    time_module.sleep(3) 

    # 3. Il comando magico che resetta lo script dall'alto
    st.rerun() 


    # TABELLA SEGNALI SCARNA MA FUNZIONANTE
    #st.subheader("📋 Storico Segnali Recenti")
    #if st.session_state.signal_history:
        #st.table(pd.DataFrame(st.session_state.signal_history).tail(10))
