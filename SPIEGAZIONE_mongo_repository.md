# Spiegazione di `mongo_repository.py` (riga per riga)

Questo file è il **livello di accesso ai dati** dell'applicazione Flask
`Car-Delivery-Dashboard`. Tutto ciò che riguarda MongoDB — connessione, lettura, scrittura,
cancellazione e "traduzione" dei documenti — vive qui. Il resto dell'app (`app.py`) non parla mai
direttamente con MongoDB: chiama le funzioni di questo file.

> Versione **semplificata** per la demo: niente type hint, una sola connessione come variabile,
> poche funzioni con un compito chiaro ciascuna.

## Contesto: com'è fatto un documento nel database

La collezione è `db_veicoli.vehicles`. Ogni documento (generato da `datagenerator.py`) ha questa forma:

```json
{
  "_id": ObjectId("..."),
  "vin_telaio": "VF1XXXXXXXXXXXXXXXX",
  "marca": "Renault",
  "modello": "Clio",
  "stato_attuale": "In Viaggio",
  "venditore": "Laura Rossi",
  "assegnato_a_cliente": {
    "id_cliente": "CUST-1234",
    "nome": "Mario Bianchi",
    "email": "mario@example.com",
    "numero_telefono": "+39 ..."
  },
  "configurazione": {
    "allestimento": "Techno",
    "motorizzazione": "TCe 90",
    "colore_esterno": "Rosso Passion",
    "pacchetti_inclusi": ["Cruise Control", "..."],
    "pacchetti_aggiuntivi": ["Head-up Display 9,3''"],
    "capacita_batteria_kw": 60,          // solo auto elettriche
    "cavo_ricarica_incluso": true        // solo auto elettriche
  },
  "logistica_timeline": [
    { "stato": "Ordinato in Fabbrica", "data": ISODate("..."), "operatore": "Sistema" },
    { "stato": "In Viaggio",           "data": ISODate("..."), "operatore": "Marco" }
  ]
}
```

Concetto chiave dei **nomi in due lingue**: nel database i campi sono in **italiano**
(`marca`, `stato_attuale`, `configurazione`...). La funzione `normalize_vehicle` li traduce in un
dizionario con chiavi in **inglese** (`brand`, `status`, `trim`...) che i template HTML usano.

> Nota: `normalize_vehicle` estrae **solo i campi che i template mostrano davvero**. Campi come i
> pacchetti o la batteria restano nel documento grezzo e vengono usati dal form di modifica (in
> `app.py`), non dalla versione normalizzata.

---

## Import e connessione (righe 1–16)

```python
import os
from datetime import datetime

from bson import ObjectId
from pymongo import ASCENDING, MongoClient
```
**Righe 1–5.**
- `os` → per leggere le variabili d'ambiente (URI del database, ecc.).
- `datetime` → tipo per gestire le date della timeline.
- `ObjectId` → la classe dell'`_id` di MongoDB. Serve a convertire una stringa (es. `"665f..."`)
  nell'oggetto ID vero e proprio per fare query per `_id`.
- `MongoClient` → il client con cui ci si connette al server MongoDB.
- `ASCENDING` → costante (`1`) che indica l'ordine crescente nell'ordinamento.

```python
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "db_veicoli")
MONGO_COLLECTION_NAME = os.getenv("MONGO_COLLECTION_NAME", "vehicles")
```
**Righe 11–13.** Configurazione. `os.getenv("NOME", "default")` legge una variabile d'ambiente e, se
non esiste, usa il valore di default. Così puoi cambiare database/collezione senza toccare il codice,
ma in locale funziona subito: database `db_veicoli`, collezione `vehicles`, porta `27017`.

```python
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
collection = client[MONGO_DB_NAME][MONGO_COLLECTION_NAME]
```
**Righe 15–16.** La connessione, fatta **una volta sola**:
- **Riga 15** crea il client. `serverSelectionTimeoutMS=3000` = se in 3 secondi non trova un server
  MongoDB, dà errore invece di restare bloccato.
- **Riga 16** `client[DB][COLLEZIONE]` seleziona il database e poi la collezione. La variabile
  `collection` è "la porta d'ingresso": tutte le funzioni sotto la usano per fare `find`, `insert_one`, ecc.

> `MongoClient` **non si connette davvero** in questa riga; la connessione vera avviene alla prima
> operazione. Per questo il file si può importare anche senza Mongo attivo. È anche il motivo per cui
> `datagenerator.py` importa direttamente questa `collection`, riusando la stessa configurazione.

---

## `format_date(value)` — formattare una data (righe 19–25)

```python
def format_date(value):
    # Trasforma una data (o stringa) nel formato leggibile gg/mm/aaaa.
    if not value:
        return "N/D"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    return str(value)[:10]
```

Trasforma una data nella stringa leggibile `giorno/mese/anno`.

- **21–22** se il valore è vuoto/assente → restituisce `"N/D"` (Non Disponibile).
- **23–24** se è un `datetime` → lo formatta come `08/07/2026`.
- **25** in ogni altro caso (es. stringa `"2026-07-08T10:00"`) → lo converte a stringa e prende i
  **primi 10 caratteri** → `"2026-07-08"`.

---

## `normalize_vehicle(document)` — la funzione centrale (righe 28–60)

È la funzione più importante: prende **un documento MongoDB grezzo** (in italiano, annidato) e lo
appiattisce/traduce in un **dizionario "pulito"** che i template HTML sanno usare.

```python
def normalize_vehicle(document):
    config = document.get("configurazione") or {}
    customer = document.get("assegnato_a_cliente") or {}
    timeline = document.get("logistica_timeline") or []
    last_step = timeline[-1] if timeline else None
    last_date = last_step["data"] if last_step else None
```

- **31** estrae il sotto-dizionario `configurazione`; se manca usa `{}` (dizionario vuoto), così le
  `.get()` successive non esplodono. Il trucco `x or {}` significa "usa `x`, ma se è `None`/vuoto usa `{}`".
- **32** stessa cosa per il cliente assegnato.
- **33** stessa cosa per la timeline (lista vuota se assente).
- **34** `last_step` = **l'ultimo evento** della timeline (`timeline[-1]`). Se vuota → `None`.
- **35** `last_date` = la data di quell'ultimo evento (o `None` se non c'è nessun evento).

```python
    return {
        "id": str(document["_id"]),
        "vin": document.get("vin_telaio", ""),
        "brand": document.get("marca", ""),
        "modello": document.get("modello", ""),
        "status": document.get("stato_attuale", ""),
        "seller": document.get("venditore", ""),
        "customer_name": customer.get("nome", ""),
        "trim": config.get("allestimento", "N/D"),
        "motorizzazione": config.get("motorizzazione", "N/D"),
        "color": config.get("colore_esterno", "N/D"),
```
Il dizionario di ritorno (traduzione italiano → inglese):
- **38** `id`: l'`_id` di Mongo convertito in **stringa** con `str(...)` (serve negli URL).
- **39–43** `vin` ← `vin_telaio`, `brand` ← `marca`, `modello`, `status` ← `stato_attuale`,
  `seller` ← `venditore`.
- **44** `customer_name` ← `nome` del cliente.
- **45–47** `trim` ← `allestimento`, `motorizzazione`, `color` ← `colore_esterno` (default `"N/D"`).

```python
        "timeline": [
            {
                "status": step.get("stato", ""),
                "date": format_date(step.get("data")),
                "operator": step.get("operatore", ""),
            }
            for step in timeline
        ],
```
- **48–55** `timeline`: traduce **ogni** evento da italiano (`stato`, `data`, `operatore`) a inglese
  (`status`, `date`, `operator`), con la data già formattata. È una **list comprehension**: "per ogni
  `step` nella timeline, crea questo dizionario tradotto". Se la timeline è vuota, esce una lista vuota.

```python
        "timeline_count": len(timeline),
        "arrival_date": format_date(last_date),
        "arrival_date_iso": last_date.date().isoformat() if isinstance(last_date, datetime) else None,
        "arrival_date_raw": last_date,
    }
```
- **56** `timeline_count`: quanti eventi ci sono (`len`).
- **57** `arrival_date`: data dell'ultimo evento **formattata** `gg/mm/aaaa`.
- **58** `arrival_date_iso`: la stessa data in formato ISO `2026-07-08`, richiesto dal calendario del
  frontend. Se non è una data valida → `None` (così il calendario salta quell'auto).
- **59** `arrival_date_raw`: la data **grezza** (oggetto `datetime` originale), utile per ordinare
  correttamente (confrontare datetime è più affidabile che confrontare stringhe formattate).

> `normalize_vehicle` è il "traduttore universale" per **mostrare** i dati, e calcola anche campi che
> nel DB non esistono (`arrival_date`, `timeline_count`). Per **modificare** un'auto, invece, il form
> usa il documento grezzo (vedi `get_vehicle_document_by_id`).

---

## `list_vehicles(...)` — elenco veicoli (righe 63–75)

```python
def list_vehicles(query=None, public_only=False, limit=None, exclude_id=None):
    # Costruisce il filtro e cerca i veicoli con find(), ordinati per marca.
    criteria = dict(query or {})
    if public_only:
        criteria["stato_attuale"] = {"$ne": "In Preparazione"}
    if exclude_id:
        criteria["_id"] = {"$ne": ObjectId(exclude_id)}

    documents = collection.find(criteria).sort("marca", ASCENDING)
    vehicles = [normalize_vehicle(document) for document in documents]
    if limit is not None:
        return vehicles[:limit]
    return vehicles
```

La funzione più usata: restituisce una lista di veicoli **normalizzati**. Parametri:
- `query`: filtri extra (es. `{"marca": "Renault"}`).
- `public_only`: se `True`, esclude le auto in preparazione (per il catalogo).
- `limit`: numero massimo di risultati.
- `exclude_id`: un ID da **escludere** (usato per i "veicoli correlati").

- **65** `dict(query or {})`: parte dal filtro ricevuto (o vuoto). `dict(...)` ne fa una **copia**,
  così non modifica quello del chiamante.
- **66–67** se `public_only=True` aggiunge la condizione `stato_attuale != "In Preparazione"`.
  `{"$ne": ...}` è l'operatore MongoDB "**not equal**".
- **68–69** se è passato `exclude_id`, aggiunge "`_id` diverso da questo ID". `ObjectId(exclude_id)`:
  la stringa va riconvertita in `ObjectId` per confrontarla col DB.
- **71** esegue la query: `collection.find(criteria)` trova i documenti, `.sort("marca", ASCENDING)`
  li ordina per marca crescente.
- **72** normalizza **ogni** documento (list comprehension).
- **73–75** se è indicato un `limit` restituisce solo i primi `limit` elementi, altrimenti tutta la lista.

---

## `get_vehicle_document_by_id(vehicle_id)` — documento grezzo (righe 78–84)

```python
def get_vehicle_document_by_id(vehicle_id):
    # Cerca un veicolo per _id oppure, se non lo trova, per numero di telaio.
    if ObjectId.is_valid(vehicle_id):
        document = collection.find_one({"_id": ObjectId(vehicle_id)})
        if document:
            return document
    return collection.find_one({"vin_telaio": vehicle_id})
```

Cerca **un solo** veicolo e restituisce il documento **grezzo** (in italiano, com'è nel DB).
Accetta sia un `_id` di Mongo sia un VIN (numero di telaio).

- **80** se `vehicle_id` ha la forma di un ObjectId valido (`ObjectId.is_valid`), lo cerca per `_id`.
- **82–83** se lo ha trovato, lo restituisce subito.
- **84** altrimenti lo cerca per `vin_telaio`. Questo rende gli URL flessibili: `/auto/<id>` funziona
  sia con l'ID sia col telaio. Se non trova nulla, `find_one` restituisce `None`.

---

## `get_vehicle_by_id(vehicle_id)` — veicolo normalizzato (righe 87–90)

```python
def get_vehicle_by_id(vehicle_id):
    # Come sopra, ma restituisce il veicolo gia' normalizzato (per mostrarlo).
    document = get_vehicle_document_by_id(vehicle_id)
    return normalize_vehicle(document) if document else None
```

**Riusa** la funzione precedente (niente codice duplicato) e in più **normalizza** il risultato.

- **89** chiama `get_vehicle_document_by_id` per prendere il documento grezzo.
- **90** se lo ha trovato lo normalizza, altrimenti restituisce `None` (→ l'app farà 404).

**Perché due funzioni?**
- `get_vehicle_by_id` (normalizzato) serve per **mostrare** i dati (i template vogliono `brand`, `status`...).
- `get_vehicle_document_by_id` (grezzo) serve per **modificare** i dati: in `app.py`, il form di
  modifica riempie i campi partendo dal documento originale (con i nomi italiani e la timeline intatta).

---

## `upsert_vehicle_document(document, vehicle_id)` — inserire o aggiornare (righe 93–99)

"Upsert" = **UP**date + in**SERT**: aggiorna se esiste, altrimenti crea.

```python
def upsert_vehicle_document(document, vehicle_id=None):
    # Se c'e' un id -> aggiorna (update_one), altrimenti crea (insert_one).
    if vehicle_id and ObjectId.is_valid(vehicle_id):
        collection.update_one({"_id": ObjectId(vehicle_id)}, {"$set": document})
        return vehicle_id
    result = collection.insert_one(document)
    return str(result.inserted_id)
```

- **95** se è passato un `vehicle_id` **ed** è un ObjectId valido → è un **aggiornamento**.
- **96** `update_one(filtro, aggiornamento)`: il filtro `{"_id": ...}` sceglie il documento;
  `{"$set": document}` sovrascrive i campi indicati lasciando intatti gli altri.
- **97** restituisce lo stesso `vehicle_id` (in un update l'id non cambia).
- **98** se non c'era un id valido → **inserimento**: `insert_one` crea un nuovo documento.
- **99** restituisce il nuovo `_id` generato da Mongo, convertito in stringa (per il redirect).

---

## `delete_vehicle_document(vehicle_id)` — cancellare (righe 102–108)

```python
def delete_vehicle_document(vehicle_id):
    # Cancella per _id oppure per numero di telaio.
    if ObjectId.is_valid(vehicle_id):
        result = collection.delete_one({"_id": ObjectId(vehicle_id)})
    else:
        result = collection.delete_one({"vin_telaio": vehicle_id})
    return result.deleted_count > 0
```

Cancella un veicolo e restituisce `True`/`False` a seconda che qualcosa sia stato cancellato.

- **104–105** se l'id è un ObjectId valido → cancella per `_id`.
- **106–107** altrimenti → cancella per `vin_telaio`.
- **108** `result.deleted_count` è quanti documenti sono stati eliminati (0 o 1); `> 0` lo trasforma
  in booleano.

---

## `dashboard_summary()` — i numeri della home (righe 111–120)

```python
def dashboard_summary():
    # Raggruppa i veicoli per stato e li conta ($group + $sum).
    pipeline = [{"$group": {"_id": "$stato_attuale", "count": {"$sum": 1}}}]
    counts = {row["_id"]: row["count"] for row in collection.aggregate(pipeline)}
    return {
        "total": sum(counts.values()),
        "ready": counts.get("Pronta per la consegna", 0) + counts.get("Arrivato in Concessionaria", 0),
        "in_transit": counts.get("In Viaggio", 0),
        "in_preparation": counts.get("In Preparazione", 0),
    }
```

Calcola le statistiche della homepage con una **aggregation pipeline** (più efficiente che scaricare
tutti i documenti e contarli in Python).

- **113** la pipeline ha un solo stadio, `$group`:
  - `"_id": "$stato_attuale"` = raggruppa per valore del campo `stato_attuale`. Il `$` significa
    "il **valore** del campo".
  - `"count": {"$sum": 1}` = per ogni gruppo somma `1` a ogni documento → li conta.
- **114** `.aggregate(pipeline)` restituisce righe tipo `{"_id": "In Viaggio", "count": 30}`. La
  **dict comprehension** le trasforma in `{"In Viaggio": 30, ...}`.
- **115–120** compone il riepilogo: `total` (somma di tutti), `ready` (somma di due stati),
  `in_transit`, `in_preparation`. `counts.get(..., 0)` mette 0 se quello stato non esiste.

---

## `seller_leaderboard()` — classifica venditori (righe 123–133)

```python
def seller_leaderboard():
    # Classifica venditori: raggruppa per venditore, conta le auto ($group +
    # $sum) e ordina dal piu' attivo ($sort).
    pipeline = [
        {"$group": {"_id": "$venditore", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    return [
        {"seller": row["_id"], "count": row["count"]}
        for row in collection.aggregate(pipeline)
    ]
```

Conta quante auto sono assegnate a ciascun venditore, ordinate dal più attivo. Alimenta la card
"Auto gestite per venditore" nella home. Usa gli stessi strumenti di `dashboard_summary` (`$group` +
`$sum`), con in più uno stadio `$sort`.

- **126–129** la pipeline ha due stadi:
  - `{"$group": {"_id": "$venditore", "count": {"$sum": 1}}}` → un gruppo per ogni venditore diverso;
    `$sum: 1` conta le auto di ciascuno.
  - `{"$sort": {"count": -1}}` → ordina i gruppi per conteggio **decrescente** (`-1`), così il più
    attivo è in cima.
- **130–133** trasforma le righe (tipo `{"_id": "Sofia Verdi", "count": 267}`) in dizionari più
  leggibili `{"seller": "...", "count": ...}`, pronti per il template.

> Nella home il template disegna una barra proporzionale: la larghezza di ogni riga è
> `count / count_del_primo * 100`, quindi il primo venditore è al 100% e gli altri in proporzione.

---

## `featured_vehicles(limit=3)` — le auto in evidenza (righe 136–141)

```python
def featured_vehicles(limit=3):
    # Le auto con l'ultimo aggiornamento piu' recente: prendo tutti i veicoli
    # e li ordino per data dell'ultimo evento, tenendo solo i primi.
    vehicles = list_vehicles()
    vehicles.sort(key=lambda vehicle: vehicle["arrival_date_raw"] or datetime.min, reverse=True)
    return vehicles[:limit]
```

Restituisce le `limit` auto con l'ultimo aggiornamento di timeline **più recente** (le "novità").

- **139** carica **tutti** i veicoli normalizzati.
- **140** li ordina per `arrival_date_raw` (la data grezza dell'ultimo evento):
  - se è `None` (nessun evento) usa `datetime.min` (la data più antica possibile), così le auto senza
    timeline finiscono **in fondo** invece di causare un errore nel confronto.
  - `reverse=True` = ordine **decrescente** (dalla più recente).
- **141** restituisce solo i primi `limit` (default 3).

---

## `build_filter_options(vehicles)` — opzioni per i menu a tendina (righe 144–150)

```python
def build_filter_options(vehicles):
    # Valori unici (senza duplicati) per riempire i menu a tendina dei filtri.
    return {
        "statuses": sorted({vehicle["status"] for vehicle in vehicles}),
        "brands": sorted({vehicle["brand"] for vehicle in vehicles}),
        "trims": sorted({vehicle["trim"] for vehicle in vehicles if vehicle["trim"] != "N/D"}),
    }
```

Data una lista di veicoli **già normalizzati**, ricava i valori **unici** per popolare i filtri.

- **147** `statuses`: insieme degli `status` distinti, ordinati. Le graffe `{...}` creano un **set**
  (set comprehension): elimina i duplicati. `sorted(...)` lo ordina e restituisce una lista.
- **148** `brands`: stessa cosa per le marche.
- **149** `trims`: stessa cosa per gli allestimenti, ma escludendo `"N/D"` (non ha senso metterlo tra
  le opzioni).

---

## `build_calendar_events(vehicles)` — eventi per il calendario (righe 153–180)

```python
def build_calendar_events(vehicles):
    # Trasforma i veicoli in eventi per il calendario del frontend.
    colori_stato = {
        "Pronta per la consegna": "#5ee0a0",
        "Arrivato in Concessionaria": "#4f8cff",
        "In Viaggio": "#ffb347",
        "Ordinato in Fabbrica": "#8e9cff",
    }
    events = []
    for vehicle in vehicles:
        if not vehicle["arrival_date_iso"]:
            continue
        events.append(
            {
                "title": f'{vehicle["brand"]} {vehicle["modello"]}',
                "start": vehicle["arrival_date_iso"],
                "vehicleId": vehicle["id"],
                "backgroundColor": colori_stato.get(vehicle["status"], "#9eb2cf"),
                "borderColor": "#ffffff22",
                "extendedProps": {
                    "status": vehicle["status"],
                    "vin": vehicle["vin"],
                    "trim": vehicle["trim"],
                    "dateLabel": vehicle["arrival_date"],
                },
            }
        )
    return events
```

Trasforma i veicoli in **eventi per FullCalendar** (la libreria calendario JavaScript del frontend).

- **155–160** `colori_stato`: una mappa "stato → colore", tirata fuori dal ciclo così è scritta una
  volta sola.
- **161** lista vuota da riempire.
- **162–164** cicla su ogni veicolo; se **non ha** una data ISO valida, lo **salta** (`continue`):
  senza data non può stare sul calendario.
- **165–178** costruisce l'evento:
  - `title`: testo mostrato, es. `"Renault Clio"`.
  - `start`: data di inizio in formato ISO (quella che FullCalendar richiede).
  - `vehicleId`: l'id, per linkare l'evento alla scheda.
  - `backgroundColor`: colore in base allo **stato** (`colori_stato.get(..., "#9eb2cf")`: colore
    giusto o un grigio-azzurro di default).
  - `borderColor`: `#ffffff22` = bianco con trasparenza (`22` = canale alpha esadecimale).
  - `extendedProps`: dati "extra" che FullCalendar conserva e che il JS legge (`status`, `vin`,
    `trim`, `dateLabel`). **Nota:** `dateLabel` sta qui dentro, così in `app.js` l'accesso
    `arg.event.extendedProps.dateLabel` è letteralmente corretto.
- **180** restituisce la lista completa di eventi.

---

## Mappa: chi chiama cosa (collegamento con `app.py`)

| Funzione del repository            | Usata in `app.py` per...                                   |
|------------------------------------|------------------------------------------------------------|
| `dashboard_summary`                | numeri delle card in home (`/`)                            |
| `seller_leaderboard`               | classifica venditori in home (`/`)                         |
| `featured_vehicles`                | auto in evidenza in home (`/`)                             |
| `list_vehicles`                    | gestione auto, catalogo, veicoli correlati                 |
| `build_filter_options`             | popolare i dropdown dei filtri                             |
| `build_calendar_events`            | eventi del calendario in "Gestione auto"                   |
| `get_vehicle_by_id`                | pagina di dettaglio auto (vista)                           |
| `get_vehicle_document_by_id`       | leggere il documento grezzo per il form di modifica        |
| `upsert_vehicle_document`          | salvare/creare un'auto (POST)                              |
| `delete_vehicle_document`          | cancellare un'auto                                         |

> `collection` è importata anche da `datagenerator.py` per popolare il database.

## Concetti chiave da ricordare

1. **Traduzione italiano ⇄ inglese**: il DB parla italiano, i template parlano inglese;
   `normalize_vehicle` è il ponte, e calcola anche i campi che nel DB non esistono.
2. **Due letture, un motivo**: versione normalizzata (per mostrare) vs grezza (per modificare).
3. **`.get(chiave, default)` ovunque**: rende il codice a prova di campi mancanti.
4. **Id o VIN**: le funzioni "per id" accettano sia l'ObjectId sia il numero di telaio.
5. **Una connessione sola**: `collection` è creata una volta a livello di modulo, e la riusano anche
   gli script di popolamento.
6. **Le operazioni MongoDB**: `find` (list_vehicles), `find_one` (get_..._by_id),
   `insert_one`/`update_one` (upsert), `delete_one` (delete), `aggregate` con `$group`+`$sum`
   (dashboard_summary, seller_leaderboard).
