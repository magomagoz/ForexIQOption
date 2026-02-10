import streamlit as st
import pandas as pd
import pandas_ta as ta
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from iqoptionapi.stable_api import IQ_Option
from PIL import Image

# Metti il tuo logo.png nella stessa cartella del file .py
logo = Image.open("banner1.png")
st.image(logo, use_column_width=True, caption="IQ Signals PRO")

st.set_page_config(page_title="IQ Signals PRO", layout="wide")

#st.title("🚀 SENTINEL AI")

# SIDEBAR CONFIG
with st.sidebar:
    st.header("⚙️ Config")
    email = st.text_input("Email Practice", type="password")
    password = st.text_input("Password", type="password")
    pair = st.selectbox("Coppia", ["EURUSD", "GBPUSD", "USDJPY"])
    rsi_buy = st.slider("RSI Buy Level", 20, 40, 30)
    rsi_sell = st.slider("RSI Sell Level", 60, 80, 70)
    
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

# **ALERT CENTRALE SOPRA TUTTO**
if st.session_state.get('connected', False) and 'df' in st.session_state:
    df = st.session_state['df']
    latest_signals = df[df['BUY_SIGNAL'] == True].tail(1)
    
    if not latest_signals.empty:
        latest = latest_signals.iloc[0]
        # **POPUP CENTRALE GIGANTE**
        st.markdown("""
        <div style='position: fixed; top: 20%; left: 50%; transform: translate(-50%, -50%);
        background: linear-gradient(45deg, #00ff88, #00cc66); padding: 20px; border-radius: 15px;
        border: 3px solid #00ff00; z-index: 1000; font-size: 24px; font-weight: bold;
        box-shadow: 0 10px 30px rgba(0,255,0,0.5); text-align: center; color: black;'>
            🚀 **SEGNALE BUY {pair}!**<br>
            💰 **ENTRATA: {latest_close:.5f}**<br>
            📊 **RSI: {latest_rsi:.0f}**<br>
            **HIGHER 1 MINUTO ORA!**
        </div>
        """.format(pair=pair, latest_close=latest['close'], latest_rsi=latest['RSI']),
        unsafe_allow_html=True)

# MAIN CONTENT
if st.session_state.get('connected', False):
    Iq = st.session_state['iq']
    
    # COUNTDOWN CENTRALE
    next_refresh = st.session_state.get('next_refresh', time.time() + 60)
    remaining = max(0, next_refresh - time.time())
    st.metric("⏱️ AUTO-REFRESH TRA", f"{int(remaining)}s")
    
    if remaining <= 0:
        st.session_state['next_refresh'] = time.time() + 60
        st.rerun()
    
    # ANALISI DATI
    left_col, right_col = st.columns([3, 1])
    
    with left_col:
        st.subheader("📊 GRAFICO REALTIME")
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
            
            # SEGNALI
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
            
            # ALERT TOAST (backup)
            current_signals = len(df[df['BUY_SIGNAL'] == True].tail(5))
            prev_signals = st.session_state.get('prev_signals', 0)
            if current_signals > prev_signals:
                st.toast(f"🚀 NUOVO SEGNALE BUY {pair}!", icon="📈")
            st.session_state['prev_signals'] = current_signals
            
        except Exception as e:
            st.error(f"Dati: {e}")
    
    # **GRAFICO OTTIMIZZATO** (spazio per titoli)
    if 'df' in st.session_state:
        df = st.session_state['df']
        
        # **GRAFICO PIÙ BASSO** per titoli leggibili
        fig = make_subplots(rows=3, cols=1,
                          subplot_titles=('💹 PREZZO', '📊 MACD', '🎯 RSI 30/70'),
                          row_heights=[0.55, 0.225, 0.225],  # **Più spazio in alto**
                          vertical_spacing=0.08,  # **Più spazio tra grafici**
                          specs=[[{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}]])
        
        # Prezzo (ultime 60 candele)
        fig.add_trace(go.Scatter(x=df.index[-60:], y=df['close'][-60:],
                               name='Close', line=dict(width=3, color='#00ff88')), row=1, col=1)
        
        # MACD colorato
        fig.add_trace(go.Scatter(x=df.index[-60:], y=df['MACD'][-60:],
                               name='MACD', line=dict(color='orange', width=2)), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index[-60:], y=df['MACD_signal'][-60:],
                               name='Signal', line=dict(color='red', width=2)), row=2, col=1)
        
        # RSI con livelli EVIDENZIATI
        fig.add_trace(go.Scatter(x=df.index[-60:], y=df['RSI'][-60:],
                               name='RSI', line=dict(color='purple', width=2.5)), row=3, col=1)
        
        # **LINE RSI SUPER EVIDENZIATE**
        fig.add_hline(y=rsi_buy, line_dash="solid", line_color="#00ff00", 
                     line_width=4, annotation_text=f"🟢 BUY", row=3, col=1)
        fig.add_hline(y=rsi_sell, line_dash="solid", line_color="#ff0000", 
                     line_width=4, annotation_text="🔴 SELL", row=3, col=1)
        fig.add_hline(y=50, line_dash="dash", line_color="gray", row=3, col=1)
        fig.add_hline(y=0, line_dash="dot", line_color="gray", row=2, col=1)
        
        fig.update_layout(height=650,  # **Più basso**
                        title=f"🎯 {pair} 1m - IQ OPTION TURBO",
                        showlegend=False,
                        margin=dict(t=80, b=20, l=20, r=20))  # **Margini per titoli**
        
        st.plotly_chart(fig, use_container_width=True)
    
# **POPUP**
st.header("📈 LIVE STATUS")
        
    if 'df' in st.session_state:
        df = st.session_state['df']
        latest = df.iloc[-1]
            
        st.markdown("### 💰 **PREZZO ENTRATA**")
        st.metric("", f"{latest['close']:.5f}")
            
        col_rsi, col_macd = st.columns(2)
        with col_rsi:
            st.metric("📊 RSI", f"{latest['RSI']:.0f}", 
                         delta=None, delta_color="normal")
        with col_macd:
            st.metric("🔥 MACD", f"{latest['MACD']:.5f}")
            
        # **ISTRUZIONI CENTRALIZZATE**
        st.markdown("---")
        st.markdown("""
        <div style='background: linear-gradient(45deg, #1e3c72, #2a5298); 
        color: white; padding: 15px; border-radius: 10px; text-align: center;'>
            <b>🎯 TURBO 1m:</b><br>
            **ENTRATA ORA** → HIGHER/LOWER → **Scadenza 60s**
        </div>
        """, unsafe_allow_html=True)
