# Spiegazione di `app.py` (riga per riga)

`app.py` è il **cuore dell'applicazione web Flask**. Il suo compito è:

1. ricevere le richieste HTTP del browser (le **rotte**, es. `/`, `/catalogo`, `/auto/<id>`),
2. chiedere i dati a `mongo_repository.py` (che parla con MongoDB),
3. costruire/leggere i documenti dei form,
4. passare tutto ai **template HTML** (Jinja) che disegnano la pagina.

> Regola d'oro dell'architettura: `app.py` **non parla mai direttamente con MongoDB**. Chiama le
> funzioni di `mongo_repository.py`. Qui dentro c'è la "logica web", là c'è la "logica database".
> Le query MongoDB sono spiegate una per una in [`query_mongodb.md`](query_mongodb.md).

---

## Import (righe 1–16)

```python
from datetime import datetime

from flask import Flask, abort, redirect, render_template, request, url_for
```
**Righe 1–3.**
- `datetime` → serve per mettere la data/ora sugli eventi della timeline quando si salva un'auto.
- Da `flask` importa gli strumenti che useremo:
  - `Flask` → la classe dell'applicazione.
  - `abort` → interrompe con un errore HTTP (es. `abort(404)` = "pagina non trovata").
  - `redirect` → rimanda il browser a un altro URL.
  - `render_template` → prende un file HTML e lo riempie con i dati.
  - `request` → contiene i dati della richiesta in arrivo (es. i campi di un form).
  - `url_for` → costruisce l'URL di una rotta dal suo nome (es. `url_for("home")` → `/`).

```python
from mongo_repository import (
    build_calendar_events,
    build_filter_options,
    dashboard_summary,
    delete_vehicle_document,
    featured_vehicles,
    get_vehicle_document_by_id,
    get_vehicle_by_id,
    list_vehicles,
    seller_leaderboard,
    upsert_vehicle_document,
)
```
**Righe 5–16.** Importa dal repository **tutte le funzioni di accesso ai dati** che useremo nelle
rotte. Ognuna è spiegata in dettaglio in [`SPIEGAZIONE_mongo_repository.md`](SPIEGAZIONE_mongo_repository.md).

---

## Creazione dell'app (riga 19)

```python
app = Flask(__name__)
```
Crea l'oggetto applicazione Flask. `__name__` dice a Flask dove si trova il file, così sa trovare le
cartelle `templates/` (gli HTML) e `static/` (CSS e JavaScript). Da qui in poi, `@app.route(...)`
serve a collegare un URL a una funzione.

---

## `_split_multiline(value)` — helper testo → lista (righe 22–23)

```python
def _split_multiline(value):
    return [item.strip() for item in value.splitlines() if item.strip()]
```

Piccolo aiutante (il `_` iniziale indica "uso interno"). Nel form i pacchetti si scrivono **uno per
riga** in una `textarea`; questa funzione trasforma quel testo in una **lista Python**.

- `value.splitlines()` → spezza il testo in righe.
- `item.strip()` → toglie spazi all'inizio/fine di ogni riga.
- `if item.strip()` → scarta le righe **vuote**.
- Risultato: `["Cruise Control", "Fari LED"]` da un testo su due righe.

---

## `_build_vehicle_document(form, existing_document)` — dal form al documento (righe 26–84)

È la funzione che **trasforma i dati del form** (quello che l'utente ha digitato) nel **documento
MongoDB** da salvare, con i nomi dei campi in italiano e la struttura annidata giusta.

Riceve:
- `form` → i dati inviati dal browser (`request.form`).
- `existing_document` → il documento già presente nel DB (solo in modifica; `None` se è un'auto nuova).

### Configurazione (righe 27–37)
```python
    configuration = {
        "allestimento": form.get("allestimento", "").strip(),
        "motorizzazione": form.get("motorizzazione", "").strip(),
        "colore_esterno": form.get("colore_esterno", "").strip(),
        "pacchetti_inclusi": _split_multiline(form.get("pacchetti_inclusi", "")),
        "pacchetti_aggiuntivi": _split_multiline(form.get("pacchetti_aggiuntivi", "")),
    }
    battery_value = form.get("capacita_batteria_kw", "").strip()
    if battery_value:
        configuration["capacita_batteria_kw"] = int(battery_value)
    configuration["cavo_ricarica_incluso"] = form.get("cavo_ricarica_incluso") == "on"
```
- **27–33** costruisce il sotto-dizionario `configurazione`. `form.get("campo", "")` prende il valore
  o stringa vuota se manca; `.strip()` toglie gli spazi. I pacchetti passano da `_split_multiline`.
- **34–36** la batteria si aggiunge **solo se è stata compilata**: `int(battery_value)` la converte
  da testo a numero. Se il campo è vuoto, la chiave non viene messa (coerente col fatto che solo le
  elettriche hanno la batteria).
- **37** `cavo_ricarica_incluso`: una checkbox HTML manda `"on"` quando è spuntata; qui diventa un
  vero booleano `True`/`False`.

### Timeline: aggiungere un evento se serve (righe 39–68)
```python
    status = form.get("stato_attuale", "").strip()
    timeline = list((existing_document or {}).get("logistica_timeline") or [])
    timeline_status = form.get("timeline_stato", "").strip()
    timeline_date = form.get("timeline_data", "").strip()
    timeline_operator = form.get("timeline_operatore", "").strip() or form.get("venditore", "").strip() or "Sistema"
```
- **39** legge lo stato attuale scelto nel form.
- **40** parte dalla timeline **già esistente** (per non perdere lo storico). `list(...)` ne fa una
  copia; `existing_document or {}` evita errori se è `None`; `... or []` gestisce la timeline assente.
- **41–42** legge l'eventuale nuovo evento manuale (stato + data) inserito nel form.
- **43** decide **chi** è l'operatore: quello scritto nel form, altrimenti il venditore, altrimenti
  `"Sistema"`. Il pattern `a or b or c` prende il primo valore non vuoto.

```python
    if timeline_status and timeline_date:
        timeline.append({ "stato": timeline_status, "data": datetime.fromisoformat(timeline_date), "operatore": timeline_operator })
    elif existing_document is None:
        timeline.append({ "stato": status, "data": datetime.now(), "operatore": timeline_operator })
    elif existing_document.get("stato_attuale") != status:
        timeline.append({ "stato": status, "data": datetime.now(), "operatore": timeline_operator })
```
Tre casi, in ordine di priorità:
- **45–52** se l'utente ha compilato **a mano** stato + data → aggiunge quell'evento.
  `datetime.fromisoformat(timeline_date)` converte la stringa `"2026-07-08"` in una vera data.
- **53–60** altrimenti, se è un'**auto nuova** (`existing_document is None`) → registra il primo
  evento con la data/ora attuale (`datetime.now()`).
- **61–68** altrimenti, se in modifica lo **stato è cambiato** rispetto a prima → registra il
  passaggio di stato automaticamente.
- Se nessuna condizione è vera (modifica senza cambio stato), la timeline resta invariata.

### Il documento finale (righe 70–84)
```python
    return {
        "vin_telaio": form.get("vin_telaio", "").strip(),
        "marca": form.get("marca", "").strip(),
        "modello": form.get("modello", "").strip(),
        "stato_attuale": status,
        "venditore": form.get("venditore", "").strip(),
        "assegnato_a_cliente": {
            "id_cliente": form.get("id_cliente", "").strip(),
            "nome": form.get("nome_cliente", "").strip(),
            "email": form.get("email_cliente", "").strip(),
            "numero_telefono": form.get("telefono_cliente", "").strip(),
        },
        "configurazione": configuration,
        "logistica_timeline": timeline,
    }
```
Assembla il documento completo **con i nomi in italiano** (quelli che vuole il database) e la
struttura annidata (`assegnato_a_cliente`, `configurazione`). Questo è ciò che verrà salvato in Mongo.

> Nota: qui i nomi sono italiani perché stiamo **scrivendo** nel DB. Quando invece **leggiamo** per
> mostrare, `normalize_vehicle` (nel repository) li traduce in inglese. Sono due direzioni opposte.

---

## `_vehicle_form_defaults(document)` — dal documento ai campi del form (righe 87–113)

Fa il lavoro **inverso** della funzione precedente: prende un documento (grezzo) e prepara i valori
con cui **pre-riempire il form** di modifica.

```python
def _vehicle_form_defaults(document):
    # Riceve il documento GREZZO (chiavi italiane), non quello normalizzato,
    # cosi' il form di modifica mostra i valori realmente salvati.
    document = document or {}
    configuration = document.get("configurazione") or {}
    customer = document.get("assegnato_a_cliente") or {}
    return {
        "vin_telaio": document.get("vin_telaio", ""),
        ...
    }
```
- **90–92** parte dal documento (o `{}` se `None`) ed estrae i sotto-dizionari `configurazione` e
  `assegnato_a_cliente`.
- **93–113** restituisce un dizionario piatto con **una chiave per ogni campo del form** HTML
  (`vin_telaio`, `nome_cliente`, `allestimento`...), leggendo dal documento grezzo.
  - I pacchetti (che nel DB sono liste) vengono riuniti in testo con `"\n".join(...)`, così tornano a
    una riga per pacchetto nella `textarea`.
  - `cavo_ricarica_incluso` default `False`; i campi timeline (`timeline_stato`, `timeline_data`)
    partono **vuoti** perché servono solo per aggiungere un *nuovo* evento.

> ⚠️ Punto importante (era un bug, ora corretto): questa funzione legge le **chiavi grezze**
> (`vin_telaio`, `configurazione`, `assegnato_a_cliente`), quindi va chiamata con il **documento
> grezzo** (`get_vehicle_document_by_id`), non con l'auto normalizzata. Se le passassi quella
> normalizzata, configurazione e cliente uscirebbero vuoti (vedi la rotta `auto_dettaglio`).

---

## Le rotte (dove il browser "entra")

Ogni funzione qui sotto ha sopra un `@app.route("...")`: è il **decoratore** che collega un URL alla
funzione. Quando il browser visita quell'URL, Flask esegue la funzione e ne restituisce il risultato.

### `home()` — la homepage (righe 116–130)
```python
@app.route("/")
def home():
    summary = dashboard_summary()
    featured = featured_vehicles(limit=3)
    leaderboard = seller_leaderboard()
    return render_template("home.html", title="Home", featured=featured, leaderboard=leaderboard,
        fleet_count=summary["total"], ready_count=summary["ready"],
        transit_count=summary["in_transit"], preparation_count=summary["in_preparation"])
```
- **116** rotta `/` (la radice del sito).
- **118–120** chiede al repository i tre blocchi della home: i **numeri** riepilogativi
  (`dashboard_summary`), le **3 auto in evidenza** (`featured_vehicles`) e la **classifica venditori**
  (`seller_leaderboard`).
- **121–130** passa tutto a `home.html`. Le variabili (`featured`, `leaderboard`, `fleet_count`...)
  diventano disponibili dentro il template.

### `gestione_auto()` — dashboard operativa (righe 133–145)
```python
@app.route("/gestione-auto")
def gestione_auto():
    vehicles = list_vehicles()
    filters = build_filter_options(vehicles)
    return render_template("gestione_auto.html", title="Gestione auto", cars=vehicles,
        calendar_events=build_calendar_events(vehicles),
        status_options=filters["statuses"], brand_options=filters["brands"], trim_options=filters["trims"])
```
- **135** prende **tutti** i veicoli.
- **136** ne ricava le opzioni per i filtri (stati/marche/allestimenti unici).
- **137–145** passa al template la lista `cars`, gli **eventi del calendario**
  (`build_calendar_events`) e le opzioni dei tre menu a tendina.

### `catalogo()` — vetrina pubblica (righe 148–159)
```python
@app.route("/catalogo")
def catalogo():
    public_cars = list_vehicles(public_only=True)
    filters = build_filter_options(public_cars)
    return render_template("catalogo.html", ...)
```
- **150** come `gestione_auto`, ma con `public_only=True`: esclude le auto "In Preparazione", che non
  devono comparire ai clienti.
- **151–159** stessa logica di filtri e render, sul template `catalogo.html`.

### `auto_dettaglio(car_id)` — scheda singola (righe 162–181)
```python
@app.route("/auto/<car_id>")
def auto_dettaglio(car_id):
    car = get_vehicle_by_id(car_id)
    if car is None:
        abort(404)

    document = get_vehicle_document_by_id(car_id)
    related = list_vehicles(query={"marca": car["brand"]}, limit=3, exclude_id=car["id"])
    return render_template("auto_dettaglio.html", title=f"{car['brand']} {car['modello']}",
        car=car, related=related, vehicle_form=_vehicle_form_defaults(document), is_new=False)
```
- **162** `<car_id>` è una **parte variabile** dell'URL: `/auto/qualcosa` passa `qualcosa` come
  `car_id` alla funzione.
- **164–166** cerca l'auto **normalizzata** (per mostrarla). Se non esiste → `abort(404)`.
- **168** prende anche il **documento grezzo**, che serve a pre-riempire il form di modifica
  (vedi la nota su `_vehicle_form_defaults`).
- **169–173** trova fino a 3 **auto correlate** della stessa marca, escludendo quella aperta.
- **174–181** renderizza la scheda passando: l'auto (`car`), le correlate (`related`), i valori del
  form (`vehicle_form`) e `is_new=False` (è una modifica, non una creazione).

### `auto_update(car_id)` — salvataggio/cancellazione (righe 184–196)
```python
@app.route("/auto/<car_id>", methods=["POST"])
def auto_update(car_id):
    existing_document = get_vehicle_document_by_id(car_id)
    if existing_document is None:
        abort(404)

    if request.form.get("action") == "delete":
        delete_vehicle_document(car_id)
        return redirect(url_for("gestione_auto"))

    vehicle_document = _build_vehicle_document(request.form, existing_document=existing_document)
    upsert_vehicle_document(vehicle_document, vehicle_id=car_id)
    return redirect(url_for("auto_dettaglio", car_id=car_id))
```
- **184** **stesso URL** di `auto_dettaglio`, ma con `methods=["POST"]`: si attiva quando il form
  viene **inviato** (non quando si visita la pagina). GET = mostra, POST = salva.
- **186–188** ricarica il documento esistente; se non c'è più → 404.
- **190–192** se il pulsante premuto era "Elimina" (`action=delete`) → cancella e torna alla gestione.
- **194–196** altrimenti costruisce il documento aggiornato dal form (`_build_vehicle_document`),
  lo salva (`upsert_vehicle_document`) e **rimanda** alla scheda aggiornata. Il `redirect` dopo un
  POST è una buona pratica (evita il doppio invio se ricarichi la pagina).

### `auto_nuova()` — creazione (righe 199–220)
```python
@app.route("/auto/nuova", methods=["GET", "POST"])
def auto_nuova():
    if request.method == "POST":
        vehicle_document = _build_vehicle_document(request.form)
        new_id = upsert_vehicle_document(vehicle_document)
        return redirect(url_for("auto_dettaglio", car_id=new_id))

    return render_template("auto_dettaglio.html", title="Nuova auto",
        car={ "brand": "", "modello": "", "status": "", "timeline": [], "timeline_count": 0, "arrival_date": "N/D" },
        related=[], vehicle_form=_vehicle_form_defaults({}), is_new=True)
```
- **199** questa rotta gestisce **due metodi**: `GET` (mostra il form vuoto) e `POST` (crea l'auto).
- **201–204** se è un POST → costruisce il documento (senza `existing_document`, quindi è nuovo), lo
  inserisce e va alla scheda del veicolo appena creato (`new_id`).
- **206–220** se è un GET → mostra lo **stesso template** della scheda, ma con un `car` "finto" e
  vuoto (giusto i 6 campi che il template legge per l'intestazione) e `is_new=True`. Il form parte
  vuoto (`_vehicle_form_defaults({})`).

> Riuso intelligente: creazione e modifica usano **lo stesso template** `auto_dettaglio.html`; la
> variabile `is_new` gli dice se comportarsi da "crea" o da "salva".

---

## Avvio dell'app (righe 223–224)

```python
if __name__ == "__main__":
    app.run(debug=True)
```
- **223** questo blocco parte solo se lanci il file **direttamente** (`python app.py`), non quando
  viene importato da altri.
- **224** avvia il server di sviluppo Flask. `debug=True` = ricarica automatica al salvataggio e
  pagine di errore dettagliate (**solo in sviluppo**, mai in produzione).

---

## Schema del flusso (chi chiama chi)

```
Browser  ──richiesta──▶  rotta in app.py  ──chiama──▶  mongo_repository.py  ──▶  MongoDB
                              │                              (query)
                              ▼
                        render_template
                              │
                              ▼
                        template HTML  ──HTML──▶  Browser
```

## Concetti chiave da ricordare

1. **Rotta = URL + funzione**: `@app.route` collega un indirizzo a una funzione Python.
2. **GET vs POST**: GET mostra le pagine, POST salva i dati dei form.
3. **Due traduzioni opposte**: `_build_vehicle_document` (form → DB, in italiano) e `normalize_vehicle`
   nel repository (DB → template, in inglese). `_vehicle_form_defaults` invece riempie il form dal
   documento grezzo.
4. **app.py non tocca MongoDB**: usa solo le funzioni di `mongo_repository.py`. Le query sono
   spiegate in [`query_mongodb.md`](query_mongodb.md).
5. **PRG (Post-Redirect-Get)**: dopo ogni salvataggio si fa `redirect`, per non ripetere l'operazione
   ricaricando la pagina.
