import streamlit as st
import pandas as pd
import pandas_ta as ta
import pytz
import time as time_module
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from iqoptionapi.stable_api import IQ_Option
from PIL import Image
import requests
import json
import os
from datetime import datetime, time, timedelta

# --- 1. CONFIGURAZIONI E TELEGRAM ---
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "IL_TUO_TOKEN_QUI")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "IL_TUO_CHAT_ID_QUI")

def genera_trade_id():
    return f"TRD-{int(datetime.now().timestamp()) % 1000000}"

def invia_telegram(messaggio):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": messaggio, "parse_mode": "Markdown"}, timeout=5)
    except Exception as e:
        print(f"Errore Telegram: {e}")

def send_telegram_signal(signal_type, pair, price, rsi, trade_id):
    timestamp = datetime.now().strftime("%H:%M:%S")
    message = (
        f"🚀 *NUOVA OPERAZIONE*\n"
        f"🔔 *Segnale:* {signal_type}\n"
        f"🆔 ID: `{trade_id}`\n"
        f"📊 Asset: {pair}\n"
        f"💰 Prezzo: `{price:.5f}`\n"
        f"📊 RSI: `{rsi:.1f}`\n"
        f"⏰ Ora: {timestamp}"
    )
    invia_telegram(message)

def registra_trade(trade_id, pair, direction, risultato, profitto):
    file_path = "daily_report.json"
    data = []
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            data = json.load(f)
    data.append({
        "id": trade_id, "pair": pair, "direction": direction,
        "risultato": risultato, "profitto": profitto,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })
    with open(file_path, "w") as f:
        json.dump(data, f)

def genera_report_finale():
    file_path = "daily_report.json"
    if not os.path.exists(file_path): return
    with open(file_path, "r") as f:
        trades = json.load(f)
    total = len(trades)
    wins = len([t for t in trades if t['risultato'] == "WIN"])
    loss = total - wins
    profitto_totale = sum([t['profitto'] for t in trades])
    accuracy = (wins / total * 100) if total > 0 else 0
    report = (
        f"📊 *REPORT GIORNALIERO SENTINEL AI*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📈 Totale Trade: {total}\n"
        f"✅ Win: {wins} | ❌ Loss: {loss}\n"
        f"🎯 Accuracy: {accuracy:.1f}%\n"
        f"💰 Profitto Netto: *{profitto_totale:.2f}€*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏁 Sessione terminata. Sistema in standby."
    )
    invia_telegram(report)
    os.remove(file_path)

def play_trade_sound(sound_type="buy"):
    sounds = {
        "buy": "https://actions.google.com/sounds/v1/alarms/beep_short.ogg",
        "win": "https://actions.google.com/sounds/v1/cartoon/clink_vibrant.ogg"
    }
    placeholder = st.empty()
    try:
        with placeholder:
            st.audio(sounds.get(sound_type, sounds["buy"]), autoplay=True)
        time_module.sleep(2.0)
    except:
        pass
    placeholder.empty()

def get_market_status():
    fuso_roma = pytz.timezone('Europe/Rome')
    now_roma = datetime.now(fuso_roma)
    now_time = now_roma.time()

    londra = (time(9,0), time(18,0))
    new_york = (time(14,0), time(23,0))
    
    is_londra = londra[0] <= now_time <= londra[1]
    is_ny = new_york[0] <= now_time <= new_york[1]
    
    if is_londra and is_ny:
        return "🔥 SOVRAPPOSIZIONE (EU/USA)\n\nAlta Volatilità"
    elif is_londra:
        return "🇪🇺 SESSIONE LONDRA"
    elif is_ny:
        return "🇺🇸 SESSIONE NEW YORK"
    else:
        return "💤 MERCATO LENTO"

def draw_market_map_inverted(current_hour_float, trading_autorizzato):
    fig = go.Figure()
    
    try:
        from PIL import Image
        bg_image = Image.open("map_bg.png")
    except:
        bg_image = "https://via.placeholder.com/1200x400/220044/white?text=MAPPA+SESSIONI"

    fig.add_layout_image(dict(
        source=bg_image, 
        xref="x", yref="y", 
        x=24, y=4.5,
        sizex=24, sizey=4.5, 
        sizing="stretch", 
        opacity=1.0, 
        layer="below"
    ))

    # --- LOGICA RITARDO (OFFSET) ---
    # Sottraiamo 30 minuti
    ritardo_ore = 30 / 60
    x_pos = current_hour_float - ritardo_ore

    # Gestione del reset: se l'ora è 00:20, sottraendo 40 min andrebbe in negativo.
    # Con l'operatore % 24, la linea ricompare correttamente dal fondo (24).
    x_pos = x_pos % 24

    color_laser = "#FFFFFF" if not trading_autorizzato else "#FFD700"

    fig.add_shape(
        type="line", 
        x0=x_pos, x1=x_pos, y0=0, y1=4.5, 
        line=dict(color=color_laser, width=5)
    )

    fig.update_layout(
        xaxis=dict(range=[24, 0], showgrid=False, visible=False, fixedrange=True),
        yaxis=dict(range=[0, 4.5], showgrid=False, visible=False, fixedrange=True),
        template="plotly_dark", 
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", 
        margin=dict(l=0, r=0, t=0, b=0), 
        height=350
    )
    return fig


# --- 2. SETUP STREAMLIT E SESSIONE ---
st.set_page_config(page_title="Sentinel AI", page_icon="🚀", layout="wide")

try:
    logo = Image.open("banner.png")
    st.image(logo, use_column_width=True, caption="IQ Signals PRO")
except:
    st.image("https://via.placeholder.com/800x100/0066cc/white?text=SENTINEL+AI", use_column_width=True)

if 'connected' not in st.session_state: st.session_state.connected = False
if 'active_trades' not in st.session_state: st.session_state.active_trades = {}
if 'signal_history' not in st.session_state: st.session_state.signal_history = []
if 'local_balance' not in st.session_state: st.session_state.local_balance = 0
if 'scanner_on' not in st.session_state: st.session_state.scanner_on = False

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ IQ FOREX TRADING")
    if not st.session_state.connected:
        email = st.text_input("Email", value="mago_magoz@libero.it")
        password = st.text_input("Password", type="password")
        tipo_conto = st.radio("Conto", ["DEMO", "REALE"])
        
        if st.button("🔌 CONNETTI"):
            from iqoptionapi.stable_api import IQ_Option
            Iq_obj = IQ_Option(email, password)
            check, reason = Iq_obj.connect()
            
            if check:
                mode = "PRACTICE" if tipo_conto == "DEMO" else "REAL"
                Iq_obj.change_balance(mode)
                st.session_state.iq = Iq_obj 
                st.session_state.connected = True
                st.session_state.account_type = tipo_conto
                st.session_state.local_balance = Iq_obj.get_balance()
                st.rerun()
    else:
        st.success(f"🟢 Conto {st.session_state.account_type} ATTIVO")
        st.metric(f"💰 Saldo {st.session_state.account_type}", f"{st.session_state.local_balance:.2f} €")    
        st.session_state.stake = st.number_input("💰 INVESTIMENTO (€)", value=100.0)
        timeframe = st.selectbox("⏱️ TIMEFRAME OPERATIVO (s)", [60, 300], index=0)
    
        if st.button("🔴 DISCONNETTI"):
            st.session_state.connected = False
            st.rerun()

        st.divider()
        now_roma = datetime.now(pytz.timezone('Europe/Rome'))
        now_cet = now_roma.time()
        
        st.header("🌍 SESSIONI DI MERCATO")
        for city, (start, end) in {"🇬🇧 LONDRA:": (time(9,0), time(17,0)), "🇺🇸 NEW YORK:": (time(15,0), time(22,0)), "🇦🇺 SYDNEY:": (time(0,0), time(6,0)), "🇯🇵 TOKYO:": (time(1,0), time(7,0))}.items():
            status = "Open 🟢" if start <= now_cet <= end else "Closed 🔴"
            st.write(f"{city} {status}")

        st.info(get_market_status())

        st.divider()
        st.header("🔧 STRUMENTI TEST")
        stress_test = st.toggle("🚀 STRESS TEST MODE", value=False)
        if stress_test:
            st.warning("⚠️ TEST:  \nno BB - RSI (45/55) - no MACD")
        else:
            st.success("🟢 REALE:  \nBB(20,2) - RSI(28/72) - MACD(8,17,9)")

        if st.button("🔔 TEST CANALI", use_container_width=True):
            play_trade_sound("buy")
            invia_telegram("✅ **SENTINEL AI: SYSTEM CHECK**\nBot online e sincronizzato. 🚀")
            st.toast("Test completato!", icon="📲")

        st.divider()
        if st.button("🗑️ PULISCI STORICO", use_container_width=True):
            st.session_state.signal_history = []
            st.session_state.local_balance = st.session_state.iq.get_balance() if st.session_state.connected else 0
            st.rerun()

# --- 4. MAIN DASHBOARD ---
if st.session_state.connected:
    Iq = st.session_state.iq
    ALL_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"]
    icons = {"EURUSD": "🇪🇺🇺🇸", "GBPUSD": "🇬🇧🇺🇸", "USDJPY": "🇺🇸🇯🇵", "AUDUSD": "🇦🇺🇺🇸", "USDCAD": "🇺🇸🇨🇦", "USDCHF": "🇺🇸🇨🇭", "NZDUSD": "🇳🇿🇺🇸", "EURGBP": "🇪🇺🇬🇧", "EURJPY": "🇪🇺🇯🇵", "GBPJPY": "🇬🇧🇯🇵"}

    st.header("👁️ Scanner FOREX")
    
    label = "🛑 STOP SCANNER" if st.session_state.scanner_on else "🚀 AVVIA SCANNER"
    if st.button(label, use_container_width=True, type="primary" if not st.session_state.scanner_on else "secondary"):
        st.session_state.scanner_on = not st.session_state.scanner_on
        st.rerun()

    # Logica Oraria
    fuso_roma = pytz.timezone('Europe/Rome')
    now_roma = datetime.now(fuso_roma)
    now_time = now_roma.time()
    h_float = now_roma.hour + (now_roma.minute / 60)

    # Finestre Operative e Report
    window_1 = (time(9, 0), time(12, 0))
    window_2 = (time(14, 0), time(18, 30))
    is_trading_time = (window_1[0] <= now_time <= window_1[1]) or (window_2[0] <= now_time <= window_2[1])
    trading_autorizzato = is_trading_time or stress_test

    if now_time >= time(18, 30) and not st.session_state.get('report_sent', False):
        genera_report_finale()
        st.session_state.report_sent = True
    if now_time < time(9, 0):
        st.session_state.report_sent = False

    # Mappa Dinamica
    st.subheader("🌍 Live Market Flow 24h")
    
    st.plotly_chart(
    draw_market_map_inverted(h_float, trading_autorizzato), 
    use_container_width=True, 
    config={'displayModeBar': False} # È QUI che va inserito per non dare errore
    )

    #https://trueforexfunds.com/wp-content/uploads/2023/05/THUMBNAIL_20_1-e1685710115417-1024x538.png
    
    # Stato Sistema
    if st.session_state.scanner_on:
        if not trading_autorizzato:
            st.warning("🛡️ PROTEZIONE ATTIVA: Mercato fuori orario. Scanner in pausa.")
            st.info(f"⏰ Prossima finestra: {window_1[0] if now_time < window_1[0] else window_2[0]}")
        else:
            st.success("SISTEMA IN SCANSIONE ATTIVA 🔥🔥🔥", icon="📡")
            
            cols = st.columns(5)
            for i, pair in enumerate(ALL_PAIRS):
                with cols[i % 5]: st.code(f"{icons.get(pair, '🔍')} {pair}")

            # Esecuzione Scanner
            current_tf = 60 if stress_test else timeframe
            rsi_buy, rsi_sell = (55, 45) if stress_test else (28, 72)
            
            for pair in ALL_PAIRS:
                try:
                    candles = Iq.get_candles(pair, current_tf, 100, time_module.time())
                    df = pd.DataFrame(candles)
                    df['RSI'] = ta.rsi(df['close'], length=7)
                    price, curr_rsi = df['close'].iloc[-1], df['RSI'].iloc[-1]

                    if stress_test:
                        is_buy, is_sell = curr_rsi < rsi_buy, curr_rsi > rsi_sell
                        curr_macd, curr_bb_status = 0.0, "TEST"
                    else:
                        bb = ta.bbands(df['close'], length=20, std=2.0)
                        macd = ta.macd(df['close'], fast=8, slow=17, signal=9)
                        curr_bb_low, curr_bb_up = bb.iloc[-1, 0], bb.iloc[-1, 2] # BBL, BBU
                        curr_macd, curr_sig = macd.iloc[-1, 0], macd.iloc[-1, 2] # MACD, SIGNAL
                        
                        is_buy = (curr_rsi < rsi_buy) and (price <= curr_bb_low) and (curr_macd > curr_sig)
                        is_sell = (curr_rsi > rsi_sell) and (price >= curr_bb_up) and (curr_macd < curr_sig)
                        curr_bb_status = "OUT" if (price <= curr_bb_low or price >= curr_bb_up) else "IN"

                    if (is_buy or is_sell) and pair not in st.session_state.active_trades:
                        direction = "BUY" if is_buy else "SELL"
                        t_id = genera_trade_id()
                        
                        st.session_state.active_trades[pair] = {
                            'id': t_id, 'entry_price': price,
                            'entry_time': time_module.time(), 'direction': direction
                        }
                        
                        st.session_state.signal_history.append({
                            'time': datetime.now().strftime("%H:%M:%S"),
                            'pair': pair, 'dir': direction, 'price': f"{price:.5f}",
                            'rsi': round(curr_rsi, 1), 'macd': round(curr_macd, 6),
                            'bb': curr_bb_status, 'result': "⏳ In corso..."
                        })
                        
                        send_telegram_signal(direction, pair, price, curr_rsi, t_id)
                        play_trade_sound("buy")
                        st.session_state.last_signal = f"🔥 SEGNALE {direction} su {pair}!"
                except Exception as e:
                    continue
    else:
        st.info("SISTEMA IN STANDBY", icon="💤")

    # --- 5. ANALISI TECNICA GRAFICA ---
    st.divider()
    st.header("📈 Analisi Tecnica")
    pair_display = st.selectbox("Seleziona asset per grafico", ALL_PAIRS)
    
    try:
        candles_ta = Iq.get_candles(pair_display, timeframe, 160, time_module.time())
        df_raw = pd.DataFrame(candles_ta)
        df_raw['RSI'] = ta.rsi(df_raw['close'], length=7)
        bb_ta = ta.bbands(df_raw['close'], length=20, std=2)
        bb_ta.columns = ['BBL', 'BBM', 'BBU', 'BBB', 'BBP'] 
        macd_ta = ta.macd(df_raw['close'], fast=8, slow=17, signal=9)
        macd_ta.columns = ['MACD', 'HIST', 'SIGNAL']
        df_final = pd.concat([df_raw, bb_ta[['BBL', 'BBM', 'BBU']], macd_ta], axis=1).tail(100)

        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.5, 0.25, 0.25], vertical_spacing=0.07, subplot_titles=("📊 Prezzo & BB", "📉 RSI", "🚀 MACD"))
        
        # Prezzo e BB
        fig.add_trace(go.Candlestick(x=df_final.index, open=df_final['open'], high=df_final['max'], low=df_final['min'], close=df_final['close'], name="Prezzo"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_final.index, y=df_final['BBU'], line=dict(color='rgba(0,71,171,0.4)', dash='dot'), name="BBU"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_final.index, y=df_final['BBL'], line=dict(color='rgba(0,71,171,0.4)', dash='dot'), fill='tonexty', fillcolor='rgba(100, 100, 255, 0.05)', name="BBL"), row=1, col=1)
        
        # RSI
        fig.add_trace(go.Scatter(x=df_final.index, y=df_final['RSI'], line=dict(color='#AB63FA'), name="RSI"), row=2, col=1)
        fig.add_hline(y=(45 if stress_test else 28), line_color="green", row=2, col=1, line_dash="dash")
        fig.add_hline(y=(55 if stress_test else 72), line_color="red", row=2, col=1, line_dash="dash")

        # MACD
        macd_colors = []
        hist_diff = df_final['HIST'].diff()
        for i in range(len(df_final)):
            val, diff = df_final['HIST'].iloc[i], hist_diff.iloc[i]
            if pd.isna(diff): macd_colors.append('rgba(0,0,0,0.2)')
            elif val > 0 and diff > 0: macd_colors.append('#26A69A')
            elif val > 0 and diff <= 0: macd_colors.append('#B2DFDB')
            elif val < 0 and diff < 0: macd_colors.append('#EF5350')
            else: macd_colors.append('#FFCDD2')

        fig.add_trace(go.Bar(x=df_final.index, y=df_final['HIST'], marker_color=macd_colors, name="HIST"), row=3, col=1)
        fig.add_trace(go.Scatter(x=df_final.index, y=df_final['MACD'], line=dict(color='#00E5FF', width=2), name="MACD"), row=3, col=1)
        fig.add_trace(go.Scatter(x=df_final.index, y=df_final['SIGNAL'], line=dict(color='#FF9100', width=2), name="Signal"), row=3, col=1)

        fig.update_layout(hovermode="x unified", height=850, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10,r=10,b=10,t=40))
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Errore grafico TA: {e}")

    # --- 6. VERIFICA ESITI TRADE ---
    now = time_module.time()
    for pair, trade in list(st.session_state.active_trades.items()):
        if now - trade['entry_time'] >= 60: 
            try:
                res = Iq.get_candles(pair, 60, 1, now)
                exit_price = res[0]['close']
                win = (exit_price > trade['entry_price']) if trade['direction'] == "BUY" else (exit_price < trade['entry_price'])
                
                res_status = "WIN" if win else "LOSS"
                stake = st.session_state.get('stake', 100.0)
                profit = (stake * 0.85) if win else -stake
                t_id = trade.get('id', 'N/D')

                st.session_state.local_balance += profit
                if win: play_trade_sound("win")

                colore_esito = "✅" if win else "❌"
                invia_telegram(f"{colore_esito} *ESITO TRADE*\n🆔 ID: `{t_id}`\n📈 Risultato: *{res_status}*\n💰 Profitto: {profit:.2f}€\n🏁 Stato: Conclusa")
                registra_trade(t_id, pair, trade['direction'], res_status, profit)
                
                for s in reversed(st.session_state.signal_history):
                    if s['pair'] == pair and s['result'] == "⏳ In corso...":
                        s['result'] = f"{colore_esito} {res_status}"
                        break
                
                del st.session_state.active_trades[pair]
            except Exception as e:
                continue

    if st.session_state.get('last_signal'):
        st.error(st.session_state.last_signal)
        st.session_state.last_signal = None 

    # --- 7. TABELLA JOURNAL ---
    st.divider()
    st.subheader("📋 Trading Journal")
    if st.session_state.signal_history:
        wins = sum(1 for s in st.session_state.signal_history if "✅" in str(s.get('result', '')))
        losses = sum(1 for s in st.session_state.signal_history if "❌" in str(s.get('result', '')))
        total = wins + losses
        rate = (wins / total * 100) if total > 0 else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("🏆 Win Rate", f"{rate:.1f}%")
        m2.metric("📊 Score", f"W: {wins} | L: {losses}")
        m3.metric(f"💰 Saldo {st.session_state.account_type}", f"{st.session_state.local_balance:.2f} €")    
        
        df_journal = pd.DataFrame(st.session_state.signal_history).iloc[::-1]
        rename_map = {'time': '⏰ ORA', 'pair': '💱 COPPIA', 'dir': '🚀 TIPO', 'price': '💰 ENTRATA', 'rsi': '📊 RSI', 'macd': '📉 MACD', 'bb': '↔️ BOLLINGER', 'result': '🔍 ESITO'}
        
        def style_result(val):
            color = '#00ff00' if '✅' in str(val) else '#ff4b4b' if '❌' in str(val) else '#ffa500' if '⏳' in str(val) else 'white'
            return f'color: {color}'
    
        st.dataframe(df_journal.rename(columns=rename_map).style.applymap(style_result, subset=['🔍 ESITO']), use_container_width=True, hide_index=True)
    else:
        st.info("⏳ In attesa di segnali...")

    # --- 8. REFRESH LOOP ---
    if st.session_state.scanner_on:
        st.caption(f"🔄 Scanner in esecuzione... Ultimo check: {now_roma.strftime('%H:%M:%S')}")
        time_module.sleep(3) 
        st.rerun()
