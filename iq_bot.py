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

def get_market_status():
    now = datetime.now().time()
    # Definiamo gli orari
    londra = (time(9,0), time(18,0))
    new_york = (time(14,0), time(23,0))
    
    is_londra = londra[0] <= now <= londra[1]
    is_ny = new_york[0] <= now <= new_york[1]
    
    if is_londra and is_ny:
        return "🔥 SOVRAPPOSIZIONE (EU/USA)\n\nAlta Volatilità"
    elif is_londra:
        return "🇪🇺 SESSIONE LONDRA"
    elif is_ny:
        return "🇺🇸 SESSIONE NEW YORK"
    else:
        return "💤 MERCATO LENTO"

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
if 'initial_balance' not in st.session_state: st.session_state.initial_balance = 0.0
if 'daily_stop_hit' not in st.session_state: st.session_state.daily_stop_hit = False


with st.sidebar:
    st.header("⚙️ IQ FOREX TRADING PLATFORM")
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
        st.success(f"🟢 Conto {st.session_state.account_type} ATTIVO")
        #st.session_state.stake = st.number_input("💰 INVESTIMENTO (€)", value=100.0)
        
        st.divider()
        st.header("🛡️ RISK MANAGEMENT")
        risk_percent = st.slider("⚖️ Rischio per Operazione (%)", 0.5, 5.0, 1.0, help="Percentuale del capitale da investire per singolo trade")
        
        max_loss = st.number_input("📉 Stop Loss Giornaliero (€)", value=500.0, step=50.0)
        
        # Calcolo dinamico dello Stake basato sul saldo attuale
        st.session_state.stake = (st.session_state.local_balance * risk_percent) / 100
        st.caption(f"💰 INVESTIMENTO CALCOLATO: {st.session_state.stake:.2f} €")

        timeframe = st.selectbox("⏱️ SELEZIONA TIMEFRAME OPERATIVO (s)", [60, 300], index=0)
    
        if st.button("🔴 DISCONNETTI"):
            st.session_state.connected = False
            st.rerun()

        st.divider()
        
        # --- SESSIONI DI MERCATO ---
        now_cet = datetime.now().time()
        st.header("🌍 SESSIONI DI MERCATO")
        
        for city, (start, end) in {"🇬🇧 LONDRA:": (time(9,0), time(18,0)), "🇺🇸 NEW YORK:": (time(14,0), time(23,0)), "🇦🇺 SYDNEY:": (time(23,0), time(8,0)), "🇯🇵 TOKYO:": (time(1,0), time(10,0))}.items():
            status = "Open 🟢" if start <= now_cet <= end else "Closed 🔴"
            st.write(f"{city} {status}")

        # Visualizzazione
        st.info(get_market_status())

        st.divider()
        st.header("🛠️ STRUMENTI DI TEST")
        stress_test = st.toggle("🚀 STRESS TEST MODE", value=False, help="Attiva segnali frequenti per testare notifiche e suoni")
        
        if stress_test:
            st.warning("⚠️ Modalità TEST:\n\nno BB - RSI (45/55) - no MACD")
        else:
            st.success("🟢 Modalità REALE:\n\nBB (20,2.0) - RSI (28/72) - MACD (8,17,9)")

        st.divider()
        if st.button("🗑️ PULISCI STORICO", use_container_width=True):
            st.session_state.signal_history = []
            
            # CORREZIONE: Usiamo st.session_state.iq invece di Iq
            if st.session_state.connected and 'iq' in st.session_state:
                st.session_state.local_balance = st.session_state.iq.get_balance()
            else:
                st.session_state.local_balance = 0
                
            st.success("✅ Storico resettato e saldo aggiornato!")
            st.rerun()

# --- MAIN DASHBOARD ---
if st.session_state.connected:
    Iq = st.session_state.iq
    
    #st.divider()

    st.header("👁️ Scanner FOREX")
    
    ALL_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"]
    
    # Lista icone per la griglia
    icons = {
        "EURUSD": "🇪🇺🇺🇸", "GBPUSD": "🇬🇧🇺🇸", "USDJPY": "🇺🇸🇯🇵", 
        "AUDUSD": "🇦🇺🇺🇸", "USDCAD": "🇺🇸🇨🇦", "USDCHF": "🇺🇸🇨🇭", 
        "NZDUSD": "🇳🇿🇺🇸", "EURGBP": "🇪🇺🇬🇧", "EURJPY": "🇪🇺🇯🇵", "GBPJPY": "🇬🇧🇯🇵"
    }

    # --- SEZIONE COMANDI SCANNER (PULSANTI VERTICALI) ---
    
    # Spazio estetico
    #st.write("")

    # 2. Pulsante START/STOP (Sotto al timeframe, a tutta larghezza)
    if 'scanner_on' not in st.session_state:
        st.session_state.scanner_on = False

    label = "🛑 STOP SCANNER" if st.session_state.scanner_on else "🚀 AVVIA SCANNER"
    
    # 'type' cambia il look: primario (colorato) o secondario (bianco/nero)
    if st.button(label, use_container_width=True, type="primary" if not st.session_state.scanner_on else "secondary", help="Attiva o disattiva la scansione degli asset"):
        st.session_state.scanner_on = not st.session_state.scanner_on
        st.rerun()

    scanner_attivo = st.session_state.scanner_on

    # 1. Calcolo del bilancio iniziale alla prima connessione reale
    if st.session_state.initial_balance == 0.0 and st.session_state.local_balance > 0:
        st.session_state.initial_balance = st.session_state.local_balance

    # 2. Controllo Drawdown (Perdita attuale)
    perdita_attuale = st.session_state.initial_balance - st.session_state.local_balance
    if perdita_attuale >= max_loss:
        st.session_state.daily_stop_hit = True

    # 3. Filtro Orario
    now_time = datetime.now().time()
    window_1 = (time(9, 0), time(12, 0))
    window_2 = (time(14, 0), time(18, 30))
    is_trading_time = (window_1[0] <= now_time <= window_1[1]) or (window_2[0] <= now_time <= window_2[1])

    # 4. Semaforo Operativo (Logica di Autorizzazione)
    scanner_autorizzato = False

    if st.session_state.daily_stop_hit:
        st.error(f"🚫 SESSIONE BLOCCATA: Stop Loss Giornaliero raggiunto (-{perdita_attuale:.2f}€)")
        st.info("Riposa. Il mercato sarà qui anche domani.")
    elif scanner_attivo and not is_trading_time and not stress_test:
        st.warning("🛡️ PROTEZIONE ORARIA: Mercato in bassa volatilità.")
        st.success(f"⏰ Prossima finestra: {window_1[0] if now_time > window_1[0] else window_2[0]}")
    
    # 5. Esecuzione Scanner
    if scanner_autorizzato:
    # Qui inizia il tuo ALL_PAIRS e il ciclo FOR per ogni coppia...

        # 3. Indicatore di stato gigante
        if scanner_attivo:
            st.success("📡 SISTEMA IN SCANSIONE ATTIVA", icon="🔥")
            
            # --- NUOVA SEZIONE: MONITOR DELLE VALUTE ---
            st.subheader("🕵️ Asset in Monitoraggio")
            
            # Creiamo una griglia di 5 colonne per mostrare le valute in modo compatto
            cols = st.columns(5)
            for i, pair in enumerate(ALL_PAIRS):
                with cols[i % 5]:
                    st.code(f"{icons.get(pair, '🔍')} {pair}") # Mostra la valuta in un box grigio tecnico

    else:
        st.info("💤 SISTEMA IN STANDBY", icon="⚪")

        st.divider()
    
    if scanner_attivo:
    #if st.session_state.scanner:    
    
        # --- 2. DEFINIZIONE PARAMETRI AUTOMATICA ---
        if stress_test:
            current_tf = 60 # Forza 1 minuto in modalità test
            # Soglie RSI larghe per generare raffiche di segnali (Consiglio 3)
            rsi_buy_trigger = 55
            rsi_sell_trigger = 45
        else:
            current_tf = timeframe
            rsi_buy_trigger = 28 # Valori reali protetti
            rsi_sell_trigger = 72
            bb_period, bb_std = 20, 2.0
            m_fast, m_slow, m_sig = 8, 17, 9
    
        # --- 3. CICLO SCANNER ---
        for pair in ALL_PAIRS:
            try:
                # Recupero candele (Minimo 100 per RSI)
                candles = Iq.get_candles(pair, current_tf, 100, time_module.time())
                df = pd.DataFrame(candles)
                df['RSI'] = ta.rsi(df['close'], length=7)
                
                price = df['close'].iloc[-1]
                curr_rsi = df['RSI'].iloc[-1]
    
                # --- LOGICA DI SEGNALE BLINDATA ---
                if stress_test:
                    # VERIFICA TEST: Solo RSI, ignora tutto il resto
                    is_buy = curr_rsi < rsi_buy_trigger
                    is_sell = curr_rsi > rsi_sell_trigger
                    
                    # Variabili segnaposto per non far crashare la tabella
                    curr_macd = 0.0
                    curr_bb_status = "TEST"
                else:
                    # MODALITÀ REALE: Calcolo completo indicatori pesanti
                    bb = ta.bbands(df['close'], length=bb_period, std=bb_std)
                    bb.columns = ['BBL', 'BBM', 'BBU', 'BBB', 'BBP']
                    macd = ta.macd(df['close'], fast=m_fast, slow=m_slow, signal=m_sig)
                    macd.columns = ['MACD', 'HIST', 'SIGNAL']
                    
                    curr_bb_low = bb['BBL'].iloc[-1]
                    curr_bb_up = bb['BBU'].iloc[-1]
                    curr_macd = macd['MACD'].iloc[-1]
                    curr_sig = macd['SIGNAL'].iloc[-1]
                    
                    # Triple Confirmation
                    is_buy = (curr_rsi < rsi_buy_trigger) and (price <= curr_bb_low) and (curr_macd > curr_sig)
                    is_sell = (curr_rsi > rsi_sell_trigger) and (price >= curr_bb_up) and (curr_macd < curr_sig)
                    curr_bb_status = "OUT" if (price <= curr_bb_low or price >= curr_bb_up) else "IN"
    
                # --- ESECUZIONE SEGNALE (Se confermato) ---
                if (is_buy or is_sell) and pair not in st.session_state.active_trades:
                    direction = "BUY" if is_buy else "SELL"
                    
                    # Registrazione trade e notifiche
                    st.session_state.active_trades[pair] = {
                        'entry_price': price,
                        'entry_time': time_module.time(),
                        'direction': direction
                    }
    
                    st.session_state.signal_history.append({
                        'time': datetime.now().strftime("%H:%M:%S"),
                        'pair': pair, 
                        'dir': direction, 
                        'price': f"{price:.5f}",
                        'rsi': round(curr_rsi, 1),
                        'macd': round(curr_macd, 6),
                        'bb': curr_bb_status,
                        'result': "⏳ In corso..."
                    })
                    
                    st.session_state.last_signal = f"🔥 SEGNALE {direction} su {pair}!"
                    play_trade_sound("buy")
                    send_telegram_signal(direction, pair, price, curr_rsi, curr_macd)
            
            except Exception as e:
                continue

    st.divider()
    st.header("📈 Analisi Tecnica")
    
    pair_display = st.selectbox("Seleziona asset", ALL_PAIRS)
    
    if st.session_state.connected:
        Iq = st.session_state.iq
        
        try:
            # 1. Recupero Dati - Aumentiamo a 160 per far partire gli indicatori da sinistra
            candles = Iq.get_candles(pair_display, timeframe, 160, time_module.time())
            df_raw = pd.DataFrame(candles)
            
            # 2. Calcolo Indicatori
            df_raw['RSI'] = ta.rsi(df_raw['close'], length=7)
            
            # Bollinger con nomi colonne forzati
            bb = ta.bbands(df_raw['close'], length=20, std=2)
            bb.columns = ['BBL', 'BBM', 'BBU', 'BBB', 'BBP'] 
            
            # MACD con nomi colonne forzati
            macd = ta.macd(df_raw['close'], fast=8, slow=17, signal=9)
            macd.columns = ['MACD', 'HIST', 'SIGNAL']
            
            # Unione e taglio per visualizzare solo le ultime 100 candele (senza buchi a sx)
            df_final = pd.concat([df_raw, bb[['BBL', 'BBM', 'BBU']], macd], axis=1).tail(100)
    
            # 3. Creazione Subplots - CORRETTO: subplot_titles
            fig = make_subplots(
                rows=3, cols=1, 
                shared_xaxes=True, 
                row_heights=[0.5, 0.25, 0.25], 
                vertical_spacing=0.07,
                subplot_titles=("📊 Analisi Prezzo & Volatilità", "📉 Oscillatore RSI", "🚀 Momentum MACD")
            )
    
            # --- PANNELLO 1: Candele + Bollinger ---
            fig.add_trace(go.Candlestick(x=df_final.index, open=df_final['open'], high=df_final['max'], 
                                         low=df_final['min'], close=df_final['close'], name="Prezzo"), row=1, col=1)
            
            fig.add_trace(go.Scatter(x=df_final.index, y=df_final['BBU'], line=dict(color='rgba(0,71,171,0.4)', dash='dot'), name="BBU"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_final.index, y=df_final['BBM'], line=dict(color='rgba(170,170,170,0.3)', width=1), name="BBM"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_final.index, y=df_final['BBL'], line=dict(color='rgba(0,71,171,0.4)', dash='dot'), 
                                     fill='tonexty', fillcolor='rgba(100, 100, 255, 0.05)', name="BBL"), row=1, col=1)
    
            # --- PANNELLO 2: RSI ---
            # Definiamo le soglie visive in base alla modalità attiva
            grafico_rsi_buy = 45 if stress_test else 28
            grafico_rsi_sell = 55 if stress_test else 72

            fig.add_trace(go.Scatter(x=df_final.index, y=df_final['RSI'], line=dict(color='#AB63FA'), name="RSI"), row=2, col=1)
            
            # Linee tratteggiate dinamiche
            fig.add_hline(y=grafico_rsi_buy, line_color="green", row=2, col=1, line_dash="dash")
            fig.add_hline(y=grafico_rsi_sell, line_color="red", row=2, col=1, line_dash="dash")
    
            # --- CALCOLO COLORI MACD DINAMICI (Stile TradingView) ---
            macd_colors = []
            hist_diff = df_final['HIST'].diff() # Calcola la differenza con la barra precedente
            
            for i in range(len(df_final)):
                val = df_final['HIST'].iloc[i]
                diff = hist_diff.iloc[i]
                
                if pd.isna(diff): # Per la primissima candela
                    macd_colors.append('rgba(0,0,0,0.2)')
                elif val > 0 and diff > 0:
                    macd_colors.append('#26A69A') # Verde Forte (Momentum rialzista in crescita)
                elif val > 0 and diff <= 0:
                    macd_colors.append('#B2DFDB') # Verde Chiaro (Momentum rialzista in esaurimento)
                elif val < 0 and diff < 0:
                    macd_colors.append('#EF5350') # Rosso Forte (Momentum ribassista in crescita)
                elif val < 0 and diff >= 0:
                    macd_colors.append('#FFCDD2') # Rosso Chiaro (Momentum ribassista in esaurimento)

            # --- PANNELLO 3: MACD ---
            # Sostituiamo il colore fisso con la nostra lista macd_colors
            fig.add_trace(go.Bar(x=df_final.index, y=df_final['HIST'], name="Momentum", marker_color=macd_colors), row=3, col=1)
            
            # (Opzionale) Ho reso le linee del MACD e del Signal un po' più spesse e visibili
            fig.add_trace(go.Scatter(x=df_final.index, y=df_final['MACD'], line=dict(color='#00E5FF', width=2), name="MACD"), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_final.index, y=df_final['SIGNAL'], line=dict(color='#FF9100', width=2), name="Signal"), row=3, col=1)
            
            for i in fig['layout']['annotations']:
                i['font'] = dict(size=14, color='#000000')

            # --- AGGIUNGI QUESTO PER LE RIGHE VERTICALI E IL MIRINO ---
            fig.update_xaxes(
                showgrid=True, 
                gridcolor='rgba(130,130,130,0.08)', # Righe verticali fisse leggere
                showspikes=True, 
                spikecolor="black", 
                spikethickness=1, 
                spikedash="dot",
                spikemode="across" # Linea interattiva che taglia tutti i 3 grafici
            )
            
            fig.update_layout(
                hovermode="x unified", # Ti mostra il valore esatto di Prezzo, RSI e MACD in un unico box!
                height=850, 
                template="plotly_dark", 
                xaxis_rangeslider_visible=False, 
                margin=dict(l=10,r=10,b=10,t=40)
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
        except Exception as e:
            st.error(f"⚠️ Errore durante il rendering del grafico: {e}")
    
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

    if not scanner_attivo:
        st.error("📡 ATTIVA LO SCANNER FOREX", icon="🔥")
            
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
                st.metric(f"💰 Saldo {st.session_state.account_type}", f"{st.session_state.local_balance:.2f} €")    
            
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
            
                # Rinominiamo le nuove colonne
                rename_map = {
                    'time': '⏰ ORA',
                    'pair': '💱 COPPIA',
                    'dir': '🚀 TIPO',
                    'price': '💰 ENTRATA',
                    'rsi': '📊 RSI',
                    'macd': '📉 MACD',
                    'bb': '↔️ BOLLINGER',
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

