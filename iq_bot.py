from iqoptionapi.stable_api import IQ_Option
import logging

class IQHandler:
    def __init__(self, email, password, mode="PRACTICE"):
        self.api = IQ_Option(email, password)
        self.mode = mode  # "PRACTICE" o "REAL"
        self.connected = False
        # Mappa degli ID per gli asset principali (Forex)
        self.asset_ids = {
            "EURUSD": 1, "GBPUSD": 2, "EURJPY": 4, 
            "USDJPY": 6, "AUDUSD": 99, "USDCAD": 100
        }

    def connetti(self):
        check, reason = self.api.connect()
        if check:
            self.api.change_balance(self.mode)
            self.connected = True
            print(f"✅ IQ Option Connesso ({self.mode})")
        else:
            print(f"❌ Errore Connessione: {reason}")
            self.connected = False
        return self.connected

    def apri_posizione(self, asset_name, direzione, importo, leva=30):
        """Apre una posizione Forex con moltiplicatore"""
        if not self.connected: return None

        # Pulizia nome asset per il mapping
        asset_clean = asset_name.replace("=X", "").upper()
        asset_id = self.asset_ids.get(asset_clean)

        if not asset_id:
            print(f"⚠️ Asset {asset_clean} non trovato nel mapping ID")
            return None

        side = "buy" if direzione in ["COMPRA", "BUY"] else "sell"
        
        # Esecuzione Ordine Forex
        # Parametri: asset_id, amount, side, leverage, type, stop_loss, take_profit
        check, order_id = self.api.buy_order(
            instrument_type="forex",
            instrument_id=asset_clean, # Alcune versioni API usano il nome, altre l'ID
            side=side,
            amount=importo,
            leverage=leva,
            type="market"
        )

        if check:
            return order_id
        else:
            print(f"❌ Errore apertura ordine: {order_id}")
            return None

    def chiudi_posizione(self, order_id):
        """Chiude una posizione aperta tramite l'ID ordine"""
        if not self.connected: return False
        check = self.api.close_order(order_id)
        return check
