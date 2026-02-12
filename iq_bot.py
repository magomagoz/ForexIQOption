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

# **CONFIG TELEGRAM** (metti nella sidebar)
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

def send_telegram_signal(signal_type, pair, price, rsi, macd):
    """Invia notifica Telegram completa"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    message = f"""
🚀 *SENTINEL AI* 🚀

*{signal_type} - {pair.upper()}*
💰 *Prezzo Entrata:* `{price:.5f}`
📊 *RSI:* `{rsi:.1f}`
🔥 *MACD:* `{macd:.5f}`
⏰ *Ora:* {timestamp}
{'🟢 Esito 1m!' if signal_type == 'BUY' else '🔴 ESITO 1m!'}
"""
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, data=payload, timeout=5)
        return response.json()
    except:
        return None

st.set_page_config(page_title="Sentinel AI", page_icon="🚀", layout="wide")

# Logo
try:
    logo = Image.open("banner.png")
    st.image(logo, use_column_width=True, caption="IQ Signals PRO")
except:
    st.image("https://via.placeholder.com/800x100/0066cc/white?text=SENTINEL+AI", use_column_width=True)
    
    # **SIDEBAR con tasto dinamico CONNETTI/ESCI**
with st.sidebar:
    st.header("⚙️ **TRADING IQ OPTION**")
    
    if not st.session_state.get('connected', False):
        email = st.text_input("Email Practice", value="mago_magoz@libero.it")
        password = st.text_input("Password", type="password")
        
        if st.button("🔗 **CONNETTI**", type="primary", use_container_width=True):
            try:
                Iq = IQ_Option(email, password)
                check, reason = Iq.connect()
                if check:
                    st.session_state['iq'] = Iq
                    st.session_state['connected'] = True
                    st.session_state['email'] = email
                    st.session_state['pair'] = "EURUSD"
                    st.session_state['signal_history'] = []
                    st.success("✅ CONNESSO!")
                    st.balloons()
                    st.rerun()
                else:
                    st.error(f"❌ {reason}")
            except Exception as e:
                st.error(f"❌ Errore: {str(e)}")
   
    else:
        st.success(f"🟢 Connesso")
        
        st.header("📊 **ANALIZZA LA VALUTA**")
        st.session_state['pair'] = st.selectbox(
            "Coppia", 
            ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"], 
            index=0
        )

        if st.button("🔴 **DISCONNETTI**", type="secondary", use_container_width=True):
            try:
                st.session_state['iq'].close()
            except:
                pass
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("👋 Disconnesso!")
            st.rerun()
    
    # **SESSIONI MERCATO FOREX**
    if st.session_state.get('connected', False):
        st.markdown("---")
        st.header("🌍 **SESSIONI MERCATO**")
        
        now_cet = datetime.now()
        ora_cet = now_cet.time()
        
        sessioni = {
            "🇦🇺 SYDNEY": {"inizio": time(23,0), "fine": time(8,0)},
            "🇯🇵 TOKYO": {"inizio": time(1,0), "fine": time(10,0)}, 
            "🇬🇧 LONDRA": {"inizio": time(9,0), "fine": time(18,0)},
            "🇺🇸 NEW YORK": {"inizio": time(14,0), "fine": time(23,0)}
        }
        
        for nome, orari in sessioni.items():
            inizio, fine = orari["inizio"], orari["fine"]
            
            if inizio < fine:
                aperto = inizio <= ora_cet <= fine
            else:
                aperto = ora_cet >= inizio or ora_cet <= fine
            
            if aperto:
                colore = "🟢 APERTO"
                badge = "background: linear-gradient(45deg, #00ff88, #00cc66); color: black;"
            else:
                colore = "🔴 CHIUSO"
                badge = "background: #333; color: #aaa;"
            
            st.markdown(f"""
            <div style='padding: 12px; margin: 5px 0; border-radius: 12px; 
                        {badge} text-align: center; font-weight: bold; font-size: 16px;'>
                {nome} | {colore} | {ora_cet.strftime('%H:%M')}
            </div>
            """, unsafe_allow_html=True)
        
        # SOVRAPPOSIZIONI
        sovrapposizioni = []
        if time(9,0) <= ora_cet <= time(10,0): sovrapposizioni.append("🌍 Tokyo-Londra")
        if time(14,0) <= ora_cet <= time(18,0): sovrapposizioni.append("🚀 Londra-NY")
        
        if sovrapposizioni:
            st.markdown(f"""
            <div style='padding: 10px; margin: 10px 0; background: linear-gradient(45deg, #ffaa00, #ff8800); 
                        color: black; border-radius: 12px; text-align: center; font-weight: bold;'>
                ⚡ SOVRAPPOSIZIONE: {' + '.join(sovrapposizioni)} (MAX VOLUME!)
            </div>
            """, unsafe_allow_html=True)
       
        st.markdown("---")
        
        if st.button("🚀 **TEST COMPLETO**", key="test_full"):
            send_telegram_signal("BUY", "EURUSD", 1.08542, 28.4, 0.00015)
            send_telegram_signal("SELL", "GBPUSD", 1.26580, 72.1, -0.00023)
            st.session_state['scanner_alerts'] = [
                {'pair': 'EURUSD', 'type': '🟢 COMPRA', 'price': '1.08542', 'rsi': '28.4'},
                {'pair': 'GBPUSD', 'type': '🔴 VENDI', 'price': '1.26580', 'rsi': '72.1'}
            ]
            st.success("✅ TEST OK! Popup+Telegram!")
            st.balloons()
            st.rerun()


        # RESET BUTTON (FINE PAGINA)
        if st.button("🗑️ **RESET COMPLETO**", key="clear_all"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("✅ RESET COMPLETO!")
            st.rerun()



ALL_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"]

# INIZIALIZZAZIONE SESSION STATE
if st.session_state.get('connected', False):
    init_keys = [
        'scanner', 'scanner_data', 'scanner_last_update', 'scanner_alerts',
        'rsi_buy', 'rsi_sell', 'amount', 'trades_executed', 'total_profit',
        'current_balance', 'initial_balance', 'auto_trade'
    ]
    
    for key in init_keys:
        if key not in st.session_state:
            if key == 'scanner': st.session_state[key] = False
            elif key == 'scanner_data': st.session_state[key] = {}
            elif key == 'scanner_last_update': st.session_state[key] = 0
            elif key == 'scanner_alerts': st.session_state[key] = []
            elif key == 'rsi_buy': st.session_state[key] = 40
            elif key == 'rsi_sell': st.session_state[key] = 60
            elif key == 'amount': st.session_state[key] = 1
            elif key == 'trades_executed': st.session_state[key] = []
            elif key == 'total_profit': st.session_state[key] = 0.0
            elif key == 'current_balance': st.session_state[key] = 10000.0
            elif key == 'initial_balance': st.session_state[key] = 10000.0
            elif key == 'auto_trade': st.session_state[key] = False

    Iq = st.session_state['iq']

    # BALANCE LIVE PRACTICE
    try:
        Iq.change_balance("PRACTICE")
        st.session_state.current_balance = float(Iq.get_balance())
        
        if 'initial_balance' not in st.session_state or st.session_state.initial_balance == 0:
            st.session_state.initial_balance = st.session_state.current_balance
            
        profit = st.session_state.current_balance - st.session_state.initial_balance
        st.session_state.total_profit = profit
        
        col1, col2, col3 = st.columns(3)
        col1.metric("💰 Balance Practice", f"€{st.session_state.current_balance:.2f}")
        col2.metric("📈 Profitto", f"€{profit:.2f}", 
                   delta=f"{(profit/st.session_state.initial_balance)*100:.1f}%")
        
        # WINRATE REALE ✅ CORRETTO
        if st.session_state.trades_executed:
            trades_df = pd.DataFrame(st.session_state.trades_executed)
            won_trades = len(trades_df[trades_df['status'] == '✅ VINTO'])
            total_trades = len(trades_df)
            winrate = (won_trades / total_trades * 100) if total_trades > 0 else 0
            col3.metric("🎯 Winrate", f"{winrate:.1f}%", delta=f"{won_trades}/{total_trades}")
        else:
            col3.metric("🎯 Winrate", "0%", delta="0/0")
        
    except Exception as e:
        st.error(f"❌ Errore balance: {str(e)}")

    st.markdown("---")

    # CONTROLLI SCANNER + TRADE AUTO
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.scanner = st.toggle("🔍 **Attiva Scanner**", value=st.session_state.scanner)
    with col2:
        st.session_state.auto_trade = st.toggle("🤖 **Trade Automatici 1m**", value=st.session_state.auto_trade)

    col1, col2, col3 = st.columns(3)
    with col1: 
        st.session_state.rsi_buy = st.number_input("🟢 RSI Buy", value=st.session_state.rsi_buy, min_value=10, max_value=45)
    with col2: 
        st.session_state.rsi_sell = st.number_input("🔴 RSI Sell", value=st.session_state.rsi_sell, min_value=55, max_value=90)
    with col3: 
        st.session_state.amount = st.number_input("💵 Importo €", value=st.session_state.amount, min_value=1, max_value=1000)

    # SCANNER + TRADING
    if st.session_state.scanner:
        last_scan = datetime.fromtimestamp(st.session_state.scanner_last_update).strftime("%H:%M:%S") if st.session_state.scanner_last_update else "Mai"
        st.markdown(f"🕐 **Ultimo update**: {last_scan}")
        
        current_time = time_module.time()
        if current_time - st.session_state.scanner_last_update > 30:
            placeholder = st.empty()
            with placeholder.container():
                st.spinner("🔍 Scanning 10 coppie + Trading...")

            st.session_state.scanner_data = {}
            st.session_state.scanner_alerts = []
            trades_this_scan = 0
    
            for pair in ALL_PAIRS:
                try:
                    candles = Iq.get_candles(pair, 60, 50, time_module.time())
                    if not candles or len(candles) < 30:
                        raise ValueError("Dati insufficienti")
    
                    df = pd.DataFrame(candles)
                    df['from'] = pd.to_datetime(df['from'], unit='s')
                    df.set_index('from', inplace=True)
    
                    df['RSI'] = ta.rsi(df['close'], length=14)
                    macd = ta.macd(df['close'])
                    df['MACD'] = macd['MACD_12_26_9']
                    df['MACD_signal'] = macd['MACDs_12_26_9']
    
                    latest_rsi = float(df['RSI'].iloc[-1])

                    # ✅ MACD PIÙ SEMPLICE (funziona sempre)
                    macd_current = float(df['MACD'].iloc[-1])
                    macd_signal_current = float(df['MACD_signal'].iloc[-1])
                    macd_current_prev = float(df['MACD'].iloc[-2])
                    macd_signal_prev = float(df['MACD_signal'].iloc[-2])

                    
                    macd_bullish = (float(df['MACD'].iloc[-1]) > float(df['MACD_signal'].iloc[-1])) and \
                                   (float(df['MACD'].iloc[-2]) <= float(df['MACD_signal'].iloc[-2]))
                    macd_bearish = (float(df['MACD'].iloc[-1]) < float(df['MACD_signal'].iloc[-1])) and \
                                   (float(df['MACD'].iloc[-2]) >= float(df['MACD_signal'].iloc[-2]))
                    current_price = float(df['close'].iloc[-1])
                    
                    signal = "⚪ ATTESA"
    
                    # TRADE CALL AUTOMATICO ✅ CORRETTO
                    if (st.session_state.auto_trade and 
                        latest_rsi < st.session_state.rsi_buy and 
                        macd_bullish):
                        
                        result = Iq.buy(
                            amount=st.session_state.amount,
                            asset=pair,
                            action="call",
                            duration=1
                        )
    
                        trade_id = result.get('id', f"{pair}_{int(time_module.time())}")
                        trade_info = {
                            'time': datetime.now().strftime("%H:%M:%S"),
                            'pair': pair,
                            'type': '🟢 CALL',
                            'amount': st.session_state.amount,
                            'price': f"{current_price:.5f}",
                            'rsi': f"{latest_rsi:.1f}",
                            'macd': f"{df['MACD'].iloc[-1]:.5f}",
                            'id': trade_id,
                            'status': '⏳ PENDING'  # ✅ CORRETTO
                        }
                        
                        st.session_state.trades_executed.append(trade_info)
                        st.session_state.scanner_alerts.append(trade_info)
                        trades_this_scan += 1
                        signal = "🟢🔼 COMPRA AUTO"
                        send_telegram_signal("BUY", pair, current_price, latest_rsi, float(df['MACD'].iloc[-1]))
    
                    elif (st.session_state.auto_trade and 
                          latest_rsi > st.session_state.rsi_sell and 
                          macd_bearish):
                        
                        result = Iq.buy(
                            amount=st.session_state.amount,
                            asset=pair,
                            action="put",
                            duration=1
                        )
    
                        trade_id = result.get('id', f"{pair}_{int(time_module.time())}")
                        trade_info = {
                            'time': datetime.now().strftime("%H:%M:%S"),
                            'pair': pair,
                            'type': '🔴 PUT',
                            'amount': st.session_state.amount,
                            'price': f"{current_price:.5f}",
                            'rsi': f"{latest_rsi:.1f}",
                            'macd': f"{df['MACD'].iloc[-1]:.5f}",
                            'id': trade_id,
                            'status': '⏳ PENDING'  # ✅ CORRETTO
                        }
                        
                        st.session_state.trades_executed.append(trade_info)
                        st.session_state.scanner_alerts.append(trade_info)
                        trades_this_scan += 1
                        signal = "🔴🔽 VENDI AUTO"
                        send_telegram_signal("SELL", pair, current_price, latest_rsi, float(df['MACD'].iloc[-1]))
    
                    st.session_state.scanner_data[pair] = {
                        'price': f"{current_price:.5f}",
                        'rsi': f"{latest_rsi:.1f}",
                        'signal': signal
                    }
    
                except Exception as e:
                    st.session_state.scanner_data[pair] = {
                        'price': '❌', 'rsi': '❌', 'signal': 'ERROR'
                    }
    
            st.session_state.scanner_last_update = current_time
            placeholder.success(f"✅ Update completato! {trades_this_scan} trade eseguiti")
            st.rerun()
        else:
            next_scan = 30 - (current_time - st.session_state.scanner_last_update)
            st.info(f"⏳ Scanner attivo - prossimo update tra {next_scan:.0f}s")
    
    st.markdown("---")
    
    # TABELLA SCANNER
    st.subheader("🔍 **SCANNER FOREX**")
    if st.session_state.scanner and st.session_state.scanner:
        scanner_df = pd.DataFrame(st.session_state.scanner_data).T
        scanner_df.reset_index(inplace=True)
        scanner_df.rename(columns={'index': 'PAIR'}, inplace=True)
        scanner_df = scanner_df[['PAIR', 'price', 'rsi', 'signal']]
        
        scanner_df.rename(columns={
            'PAIR': '💱 COPPIA',
            'price': '💰 PREZZO', 
            'rsi': '📊 RSI',
            'signal': '🚦 SEGNALE'
        }, inplace=True)
        
        st.dataframe(scanner_df, use_container_width=True, height=400, hide_index=True)
    
    # TRADES LIVE
    if st.session_state.trades_executed:
        st.subheader("📊 **TRADES IN CORSO**")
        trades_df = pd.DataFrame(st.session_state.trades_executed)
        st.dataframe(trades_df, use_container_width=True)

    # CHECK ESITI TRADES ✅ CORRETTO
    if st.session_state.trades_executed:
        Iq = st.session_state['iq']
        for i, trade in enumerate(st.session_state.trades_executed):
            if trade['status'] == '⏳ PENDING':
                try:
                    result = Iq.check_win_v3(trade['id'])
                    if result and result.get('win') is not None:
                        if result['win']:
                            st.session_state.trades_executed[i]['status'] = '✅ VINTO'
                            st.session_state.trades_executed[i]['payout'] = result.get('win_amount', trade['amount'] * 0.8)
                        else:
                            st.session_state.trades_executed[i]['status'] = '❌ PERSO'
                            st.session_state.trades_executed[i]['payout'] = -trade['amount']
                except:
                    pass

    # ALERT POPUP
    if st.session_state.get('scanner_alerts', []):
        for alert in st.session_state.scanner_alerts:
            col1, col2 = st.columns([3,1])
            with col1:
                color = "#00ff88" if "CALL" in alert['type'] or "COMPRA" in alert['type'] else "#ff4444"
                st.markdown(f"""
                <div style='background: linear-gradient(45deg, {color}, {color}); 
                padding: 25px; border-radius: 20px; border: 4px solid #00ff00; 
                text-align: center; font-size: 24px; font-weight: bold; color: black;'>
                    🚀 **{alert['type']} {alert['pair'].upper()}**
                    <div style='font-size: 28px; margin-top: 10px;'>
                        💰 {alert['price']} | 📊 RSI: {alert['rsi']}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                if st.button("✅ OK", key=f"alert_{alert['pair']}"):
                    st.session_state.scanner_alerts = [a for a in st.session_state.scanner_alerts if a['pair'] != alert['pair']]
                    st.rerun()
        st.markdown("---")

    st.markdown("---")

    # LIVE STATUS
    st.subheader("📈 LIVE STATUS")
    if (st.session_state.get('connected', False) and 
        st.session_state.get('pair')):
        
        try:
            Iq = st.session_state['iq']
            pair = st.session_state['pair']
            candles = Iq.get_candles(pair, 60, 50, time_module.time())
            df_live = pd.DataFrame(candles)
            df_live['from'] = pd.to_datetime(df_live['from'], unit='s')
            df_live.set_index('from', inplace=True)
            
            df_live['RSI'] = ta.rsi(df_live['close'], length=14)
            macd = ta.macd(df_live['close'])
            df_live['MACD'] = macd['MACD_12_26_9']
            df_live['MACD_signal'] = macd['MACDs_12_26_9']
            
            latest = df_live.iloc[-1]
            st.session_state['df_live'] = df_live
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("💰 PREZZO", f"{latest['close']:.5f}")
            with col2:
                st.metric("📊 RSI", f"{latest['RSI']:.1f}")
            with col3:
                st.metric("🔥 MACD", f"{latest['MACD']:.5f}")
            with col4:
                trend = "📈 UP" if latest['MACD'] > latest['MACD_signal'] else "📉 DOWN"
                st.metric("⚡ TREND", trend)
                
        except:
            st.info("⏳ Caricamento dati live...")
    
    st.markdown("---")

# GRAFICO CENTRALE ✅ COMPLETO
if st.session_state.get('connected', False):
    Iq = st.session_state['iq']
    pair = st.session_state.get('pair', 'EURUSD')
    rsi_buy = st.session_state.get('rsi_buy', 30)
    rsi_sell = st.session_state.get('rsi_sell', 70)
    
    st.subheader(f"📊 GRAFICO REALTIME - {pair.upper()}")
    
    try:
        candles = Iq.get_candles(pair, 60, 150, time_module.time())
        df = pd.DataFrame(candles)
        df['from'] = pd.to_datetime(df['from'], unit='s')
        df.set_index('from', inplace=True)
        
        # INDICATORI
        df['RSI'] = ta.rsi(df['close'], length=14)
        bbands = ta.bbands(df['close'], length=20, std=2.0)
        
        bb_cols = [col for col in bbands.columns if 'BB' in col]
        if len(bb_cols) >= 3:
            df['BBU'] = bbands[bb_cols[0]]
            df['BBM'] = bbands[bb_cols[1]] 
            df['BBL'] = bbands[bb_cols[2]]
        else:
            df['BBU'] = df['close'].rolling(20).mean() + (df['close'].rolling(20).std() * 2)
            df['BBM'] = df['close'].rolling(20).mean()
            df['BBL'] = df['close'].rolling(20).mean() - (df['close'].rolling(20).std() * 2)
        
        macd = ta.macd(df['close'])
        df['MACD'] = macd['MACD_12_26_9']
        df['MACD_signal'] = macd['MACDs_12_26_9']
        
        st.session_state['df'] = df
        
        # GRAFICO
        df_last_hour = df.tail(60).copy()
        fig = make_subplots(
            rows=3, cols=1,
            subplot_titles=(f'💹 TREND PREZZO CON BB', '📈 RSI', '📉 MACD'),
            row_heights=[0.5, 0.175, 0.175],
            vertical_spacing=0.05,
            shared_xaxes=True
        )
        
        # CANDELE
        fig.add_trace(go.Candlestick(
            x=df_last_hour.index, open=df_last_hour['open'], 
            high=df_last_hour['max'], low=df_last_hour['min'], 
            close=df_last_hour['close'], 
            increasing_line_color='#00ff88', decreasing_line_color='#ff4444'), 
            row=1, col=1)

        # BOLLINGER
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['BBU'], 
                               line=dict(color='#00ccff', width=1.5), name='BBU', opacity=0.7), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['BBM'], 
                               line=dict(color='#ffaa00', width=2), name='BBM'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['BBL'], 
                               line=dict(color='#00ccff', width=1.5), fill='tonexty',
                               fillcolor='rgba(0, 204, 255, 0.15)', showlegend=False), row=1, col=1)
        
        # RSI
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['RSI'], 
                               line=dict(color='purple', width=2)), row=2, col=1)
        fig.add_hline(y=rsi_buy, line_dash="solid", line_color="#00ff00", line_width=3, row=2, col=1)
        fig.add_hline(y=rsi_sell, line_dash="solid", line_color="#ff0000", line_width=3, row=2, col=1)
        
        # MACD
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['MACD'], 
                               line=dict(color='orange', width=2)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df_last_hour.index, y=df_last_hour['MACD_signal'], 
                               line=dict(color='red', width=2)), row=3, col=1)
        fig.add_hline(y=0, line_dash="dot", line_color="gray", row=3, col=1)
        
        # GRIGLIA
        for i in range(0, len(df_last_hour), 5):
            fig.add_vline(x=df_last_hour.index[i], line_dash="dot", line_color="gray", 
                         opacity=0.3, row=1, col=1, layer="below")
            fig.add_vline(x=df_last_hour.index[i], line_dash="dot", line_color="gray", 
                         opacity=0.3, row=2, col=1, layer="below")
            fig.add_vline(x=df_last_hour.index[i], line_dash="dot", line_color="gray", 
                         opacity=0.3, row=3, col=1, layer="below")
        
        fig.update_layout(height=900, showlegend=False, title=f"🎯 {pair.upper()} - ULTIMA ORA", 
                         xaxis_rangeslider_visible=False, margin=dict(t=100))
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"❌ Grafico {pair}: {e}")

    # CRONOLOGIA SEGNALI
    st.markdown("---")
    st.subheader("📋 CRONOLOGIA SEGNALI")
    
    if 'signal_history' in st.session_state and st.session_state['signal_history']:
        signals_df = pd.DataFrame(st.session_state['signal_history'])
        cols = ['time', 'pair', 'type', 'price_entry', 'rsi', 'macd', 'outcome']
        signals_df = signals_df[cols] if len(signals_df.columns) >= len(cols) else signals_df
        
        signals_df.columns = ['Ora', 'Valuta', 'Azione', 'Prezzo Entrata', 'RSI', 'MACD', 'Esito']
        signals_df.reset_index(drop=True, inplace=True)
        signals_df.index += 1
        
        st.dataframe(signals_df, use_container_width=True, height=350, hide_index=False)
    else:
        st.info("⏳ Nessun segnale generato")
