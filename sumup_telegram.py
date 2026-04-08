"""
Notifiche Pagamenti SumUp → Telegram
Controlla nuove transazioni SumUp ogni 60 secondi
e invia notifica su Telegram.

Attivo dalle 17:00 alle 03:00.
"""

import os
import time
import json
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Fuso orario italiano (gestisce automaticamente ora legale/solare)
FUSO_ITALIA = ZoneInfo("Europe/Rome")

# --- Configurazione (variabili d'ambiente) ---
SUMUP_API_KEY = os.environ["SUMUP_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# --- Orari di attività ---
ORA_INIZIO = 17  # 17:00
ORA_FINE = 3     # 03:00

# --- File per ricordare l'ultima transazione vista ---
LAST_TXN_FILE = "last_transaction.json"

SUMUP_API_URL = "https://api.sumup.com"
SUMUP_HEADERS = {
    "Authorization": f"Bearer {SUMUP_API_KEY}",
    "Accept": "application/json",
}


def e_orario_attivo():
    """Controlla se siamo tra le 17:00 e le 03:00."""
    ora = datetime.now(FUSO_ITALIA).hour
    if ORA_INIZIO <= ora <= 23:
        return True
    if 0 <= ora < ORA_FINE:
        return True
    return False


def carica_ultima_transazione():
    """Carica l'ID dell'ultima transazione già notificata."""
    try:
        with open(LAST_TXN_FILE, "r") as f:
            data = json.load(f)
            return data.get("last_id")
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def salva_ultima_transazione(txn_id):
    """Salva l'ID dell'ultima transazione notificata."""
    with open(LAST_TXN_FILE, "w") as f:
        json.dump({"last_id": txn_id}, f)


def ottieni_transazioni():
    """Chiede a SumUp le transazioni recenti."""
    try:
        response = requests.get(
            f"{SUMUP_API_URL}/v0.1/me/transactions/history",
            headers=SUMUP_HEADERS,
            params={
                "limit": 10,
                "order": "descending",
                "statuses[]": "SUCCESSFUL",
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("items", [])
    except requests.RequestException as e:
        print(f"[ERRORE] Chiamata SumUp fallita: {e}")
        return []


def invia_telegram(messaggio):
    """Invia un messaggio su Telegram."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        response = requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": messaggio,
                "parse_mode": "HTML",
            },
            timeout=10,
        )
        response.raise_for_status()
        print(f"[OK] Notifica Telegram inviata")
    except requests.RequestException as e:
        print(f"[ERRORE] Invio Telegram fallito: {e}")


def formatta_messaggio(txn):
    """Formatta il messaggio di notifica per una transazione."""
    importo = txn.get("amount", 0)
    valuta = txn.get("currency", "EUR")
    timestamp = txn.get("timestamp", "")
    tipo_carta = txn.get("card_type", "Carta")
    codice = txn.get("transaction_code", "")

    # Formatta la data
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        dt_italia = dt.astimezone(FUSO_ITALIA)
        data_formattata = dt_italia.strftime("%d/%m/%Y - %H:%M")
    except (ValueError, AttributeError):
        data_formattata = timestamp

    # Simbolo valuta
    simbolo = "€" if valuta == "EUR" else valuta

    return (
        f"💳 <b>Pagamento ricevuto!</b>\n"
        f"Importo: {simbolo}{importo:.2f}\n"
        f"Data: {data_formattata}\n"
        f"Carta: {tipo_carta}\n"
        f"Codice: {codice}"
    )


def controlla_nuove_transazioni():
    """Controlla se ci sono nuove transazioni e notifica."""
    ultimo_id = carica_ultima_transazione()
    transazioni = ottieni_transazioni()

    if not transazioni:
        return

    # Se è la prima esecuzione, salva l'ultima transazione senza notificare
    if ultimo_id is None:
        salva_ultima_transazione(transazioni[0]["id"])
        print("[INFO] Prima esecuzione: salvata transazione più recente come riferimento")
        return

    # Trova le transazioni nuove (quelle prima dell'ultimo ID salvato)
    nuove = []
    for txn in transazioni:
        if txn["id"] == ultimo_id:
            break
        nuove.append(txn)

    if not nuove:
        return

    # Notifica ogni nuova transazione (dalla più vecchia alla più recente)
    for txn in reversed(nuove):
        messaggio = formatta_messaggio(txn)
        invia_telegram(messaggio)
        time.sleep(1)  # Pausa tra messaggi per non sovraccaricare Telegram

    # Salva la transazione più recente
    salva_ultima_transazione(transazioni[0]["id"])
    print(f"[INFO] Notificate {len(nuove)} nuove transazioni")


def main():
    print("🚀 Avvio monitoraggio pagamenti SumUp → Telegram")
    print(f"   Orario attivo: {ORA_INIZIO}:00 - {ORA_FINE:02d}:00")
    print(f"   Polling ogni 60 secondi")
    print()

    while True:
        if e_orario_attivo():
            controlla_nuove_transazioni()
        else:
            ora = datetime.now(FUSO_ITALIA).strftime("%H:%M")
            print(f"[PAUSA] {ora} - fuori orario, prossimo controllo tra 5 minuti")
            time.sleep(240)  # Dorme 4 minuti extra (+ il sleep finale di 60 = 5 min)

        time.sleep(60)


if __name__ == "__main__":
    main()
