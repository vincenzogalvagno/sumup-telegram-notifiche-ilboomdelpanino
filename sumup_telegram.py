"""
Notifiche Pagamenti SumUp → Telegram
Versione per GitHub Actions: esegue un singolo controllo e termina.
Lo stato (ultima transazione vista) è salvato direttamente nel repository.

Attivo dalle 17:00 alle 03:00 ora italiana.
"""

import os
import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# Fuso orario italiano (gestisce automaticamente ora legale/solare)
FUSO_ITALIA = ZoneInfo("Europe/Rome")

# --- Configurazione (variabili d'ambiente) ---
SUMUP_API_KEY = os.environ["SUMUP_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# --- Orari di attività ---
ORA_INIZIO = 9  # 9:00
ORA_FINE = 3     # 03:00

# --- File per ricordare l'ultima transazione vista ---
LAST_TXN_FILE = "last_transaction.json"

SUMUP_API_URL = "https://api.sumup.com"
SUMUP_HEADERS = {
    "Authorization": f"Bearer {SUMUP_API_KEY}",
    "Accept": "application/json",
}


def e_orario_attivo():
    """Controlla se siamo tra le 17:00 e le 03:00 ora italiana."""
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
        print("[OK] Notifica Telegram inviata")
    except requests.RequestException as e:
        print(f"[ERRORE] Invio Telegram fallito: {e}")


def formatta_messaggio(txn):
    """Formatta il messaggio di notifica per una transazione."""
    importo = txn.get("amount", 0)
    valuta = txn.get("currency", "EUR")
    timestamp = txn.get("timestamp", "")
    tipo_carta = txn.get("card_type", "Carta")
    codice = txn.get("transaction_code", "")

    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        dt_italia = dt.astimezone(FUSO_ITALIA)
        data_formattata = dt_italia.strftime("%d/%m/%Y - %H:%M")
    except (ValueError, AttributeError):
        data_formattata = timestamp

    simbolo = "€" if valuta == "EUR" else valuta

    return (
        f"💳 <b>Pagamento ricevuto!</b>\n"
        f"Importo: {simbolo}{importo:.2f}\n"
        f"Data: {data_formattata}\n"
        f"Carta: {tipo_carta}\n"
        f"Codice: {codice}"
    )


def main():
    ora_italia = datetime.now(FUSO_ITALIA).strftime("%H:%M")
    print(f"[INFO] Controllo alle {ora_italia} ora italiana")

    if not e_orario_attivo():
        print(f"[PAUSA] Fuori orario (attivo {ORA_INIZIO}:00 - {ORA_FINE:02d}:00)")
        return

    ultimo_id = carica_ultima_transazione()
    transazioni = ottieni_transazioni()

    if not transazioni:
        print("[INFO] Nessuna transazione trovata")
        return

    if ultimo_id is None:
        salva_ultima_transazione(transazioni[0]["id"])
        print("[INFO] Prima esecuzione: salvata transazione più recente come riferimento")
        return

    nuove = []
    for txn in transazioni:
        if txn["id"] == ultimo_id:
            break
        nuove.append(txn)

    if not nuove:
        print("[INFO] Nessuna nuova transazione")
        return

    for txn in reversed(nuove):
        messaggio = formatta_messaggio(txn)
        invia_telegram(messaggio)

    salva_ultima_transazione(transazioni[0]["id"])
    print(f"[INFO] Notificate {len(nuove)} nuove transazioni")


if __name__ == "__main__":
    main()
