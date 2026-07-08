# Spiegazione di `mongo_repository.py` (riga per riga)

Questo file è il **livello di accesso ai dati** (data access layer / repository) dell'applicazione
Flask `Car-Delivery-Dashboard`. Tutto ciò che riguarda MongoDB — connessione, lettura, scrittura,
cancellazione e "normalizzazione" dei documenti — vive qui. Il resto dell'app (`app.py`) non parla
mai direttamente con MongoDB: chiama le funzioni di questo file.

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

Nota importante sui **nomi in due lingue**: nel database i campi sono in **italiano**
(`marca`, `stato_attuale`, `configurazione`...). Le funzioni di questo file traducono questi
documenti in dizionari con chiavi in **inglese** (`brand`, `status`, `trim`...) che i template
HTML usano. Questa traduzione è il cuore di `normalize_vehicle`.

---

## Import e configurazione (righe 1–14)

```python
from __future__ import annotations
```
**Riga 1.** Permette di usare le annotazioni di tipo "moderne" (es. `str | None`, `list[dict]`)
anche su versioni di Python in cui non sarebbero ancora native, perché rende tutte le annotazioni
"stringhe" valutate solo se serve. In pratica: fa funzionare i type hint scritti sotto senza errori.

```python
import os
from datetime import date, datetime
from functools import lru_cache
from typing import Any
```
**Righe 3–6.**
- `os` → per leggere le variabili d'ambiente (URI del database, ecc.).
- `date, datetime` → tipi per gestire le date della timeline.
- `lru_cache` → decoratore di cache; qui serve a creare la connessione a Mongo **una sola volta**.
- `Any` → tipo generico "qualsiasi cosa", usato nei type hint.

```python
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, MongoClient
```
**Righe 8–9.**
- `ObjectId` → la classe dell'`_id` di MongoDB. Serve a convertire una stringa (es. `"665f..."`)
  nell'oggetto ID vero e proprio per fare query per `_id`.
- `MongoClient` → il client con cui ci si connette al server MongoDB.
- `ASCENDING`, `DESCENDING` → costanti (`1` e `-1`) per indicare l'ordine di ordinamento nelle query.
  `DESCENDING` è importato ma **non usato** nel file (import "di troppo").

```python
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "db_veicoli")
MONGO_COLLECTION_NAME = os.getenv("MONGO_COLLECTION_NAME", "vehicles")
```
**Righe 12–14.** Configurazione. `os.getenv("NOME", "default")` legge una variabile d'ambiente e,
se non esiste, usa il valore di default. Così puoi cambiare database/collezione (es. in produzione)
senza toccare il codice, ma in locale funziona subito con i default:
- database `db_veicoli`, collezione `vehicles`, server locale sulla porta `27017`.

---

## `get_collection()` — la connessione (righe 17–20)

```python
@lru_cache(maxsize=1)
def get_collection():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    return client[MONGO_DB_NAME][MONGO_COLLECTION_NAME]
```

- **Riga 17** `@lru_cache(maxsize=1)`: memorizza il risultato della funzione. Poiché non ci sono
  argomenti, la funzione viene eseguita **davvero solo la prima volta**; da lì in poi restituisce
  sempre lo stesso oggetto memorizzato. È il modo (semplice) per avere un'**unica connessione
  condivisa** invece di aprirne una nuova a ogni chiamata.
- **Riga 19** crea il client. `serverSelectionTimeoutMS=3000` = se in 3 secondi non trova un server
  MongoDB, lancia un errore invece di restare bloccato all'infinito.
- **Riga 20** `client[MONGO_DB_NAME][MONGO_COLLECTION_NAME]` = seleziona il database e poi la
  collezione, e restituisce l'oggetto **collezione** su cui poi si fanno `find`, `insert_one`, ecc.

> In sintesi: questa è "la porta d'ingresso" al database. Tutte le altre funzioni chiamano
> `get_collection()` per ottenere la collezione su cui lavorare.

---

## `format_date(value)` — formattare una data per l'utente (righe 23–32)

```python
def format_date(value: Any) -> str:
    if value is None:
        return "N/D"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, str):
        return value[:10]
    return str(value)
```

Trasforma "qualsiasi" tipo di data nella stringa leggibile `giorno/mese/anno`. È robusta perché
i dati possono arrivare in formati diversi.

- **24–25** se il valore è `None` (assente) → restituisce `"N/D"` (Non Disponibile).
- **26–27** se è un `datetime` (data + ora) → lo formatta come `08/07/2026`.
- **28–29** se è un `date` (solo data) → stesso formato `08/07/2026`.
- **30–31** se è già una stringa → prende i **primi 10 caratteri** (es. da `"2026-07-08T10:00"`
  ottiene `"2026-07-08"`). Non riformatta, taglia soltanto.
- **32** qualsiasi altro caso → lo converte a stringa e basta (fallback di sicurezza).

Questa funzione è anche esposta ai template HTML (vedi `app.py`, `inject_helpers`), quindi si può
usare direttamente dentro l'HTML.

---

## `_iso_date(value)` — data in formato ISO per calendario/JS (righe 35–44)

```python
def _iso_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value[:10]
    return None
```

Molto simile a `format_date`, ma produce il formato **ISO `AAAA-MM-GG`** (es. `2026-07-08`), che è
quello richiesto dalla libreria calendario nel frontend (FullCalendar).

- Il prefisso `_` nel nome (`_iso_date`) è la convenzione Python per dire "**funzione privata/interna**",
  usata solo dentro questo file.
- **36–37** `None` → `None` (nessuna data).
- **38–39** `datetime` → `.date()` toglie l'ora, `.isoformat()` produce `2026-07-08`.
- **40–41** `date` → direttamente `.isoformat()`.
- **42–43** stringa → primi 10 caratteri.
- **44** altro → `None`.

Differenza chiave con `format_date`: qui il caso "sconosciuto" restituisce `None` (non una stringa),
perché a valle serve poter dire "non c'è una data valida" e saltare l'evento nel calendario.

---

## `_timeline_date(entry)` — data dell'ultimo evento (righe 47–50)

```python
def _timeline_date(entry: dict[str, Any] | None) -> str:
    if not entry:
        return "N/D"
    return format_date(entry.get("data"))
```

Riceve **un singolo evento** della timeline (un dizionario tipo
`{"stato": ..., "data": ..., "operatore": ...}`) e ne restituisce la data formattata.

- **48–49** se `entry` è `None` o vuoto → `"N/D"`.
- **50** altrimenti estrae il campo `data` con `entry.get("data")` (che restituisce `None` se manca,
  senza errori) e lo passa a `format_date`.

---

## `_normalize_timeline(entries)` — tradurre la timeline (righe 53–63)

```python
def _normalize_timeline(entries: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized = []
    for entry in entries or []:
        normalized.append(
            {
                "status": entry.get("stato", ""),
                "date": format_date(entry.get("data")),
                "operator": entry.get("operatore", ""),
            }
        )
    return normalized
```

Prende la lista di eventi in **italiano** (`stato`, `data`, `operatore`) e la ritraduce in
**inglese** (`status`, `date`, `operator`) con la data già formattata, pronta per i template.

- **54** parte da una lista vuota che riempirà.
- **55** `for entry in entries or []`: il trucco `entries or []` evita l'errore se `entries` è `None`
  — in quel caso itera su una lista vuota (zero giri).
- **56–62** per ogni evento crea un nuovo dizionario tradotto. `entry.get("stato", "")` significa
  "prendi `stato`, o stringa vuota se manca" → così non si rompe mai per campi assenti.
- **63** restituisce la lista tradotta.

---

## `_timeline_sort_key(vehicle)` — chiave di ordinamento (righe 66–67)

```python
def _timeline_sort_key(vehicle: dict[str, Any]) -> str:
    return vehicle.get("arrival_date_raw") or vehicle.get("arrival_date") or ""
```

Restituisce un valore da usare per **ordinare** i veicoli per data di arrivo.

- Prova prima `arrival_date_raw` (la data "grezza", cioè l'oggetto `datetime` originale);
  se manca usa `arrival_date` (la stringa formattata); se manca anche quella usa `""`.
- Il pattern `a or b or c` restituisce il primo valore "vero" (non `None`, non vuoto).

> ⚠️ Nota tecnica: questa funzione **non viene chiamata da nessuna parte** nel file (né in `app.py`).
> È codice "morto"/di riserva. L'ordinamento vero avviene con altre chiavi (vedi `featured_vehicles`).

---

## `normalize_vehicle(document)` — la funzione centrale (righe 70–98)

È la funzione più importante: prende **un documento MongoDB grezzo** (in italiano, annidato) e lo
appiattisce/traduce in un **dizionario "pulito"** che i template HTML sanno usare.

```python
def normalize_vehicle(document: dict[str, Any]) -> dict[str, Any]:
    config = document.get("configurazione") or {}
    customer = document.get("assegnato_a_cliente") or {}
    timeline = document.get("logistica_timeline") or []
    last_step = timeline[-1] if timeline else None
```

- **71** estrae il sotto-dizionario `configurazione`; se manca usa `{}` (dizionario vuoto), così le
  `.get()` successive non esplodono.
- **72** stessa cosa per il cliente assegnato.
- **73** stessa cosa per la timeline (lista vuota se assente).
- **74** `last_step` = **l'ultimo evento** della timeline (`timeline[-1]` = ultimo elemento). Se la
  timeline è vuota → `None`. L'ultimo evento rappresenta lo "stato logistico più recente" ed è la
  base per calcolare la data di arrivo.

```python
    return {
        "id": str(document.get("_id")),
        "vin": document.get("vin_telaio", ""),
        "brand": document.get("marca", ""),
        "modello": document.get("modello", ""),
        "status": document.get("stato_attuale", ""),
        "seller": document.get("venditore", ""),
```

Il dizionario di ritorno (traduzione italiano → inglese):
- **76** `id`: l'`_id` di Mongo convertito in **stringa** con `str(...)` (perché `ObjectId` non è
  serializzabile direttamente e negli URL serve una stringa).
- **77** `vin` ← `vin_telaio`.
- **78** `brand` ← `marca`.
- **79** `modello` (resta uguale).
- **80** `status` ← `stato_attuale`.
- **81** `seller` ← `venditore`.

```python
        "customer_name": customer.get("nome", ""),
        "customer_email": customer.get("email", ""),
        "customer_phone": customer.get("numero_telefono", ""),
```
- **82–84** dati del cliente, presi dal sotto-dizionario `customer` estratto prima.

```python
        "trim": config.get("allestimento", "N/D"),
        "motorizzazione": config.get("motorizzazione", "N/D"),
        "color": config.get("colore_esterno", "N/D"),
        "included_packages": config.get("pacchetti_inclusi", []),
        "extra_packages": config.get("pacchetti_aggiuntivi", []),
        "battery_kwh": config.get("capacita_batteria_kw"),
        "charging_cable": config.get("cavo_ricarica_incluso"),
```
- **85–91** dati di configurazione:
  - `trim` ← `allestimento` (default `"N/D"`).
  - `motorizzazione`, `color` ← `colore_esterno` (default `"N/D"`).
  - `included_packages`, `extra_packages`: liste (default `[]`).
  - `battery_kwh`, `charging_cable`: **senza default**, quindi valgono `None` se assenti. Questo è
    voluto: sono campi presenti **solo sulle auto elettriche** (vedi il "Polymorphic Pattern" in
    `datagenerator.py`), quindi `None` significa "auto non elettrica / dato non applicabile".

```python
        "timeline": _normalize_timeline(timeline),
        "timeline_count": len(timeline),
        "arrival_date": _timeline_date(last_step),
        "arrival_date_iso": _iso_date(last_step.get("data") if last_step else None),
        "arrival_date_raw": last_step.get("data") if last_step else None,
        "public": document.get("stato_attuale") != "In Preparazione",
    }
```
- **92** `timeline`: la timeline tradotta (chiama `_normalize_timeline`).
- **93** `timeline_count`: quanti eventi ci sono (`len`).
- **94** `arrival_date`: data dell'ultimo evento **formattata** `gg/mm/aaaa` (via `_timeline_date`).
- **95** `arrival_date_iso`: la stessa data in formato ISO per il calendario.
  `last_step.get("data") if last_step else None` = prendi la data dell'ultimo evento, ma solo se
  esiste un ultimo evento (altrimenti `None`, per non chiamare `.get` su `None` → errore).
- **96** `arrival_date_raw`: la data **grezza** (oggetto `datetime` originale), utile per ordinare
  correttamente (confrontare datetime è più affidabile che confrontare stringhe formattate).
- **97** `public`: campo booleano calcolato. È `True` per tutte le auto **tranne** quelle
  `"In Preparazione"`. Serve a decidere cosa mostrare nel catalogo pubblico: un'auto ancora in
  preparazione non deve comparire ai clienti.

> Riassunto: `normalize_vehicle` è il "traduttore universale". Ogni volta che leggi un veicolo dal
> DB per mostrarlo, passa da qui.

---

## `_vehicle_query(query, public_only)` — costruire i criteri di filtro (righe 101–105)

```python
def _vehicle_query(query: dict[str, Any] | None = None, public_only: bool = False) -> dict[str, Any]:
    criteria: dict[str, Any] = dict(query or {})
    if public_only:
        criteria["stato_attuale"] = {"$ne": "In Preparazione"}
    return criteria
```

Costruisce il dizionario di **filtro** (in gergo Mongo: il "query filter") da passare a `find()`.

- **102** `dict(query or {})`: parte dal filtro ricevuto, oppure da un dizionario vuoto. Usa `dict(...)`
  per farne una **copia**, così non modifica il dizionario originale del chiamante (buona pratica).
- **103–104** se `public_only=True` aggiunge la condizione `stato_attuale != "In Preparazione"`.
  `{"$ne": ...}` è l'operatore MongoDB "**not equal**" (diverso da).
- **105** restituisce i criteri. Esempio di risultato: `{"marca": "Renault", "stato_attuale": {"$ne": "In Preparazione"}}`.

---

## `list_vehicles(...)` — elenco veicoli (righe 108–126)

```python
def list_vehicles(
    query: dict[str, Any] | None = None,
    public_only: bool = False,
    limit: int | None = None,
    exclude_id: str | None = None,
) -> list[dict[str, Any]]:
```
**108–113** La funzione più usata: restituisce una lista di veicoli **normalizzati**. Parametri:
- `query`: filtri extra (es. `{"marca": "Renault"}`).
- `public_only`: se `True`, esclude le auto in preparazione (per il catalogo).
- `limit`: numero massimo di risultati.
- `exclude_id`: un ID da **escludere** (usato per "veicoli correlati", per non mostrare l'auto stessa).

```python
    criteria = _vehicle_query(query=query, public_only=public_only)
    if exclude_id:
        criteria["_id"] = {"$ne": ObjectId(exclude_id)}
```
- **114** costruisce i criteri base con la funzione vista sopra.
- **115–116** se è stato passato `exclude_id`, aggiunge la condizione "`_id` diverso da questo ID".
  Nota `ObjectId(exclude_id)`: la stringa va riconvertita in `ObjectId` per confrontarla col DB.

```python
    documents = list(
        get_collection()
        .find(criteria)
        .sort([("marca", ASCENDING), ("modello", ASCENDING), ("vin_telaio", ASCENDING)])
    )
```
- **117–121** esegue la query:
  - `get_collection().find(criteria)` → trova tutti i documenti che rispettano i criteri.
  - `.sort([...])` → ordina lato database per marca, poi modello, poi VIN, tutti crescenti.
  - `list(...)` → forza l'esecuzione della query e mette i risultati in una lista Python.

```python
    vehicles = [normalize_vehicle(document) for document in documents]
    vehicles.sort(key=lambda vehicle: (vehicle["brand"], vehicle["modello"], vehicle["vin"]))
```
- **122** normalizza **ogni** documento (list comprehension) → lista di dizionari puliti.
- **123** riordina **di nuovo**, stavolta lato Python, sulle chiavi tradotte (`brand`, `modello`, `vin`).
  È in parte ridondante col `.sort()` del DB, ma garantisce l'ordine finale sui campi normalizzati.

```python
    if limit is not None:
        return vehicles[:limit]
    return vehicles
```
- **124–126** se è stato indicato un `limit`, restituisce solo i primi `limit` elementi
  (`vehicles[:limit]`); altrimenti tutta la lista.

---

## `get_vehicle_by_id(vehicle_id)` — un veicolo normalizzato (righe 129–136)

```python
def get_vehicle_by_id(vehicle_id: str) -> dict[str, Any] | None:
    collection = get_collection()
    document = None
    if ObjectId.is_valid(vehicle_id):
        document = collection.find_one({"_id": ObjectId(vehicle_id)})
    if document is None:
        document = collection.find_one({"vin_telaio": vehicle_id})
    return normalize_vehicle(document) if document else None
```

Cerca **un solo** veicolo e lo restituisce **normalizzato** (pronto per la vista di dettaglio).
La particolarità: accetta sia un `_id` di Mongo sia un VIN.

- **130** ottiene la collezione.
- **131** parte da `document = None`.
- **132–133** se `vehicle_id` **ha la forma** di un ObjectId valido (`ObjectId.is_valid` controlla
  senza lanciare eccezioni), prova a cercarlo per `_id`.
- **134–135** se non ha trovato nulla (o l'id non era un ObjectId), prova a cercarlo per `vin_telaio`.
  Questo rende gli URL flessibili: `/auto/<id>` funziona sia con l'ID che col numero di telaio.
- **136** se ha trovato un documento lo normalizza, altrimenti restituisce `None` (→ l'app farà 404).

---

## `get_vehicle_document_by_id(vehicle_id)` — il documento GREZZO (righe 139–146)

```python
def get_vehicle_document_by_id(vehicle_id: str) -> dict[str, Any] | None:
    collection = get_collection()
    document = None
    if ObjectId.is_valid(vehicle_id):
        document = collection.find_one({"_id": ObjectId(vehicle_id)})
    if document is None:
        document = collection.find_one({"vin_telaio": vehicle_id})
    return document
```

**Identica** alla precedente, con **una** differenza cruciale alla fine:
- **146** restituisce il documento **grezzo** (in italiano, com'è nel DB), **senza** normalizzarlo.

**Perché esistono due versioni?**
- `get_vehicle_by_id` (normalizzato) serve per **mostrare** i dati (i template vogliono `brand`, `status`...).
- `get_vehicle_document_by_id` (grezzo) serve per **modificare** i dati: in `app.py`, prima di un
  update, serve il documento originale (con `logistica_timeline` intatta e i nomi italiani) per
  aggiungere un nuovo evento alla timeline senza perdere lo storico.

---

## `upsert_vehicle_document(document, vehicle_id)` — inserire o aggiornare (righe 149–155)

"Upsert" = **UP**date + in**SERT**: aggiorna se esiste, altrimenti crea.

```python
def upsert_vehicle_document(document: dict[str, Any], vehicle_id: str | None = None) -> str:
    collection = get_collection()
    if vehicle_id and ObjectId.is_valid(vehicle_id):
        collection.update_one({"_id": ObjectId(vehicle_id)}, {"$set": document})
        return vehicle_id
    result = collection.insert_one(document)
    return str(result.inserted_id)
```

- **150** ottiene la collezione.
- **151** se è stato passato un `vehicle_id` **ed** è un ObjectId valido → è un **aggiornamento**.
- **152** `update_one(filtro, aggiornamento)`:
  - filtro `{"_id": ObjectId(vehicle_id)}` = "il documento con questo id".
  - `{"$set": document}` = sovrascrive i campi con quelli del nuovo documento. `$set` è l'operatore
    MongoDB che imposta/aggiorna i campi indicati.
- **153** restituisce lo stesso `vehicle_id` (l'id non cambia in un update).
- **154** se non c'era un id valido → è un **inserimento**: `insert_one` crea un nuovo documento.
- **155** restituisce il nuovo `_id` generato da Mongo, convertito in stringa (usato per fare il
  redirect alla pagina della nuova auto).

---

## `delete_vehicle_document(vehicle_id)` — cancellare (righe 158–164)

```python
def delete_vehicle_document(vehicle_id: str) -> bool:
    collection = get_collection()
    if ObjectId.is_valid(vehicle_id):
        result = collection.delete_one({"_id": ObjectId(vehicle_id)})
        return result.deleted_count > 0
    result = collection.delete_one({"vin_telaio": vehicle_id})
    return result.deleted_count > 0
```

Cancella un veicolo e restituisce `True`/`False` a seconda che qualcosa sia stato davvero cancellato.

- **160–162** se l'id è un ObjectId valido → cancella per `_id`. `result.deleted_count` è quanti
  documenti sono stati eliminati (0 o 1 con `delete_one`); `> 0` lo trasforma in booleano.
- **163–164** altrimenti tenta la cancellazione per `vin_telaio`.

Stesso pattern "id o VIN" delle funzioni di lettura, per coerenza.

---

## `dashboard_summary()` — i numeri della home (righe 167–180)

```python
def dashboard_summary() -> dict[str, int]:
    # Raggruppa i veicoli per stato e conta quanti ce ne sono in ciascuno.
    # Stesso schema visto a lezione: $group con _id su un campo + accumulatore $sum.
    pipeline = [
        {"$group": {"_id": "$stato_attuale", "count": {"$sum": 1}}},
    ]
    counts = {row["_id"]: row["count"] for row in get_collection().aggregate(pipeline)}
```

Calcola le statistiche mostrate in homepage usando una **aggregation pipeline** di MongoDB (più
efficiente che scaricare tutti i documenti e contarli in Python).

- **170–172** la pipeline ha un solo stadio: `$group`.
  - `"_id": "$stato_attuale"` = raggruppa i documenti per valore del campo `stato_attuale`.
    (Il `$` davanti significa "il valore del campo", non la stringa letterale.)
  - `"count": {"$sum": 1}` = per ogni gruppo somma `1` a ogni documento → cioè li conta.
- **173** `.aggregate(pipeline)` esegue la pipeline e restituisce righe tipo
  `{"_id": "In Viaggio", "count": 30}`. La **dict comprehension** le trasforma in un dizionario
  comodo: `{"In Viaggio": 30, "In Preparazione": 12, ...}`.

```python
    return {
        "total": sum(counts.values()),
        "ready": counts.get("Pronta per la consegna", 0) + counts.get("Arrivato in Concessionaria", 0),
        "in_transit": counts.get("In Viaggio", 0),
        "in_preparation": counts.get("In Preparazione", 0),
    }
```
- **175–180** compone il riepilogo finale:
  - `total`: somma di tutti i conteggi = numero totale di veicoli.
  - `ready`: veicoli "pronti", cioè la somma di due stati ("Pronta per la consegna" +
    "Arrivato in Concessionaria"). `counts.get(..., 0)` mette 0 se quello stato non esiste.
  - `in_transit`: veicoli "In Viaggio".
  - `in_preparation`: veicoli "In Preparazione".

Questi quattro numeri finiscono nelle card della home (`app.py`, funzione `home`).

---

## `featured_vehicles(limit=3)` — le auto in evidenza (righe 183–192)

```python
def featured_vehicles(limit: int = 3) -> list[dict[str, Any]]:
    # Le auto con l'evento di timeline piu' recente: recupero tutti i veicoli con
    # find() e li ordino in Python sulla data dell'ultimo evento (gia' calcolata
    # in normalize_vehicle), tenendo solo i primi.
    vehicles = list_vehicles()
    vehicles.sort(
        key=lambda vehicle: vehicle["arrival_date_raw"] or datetime.min,
        reverse=True,
    )
    return vehicles[:limit]
```

Restituisce le `limit` auto con l'ultimo aggiornamento di timeline **più recente** (le "novità").

- **187** carica **tutti** i veicoli normalizzati.
- **188–191** li ordina per `arrival_date_raw` (la data grezza dell'ultimo evento):
  - `key=lambda vehicle: vehicle["arrival_date_raw"] or datetime.min` = usa quella data come chiave;
    se è `None` (nessun evento) usa `datetime.min` (la data più antica possibile), così le auto senza
    timeline finiscono **in fondo** invece di causare un errore nel confronto.
  - `reverse=True` = ordine **decrescente** (dalla più recente alla più vecchia).
- **192** restituisce solo i primi `limit` (default 3).

---

## `build_filter_options(vehicles)` — opzioni per i menu a tendina (righe 195–200)

```python
def build_filter_options(vehicles: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        "statuses": sorted({vehicle["status"] for vehicle in vehicles}),
        "brands": sorted({vehicle["brand"] for vehicle in vehicles}),
        "trims": sorted({vehicle["trim"] for vehicle in vehicles if vehicle["trim"] != "N/D"}),
    }
```

Data una lista di veicoli **già normalizzati**, ricava i valori **unici** per popolare i filtri
(dropdown) nelle pagine catalogo/gestione.

- **197** `statuses`: insieme di tutti gli `status` distinti, ordinati. Le graffe `{...}` qui creano
  un **set** (set comprehension): elimina automaticamente i duplicati. `sorted(...)` lo ordina
  alfabeticamente restituendo una lista.
- **198** `brands`: stessa cosa per le marche.
- **199** `trims`: stessa cosa per gli allestimenti, ma con un **filtro**: `if vehicle["trim"] != "N/D"`
  esclude gli allestimenti sconosciuti (non ha senso mettere "N/D" tra le opzioni selezionabili).

---

## `build_calendar_events(vehicles)` — eventi per il calendario (righe 203–228)

```python
def build_calendar_events(vehicles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    for vehicle in vehicles:
        if not vehicle["arrival_date_iso"]:
            continue
```

Trasforma i veicoli in **eventi per FullCalendar** (la libreria calendario JavaScript del frontend).

- **204** lista vuota da riempire.
- **205** cicla su ogni veicolo.
- **206–207** se il veicolo **non ha** una data ISO valida (`arrival_date_iso` è `None`/vuoto),
  lo **salta** (`continue`): senza data non può stare sul calendario.

```python
        events.append(
            {
                "title": f'{vehicle["brand"]} {vehicle["modello"]}',
                "start": vehicle["arrival_date_iso"],
                "dateLabel": vehicle["arrival_date"],
                "vehicleId": vehicle["id"],
```
- **208–213** costruisce l'evento:
  - `title`: testo mostrato, es. `"Renault Clio"` (f-string che unisce marca e modello).
  - `start`: data di inizio evento in formato ISO (quella che FullCalendar richiede).
  - `dateLabel`: la data "bella" `gg/mm/aaaa` da mostrare nei tooltip.
  - `vehicleId`: l'id, per poter linkare l'evento alla pagina di dettaglio.

```python
                "backgroundColor": {
                    "Pronta per la consegna": "#5ee0a0",
                    "Arrivato in Concessionaria": "#4f8cff",
                    "In Viaggio": "#ffb347",
                    "Ordinato in Fabbrica": "#8e9cff",
                }.get(vehicle["status"], "#9eb2cf"),
                "borderColor": "#ffffff22",
```
- **214–220** `backgroundColor`: colore dell'evento in base allo **stato**. È un dizionario
  "stato → colore" su cui si chiama `.get(vehicle["status"], "#9eb2cf")`: prende il colore giusto,
  oppure un grigio-azzurro di default `#9eb2cf` se lo stato non è tra quelli elencati (es. "In Preparazione").
- **220** `borderColor`: `#ffffff22` = bianco con trasparenza (gli ultimi due caratteri `22` sono
  il canale alpha in esadecimale → bordo tenue).

```python
                "extendedProps": {
                    "status": vehicle["status"],
                    "vin": vehicle["vin"],
                    "trim": vehicle["trim"],
                },
            }
        )
    return events
```
- **221–225** `extendedProps`: dati "extra" che FullCalendar conserva sull'evento e che il JS può
  leggere (es. per mostrare stato, VIN e allestimento in un popup al click).
- **228** restituisce la lista completa di eventi.

---

## Mappa: chi chiama cosa (collegamento con `app.py`)

| Funzione del repository            | Usata in `app.py` per...                                   |
|------------------------------------|------------------------------------------------------------|
| `dashboard_summary`                | numeri delle card in home (`/`)                            |
| `featured_vehicles`                | auto in evidenza in home (`/`)                             |
| `list_vehicles`                    | gestione auto, catalogo, veicoli correlati                 |
| `build_filter_options`             | popolare i dropdown dei filtri                             |
| `build_calendar_events`            | eventi del calendario in "Gestione auto"                   |
| `get_vehicle_by_id`                | pagina di dettaglio auto (vista)                           |
| `get_vehicle_document_by_id`       | leggere il documento grezzo prima di un update             |
| `upsert_vehicle_document`          | salvare/creare un'auto (POST)                              |
| `delete_vehicle_document`          | cancellare un'auto                                         |
| `format_date`                      | esposta ai template come helper                            |

## Concetti chiave da ricordare

1. **Traduzione italiano ⇄ inglese**: il DB parla italiano, i template parlano inglese;
   `normalize_vehicle` è il ponte.
2. **Due letture, un motivo**: versione normalizzata (per mostrare) vs grezza (per modificare).
3. **`.get(chiave, default)` ovunque**: rende il codice a prova di campi mancanti.
4. **Id o VIN**: quasi tutte le funzioni "per id" accettano sia l'ObjectId sia il numero di telaio.
5. **Connessione unica**: `@lru_cache` su `get_collection()` evita di riaprire la connessione.
6. **Aggregation vs Python**: i conteggi (`dashboard_summary`) sfruttano `$group` lato DB;
   ordinamenti fini e filtri di presentazione avvengono lato Python.
