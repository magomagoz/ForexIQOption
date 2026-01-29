# file: iq_bot.py
from iqoptionapi.stable_api import IQ_Option
import time

class IQHandler:
    def __init__(self, email, password):
        self.api = IQ_Option(email, password)
        self.connected = False

    def connetti(self):
        check, reason = self.api.connect()
        if check:
            print("✅ Connesso a IQ Option")
            self.api.change_balance("PRACTICE") # O "REAL" (Rischioso!)
            self.connected = True
        else:
            print(f"❌ Errore Connessione: {reason}")
            self.connected = False
        return self.connected

    def get_asset_iq(self, yfinance_ticker):
        # Mappa i nomi di YFinance su quelli di IQ
        # YF: EURUSD=X -> IQ: EURUSD
        return yfinance_ticker.replace("=X", "").replace("-USD", "USD")

    def apri_posizione(self, asset_yf, direzione, importo):
        if not self.connected: return None
        
        asset_iq = self.get_asset_iq(asset_yf)
        action = "call" if direzione == "COMPRA" else "put"
        
        # Compra Opzione Digitale (Scadenza 5 o 15 minuti per dare tempo al trade)
        # duration 1 = 1m, 5 = 5m. Qui usiamo 5 per avere respiro.
        try:
            check, id_ordine = self.api.buy_digital_spot(asset_iq, importo, action, 5)
            if check:
                return id_ordine
            else:
                print("Errore apertura:", id_ordine)
                return None
        except Exception as e:
            print(f"Eccezione IQ: {e}")
            return None

    def chiudi_posizione(self, id_ordine):
        if not self.connected: return False
        
        # Su IQ, "chiudere" significa vendere l'opzione prima della scadenza
        try:
            self.api.close_digital_option(id_ordine)
            return True
        except:
            return False

    def get_profitto_netto(self, id_ordine):
        # Ottiene il P&L attuale di un ordine aperto (per aggiornare la UI)
        # Nota: Richiede chiamate complesse alle API posizioni, 
        # per ora simuliamo o usiamo il calcolo teorico del tuo script.
        pass
