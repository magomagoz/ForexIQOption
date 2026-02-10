import streamlit as st
import pandas as pd
import pandas_ta as ta
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from iqoptionapi.stable_api import IQ_Option

st.set_page_config(page_title="IQ Signals PRO", layout="wide")

st.title("🚀 IQ Option Signals PRO - Popup Alert 1m")

# SIDEBAR CONFIG
with st.sidebar:
    st.header("⚙️ Config")
    email = st.text_input("Email Practice", type="password")
    password = st.text_input("Password", type="password")
    pair = st.selectbox("Coppia", ["EURUSD", "GBPUSD", "USDJPY"])
    rsi_buy = st.slider("RSI Buy Level", 20, 40, 30)
    rsi_sell = st.slider("RSI Sell Level", 60, 80, 70)
    
    st.header("📊 Status")
    if st.button("🔗 CONNETTI PRACTICE", use_container_width=True):
        try:
            Iq = IQ_Option(email, password)
            check, reason = Iq.connect()
            if check:
                st.session_state['iq'] = Iq
                st.session_state['connected'] = True
                st.session_state['email'] = email
                st.session_state['pair'] = pair
                st.success("✅ CONNESSO!")
                st.balloons()
            else:
                st.error(f"❌ {reason}")
        except Exception as e:
            st.error(f"❌ {e}")

# MAIN LOGIC + AUTO REFRESH 60s
if st.session_state.get('connected', False):
    # COUNTDOWN VISIBILE
    next_refresh = st.session_state.get('next_refresh', time.time() + 60)
    remaining = max(0, next_refresh - time.time())
    
    col1, col2 = st.columns([3,1])
    with col1:
        st.metric("⏱️ PROSSIMO REFRESH", f"{int(remaining)} secondi", delta=None)
    with col2:
        if st.button("🔄 REFRESH ORA", use_container_width=True):
            st.session_state['next_refresh'] = time.time()
    
    # AUTO REFRESH
    if remaining <= 0:
        st.session_state['next_refresh'] = time.time() + 60
        st.rerun()
    
    # ANALISI REALTIME
    Iq = st.session_state['iq']
    
    # Layout 2 colonne
    left_col, right_col = st.columns([2,1])
    
    with left_col:
        # GRANDE GRAFICO CON LINEE RSI
        try:
            candles = Iq.get_candles(pair, 60, 150, time.time())
            df = pd.DataFrame(candles)
            df['from'] = pd.to_datetime(df['from'], unit='s')
            df.set_index('from', inplace=True)
            
            # INDICATORI
            df['RSI'] = ta.rsi(df['close'], length=14)
            macd = ta.macd(df['close'])
            df['MACD'] = macd['MACD_12_26_9']
            df['MACD_signal'] = macd['MACDs_12_26_9']
            
            # SEGNALI IQ OPTION 1m
            df['prev_MACD'] = df['MACD'].shift(1)
            df['prev_signal'] = df['MACD_signal'].shift(1)
            
            df['BUY_SIGNAL'] = (
                (df['RSI'] < rsi_buy) & 
                (df['MACD'] > df['MACD_signal']) &
                (df['prev_MACD'] <= df['prev_signal'])
            )
            
            df['SELL_SIGNAL'] = (
                (df['RSI'] > rsi_sell) & 
                (df['MACD'] < df['MACD_signal']) &
                (df['prev_MACD'] >= df['prev_signal'])
            )
            
            st.session_state['df'] = df
            
            # **POPUP ALERT** NUOVI SEGNALI
            current_signals = len(df[df['BUY_SIGNAL'] == True].tail(5))
            prev_signals = st.session_state.get('prev_signals', 0)
            
            if current_signals > prev_signals:
                # 🎉 POPUP TOAST AGGRESSIVO
                st.toast(f"🚀 **SEGNALE BUY {pair}!** RSI:{df['RSI'].iloc[-1]:.0f} Prezzo:{df['close'].iloc[-1]:.5f}", 
                        icon="📈")
                st.balloons()
            
            st.session_state['prev_signals'] = current_signals
            
        except Exception as e:
            st.error(f"Dati: {e}")
    
    # GRAFICO PLOTLY CON RSI 30/70
    if 'df' in st.session_state:
        df = st.session_state['df']
        
        fig = make_subplots(rows=3, cols=1, 
                          subplot_titles=('💹 Prezzo Close', '📊 MACD', '🎯 RSI LEVELS'),
                          row_heights=[0.5, 0.25, 0.25],
                          vertical_spacing=0.05)
        
        # Prezzo
        fig.add_trace(go.Scatter(x=df.index[-60:], y=df['close'][-60:], 
                               name='Close', line=dict(width=2, color='#00ff88')), row=1, col=1)
        
        # MACD
        colors = ['orange' if x > 0 else 'red' for x in df['MACD'].tail(60)]
        fig.add_trace(go.Scatter(x=df.index[-60:], y=df['MACD'][-60:], 
                               name='MACD', line=dict(color='orange')), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index[-60:], y=df['MACD_signal'][-60:], 
                               name='Signal', line=dict(color='red')), row=2, col=1)
        
        # RSI CON LINEE EVIDENZIATE
        fig.add_trace(go.Scatter(x=df.index[-60:], y=df['RSI'][-60:], 
                               name='RSI', line=dict(color='purple', width=2)), row=3, col=1)
        
        # **LINE RSI 30/70 SUPER EVIDENZIATE**
        fig.add_hline(y=rsi_buy, line_dash="solid", line_color="#00ff00", 
                     line_width=3, annotation_text=f"🟢 BUY <{rsi_buy}", row=3, col=1)
        fig.add_hline(y=rsi_sell, line_dash="solid", line_color="#ff0000", 
                     line_width=3, annotation_text=f"🔴 SELL >{rsi_sell}", row=3, col=1)
        fig.add_hline(y=50, line_dash="dash", line_color="gray", row=3, col=1)
        
        fig.update_layout(height=750, showlegend=True, 
                        title=f"🎯 {pair} 1m - **IQ OPTION TURBO SIGNALS**")
        st.plotly_chart(fig, use_container_width=True)
    
    # **PANEL DESTRA: ALERT + STATS**
    with right_col:
        st.header("🚨 ALERT LIVE")
        
        if 'df' in st.session_state:
            df = st.session_state['df']
            latest = df.iloc[-1]
            
            # **CONFERMA TRADE IQ OPTION 1m**
            st.markdown("### 📋 **COME FARE IL TRADE**")
            st.info("""
            **TURBO OPTION 1 MINUTO:**
            1. **ENTRATA**: Prezzo attuale candela corrente
            2. **DIREZIONE**: Higher/Lower basata sul segnale  
            3. **SCADENZA**: 60 secondi (1 candela)
            4. **VITTORIA**: Se candela chiude nella direzione giusta
            5. **PAYOUT**: 80-95% profitto
            """)
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("💵 **PREZZO ENTRATA**", f"{latest['close']:.5f}")
                st.metric("📊 **RSI ATTUALE**", f"{latest['RSI']:.0f}")
            
            with col_b:
                st.metric("🔥 **MACD**", f"{latest['MACD']:.5f}")
                st.metric("⚡ **Trend**", "🟢 BULLISH" if latest['MACD'] > latest['MACD_signal'] else "🔴 BEARISH")
            
            # SEGNALI RECENTI
            buy_signals = df[df['BUY_SIGNAL'] == True].tail(3)
            if not buy_signals.empty:
                st.success(f"🚀 **{len(buy_signals)} BUY RECENTI**")
                for idx, row in buy_signals.iterrows():
                    st.caption(f"🕐 {idx.strftime('%H:%M')} | 💰 {row['close']:.5f} | RSI {row['RSI']:.0f}")
