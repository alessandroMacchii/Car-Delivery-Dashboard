# Car Delivery Dashboard — Presentazione del progetto

> Deck per la presentazione orale. Ogni sezione `---` è una "slide".
> Focus su **dati, MongoDB e backend**; la parte di front-end (HTML/CSS/JavaScript)
> è volutamente esclusa. Sotto ogni slide c'è un **🎤 Da dire** con la traccia parlata.

---

## Slide 1 — Titolo

# 🚗 Car Delivery Dashboard
### Gestione della consegna auto con Flask + MongoDB

Studente: *Alessandro Macchi*

🎤 **Da dire:** *"Presento una dashboard per gestire il flusso di consegna delle
auto di una concessionaria: dall'ordine in fabbrica fino alla consegna al cliente.
Il cuore del progetto è un database MongoDB interrogato da un'applicazione Flask."*

---

## Slide 2 — Il problema

Una concessionaria deve tenere traccia di:
- **dove si trova** ogni auto nel percorso (ordinata, in viaggio, arrivata, pronta…)
- la **configurazione** di ogni vettura (allestimento, motore, colore, optional…)
- il **cliente** a cui è assegnata
- la **storia logistica** (chi ha fatto cosa e quando)

Serve un modello dati **flessibile**: auto diverse hanno campi diversi (es. solo le
elettriche hanno batteria e cavo di ricarica).

🎤 **Da dire:** *"Il dato non è rigido: un'auto elettrica ha campi che una termica
non ha. Un modello a tabelle fisse sarebbe scomodo; un database a documenti come
MongoDB si adatta meglio."*

---

## Slide 3 — Stack tecnologico

| Componente        | Tecnologia            | Ruolo                              |
|-------------------|-----------------------|------------------------------------|
| Database          | **MongoDB**           | Archivio documenti (NoSQL)         |
| Driver            | **PyMongo**           | Collega Python a MongoDB           |
| Web framework     | **Flask**             | Rotte e pagine dell'app            |
| Template          | Jinja2                | HTML dinamico *(non presentato)*   |
| Dati di test      | **Faker**             | Genera veicoli realistici          |

🎤 **Da dire:** *"Python fa da collante: Flask gestisce le pagine, PyMongo parla col
database. Per popolare il DB uso Faker, che genera dati finti ma verosimili."*

---

## Slide 4 — Architettura a livelli

```
  Browser
     │  richiesta HTTP (es. GET /catalogo)
     ▼
  app.py            ← LIVELLO WEB: rotte, form, logica di pagina
     │  chiama funzioni
     ▼
  mongo_repository.py ← LIVELLO DATI: tutte le query MongoDB
     │  find / aggregate / insert / update / delete
     ▼
  MongoDB (db_veicoli.vehicles)
```

**Regola chiave:** `app.py` **non parla mai direttamente con MongoDB**. Tutte le
query stanno in un unico file, `mongo_repository.py`.

🎤 **Da dire:** *"Ho separato le responsabilità: la logica web sta in app.py, tutto
l'accesso ai dati in mongo_repository. Così le query sono in un posto solo e il
codice è più ordinato e testabile."*

---

## Slide 5 — Il modello dati: un documento `vehicles`

```json
{
  "_id": ObjectId("..."),
  "vin_telaio": "VF1...",
  "marca": "Renault",
  "modello": "Scenic E-Tech",
  "stato_attuale": "In Viaggio",
  "venditore": "Sofia Verdi",
  "assegnato_a_cliente": { "nome": "...", "email": "...", "numero_telefono": "..." },
  "configurazione": {
    "allestimento": "Techno", "motorizzazione": "...", "colore_esterno": "...",
    "pacchetti_inclusi": [ ... ], "pacchetti_aggiuntivi": [ ... ],
    "capacita_batteria_kw": 87, "cavo_ricarica_incluso": true   // solo elettriche
  },
  "logistica_timeline": [
    { "stato": "Ordinato in Fabbrica", "data": ISODate("..."), "operatore": "Sistema" },
    { "stato": "In Viaggio", "data": ISODate("..."), "operatore": "Marco" }
  ]
}
```

🎤 **Da dire:** *"Ogni auto è un unico documento che contiene tutto: dati piatti,
oggetti annidati (cliente, configurazione) e un array (la timeline). In un DB
relazionale servirebbero più tabelle con join; qui è tutto in un documento."*

---

## Slide 6 — Perché MongoDB (i concetti che sfrutto)

- **Documenti annidati** → cliente e configurazione dentro l'auto, niente join.
- **Array** → `logistica_timeline` è una lista di eventi dentro il documento.
- **Schema flessibile / Polymorphic Pattern** → i campi `capacita_batteria_kw` e
  `cavo_ricarica_incluso` esistono **solo** sulle auto elettriche.
- **`_id` come `ObjectId`** → chiave primaria generata automaticamente.

🎤 **Da dire:** *"Sfrutto tre cose tipiche del modello a documenti: annidamento,
array e schema flessibile. È il 'polymorphic pattern': documenti della stessa
collezione con forma leggermente diversa a seconda del tipo di auto."*

---

## Slide 7 — Le operazioni sul database (CRUD + aggregazioni)

Tutte le query stanno in `mongo_repository.py`:

| Operazione        | Metodo MongoDB              | Funzione                     |
|-------------------|-----------------------------|------------------------------|
| Leggi elenco      | `find().sort()`             | `list_vehicles`              |
| Leggi uno         | `findOne`                   | `get_vehicle_by_id`          |
| Crea              | `insertOne`                 | `upsert_vehicle_document`    |
| Modifica          | `updateOne` + `$set`        | `upsert_vehicle_document`    |
| Cancella          | `deleteOne`                 | `delete_vehicle_document`    |
| Conta/raggruppa   | `aggregate` + `$group/$sum` | `dashboard_summary`, `seller_leaderboard` |

🎤 **Da dire:** *"Ci sono tutte e quattro le operazioni CRUD, più le aggregazioni per
i numeri della dashboard. Le vediamo una per una."*

---

## Slide 8 — Lettura: `find` e `findOne`

```js
// Elenco ordinato (Gestione auto)
db.vehicles.find({}).sort({ marca: 1 })

// Solo pubblici, esclude "In Preparazione" (Catalogo) — operatore $ne
db.vehicles.find({ stato_attuale: { $ne: "In Preparazione" } })

// Un singolo veicolo (Dettaglio) — per _id o per telaio
db.vehicles.findOne({ _id: ObjectId("...") })
```

- `find({})` = tutti; il filtro `{}` è vuoto.
- `$ne` = "diverso da" → nasconde le auto in preparazione ai clienti.
- `findOne` = un solo documento.

🎤 **Da dire:** *"La lettura di base: find per le liste, findOne per il singolo. Uso
l'operatore $ne per il catalogo pubblico, che non deve mostrare le auto ancora in
preparazione."*

---

## Slide 9 — Scrittura: `insertOne` / `updateOne` / `deleteOne`

```js
db.vehicles.insertOne({ vin_telaio: "...", marca: "Renault", ... })

db.vehicles.updateOne(
  { _id: ObjectId("...") },                 // QUALE documento
  { $set: { stato_attuale: "In Viaggio" } } // COSA cambiare
)

db.vehicles.deleteOne({ _id: ObjectId("...") })
```

- `$set` aggiorna **solo** i campi indicati, lasciando intatti gli altri.
- Nell'app queste tre operazioni sono guidate dai **form** (crea / salva / elimina).

🎤 **Da dire:** *"La scrittura è pilotata dai form dell'app. Nota updateOne con $set:
cambio solo i campi modificati senza toccare il resto, per esempio senza perdere la
timeline."*

---

## Slide 10 — Aggregazioni: contare e raggruppare

**Riepilogo per stato** (le card della home):
```js
db.vehicles.aggregate([
  { $group: { _id: "$stato_attuale", count: { $sum: 1 } } }
])
```

**Classifica venditori** (card in home):
```js
db.vehicles.aggregate([
  { $group: { _id: "$venditore", count: { $sum: 1 } } },
  { $sort: { count: -1 } }
])
```

- `$group` raggruppa per un campo; `$sum: 1` conta; `$sort: -1` ordina dal più alto.

🎤 **Da dire:** *"Per i numeri uso una aggregation pipeline: $group raggruppa,
$sum conta. La classifica venditori è la stessa cosa con in più un $sort. È l'unico
punto dove faccio calcolare al database, non a Python."*

---

## Slide 11 — La "normalizzazione" dei dati

Nel DB i campi sono in **italiano** e annidati; le pagine vogliono dati **piatti** e
in **inglese**. La funzione `normalize_vehicle` fa da ponte:

```
{ "marca": "Renault",                        {  "brand": "Renault",
  "configurazione": { "allestimento": "..."}, ─▶  "trim": "...",
  "logistica_timeline": [ ..., {ultimo} ] }       "arrival_date": "08/07/2026" }
```

Non solo rinomina: **calcola** anche campi che nel DB non esistono, come la data di
arrivo (= data dell'ultimo evento della timeline) e il numero di eventi.

🎤 **Da dire:** *"Un piccolo strato traduce il documento grezzo in un formato comodo
per le pagine, e calcola valori derivati come la data di arrivo. Così la logica sta
in un punto solo invece di essere sparsa."*

---

## Slide 12 — Popolamento del database (Faker)

`datagenerator.py` crea veicoli Renault realistici e li inserisce:

- sceglie modello, motore, allestimento, colore, pacchetti in modo coerente;
- se l'auto è **elettrica**, aggiunge batteria e cavo (polymorphic pattern);
- genera una **timeline** progressiva coerente con lo stato attuale;
- usa la **stessa connessione** dell'app (`from mongo_repository import collection`).

```bash
python datagenerator.py   # svuota e ripopola la collection
```

🎤 **Da dire:** *"Per avere dati su cui lavorare uso Faker: genera veicoli verosimili
con una timeline coerente. Riusa la connessione del repository, così la
configurazione del database è definita una volta sola."*

---

## Slide 13 — Dove si vedono le query (mappa demo)

| Query                         | Pagina della demo            |
|-------------------------------|------------------------------|
| `dashboard_summary`, `seller_leaderboard`, `featured_vehicles` | **Home** |
| `list_vehicles` + filtri      | **Gestione auto**            |
| `list_vehicles(public_only)`  | **Catalogo**                 |
| `findOne` + correlate         | **Dettaglio auto**           |
| `insert / update / delete`    | **Nuova auto / Dettaglio**   |

🎤 **Da dire:** *"Ogni query ha un posto preciso nell'interfaccia: qui è la mappa tra
il codice e ciò che si vede."*

---

## Slide 14 — Demo dal vivo (percorso consigliato)

1. **Home** → mostro le card riepilogative (`$group`) e la classifica venditori (`$group`+`$sort`).
2. **Gestione auto** → l'elenco (`find`) e i filtri.
3. **Catalogo** → stessa lista ma con `$ne` (niente auto in preparazione).
4. **Dettaglio auto** → `findOne`, timeline e auto correlate.
5. **Modifica / Nuova** → `updateOne` / `insertOne`, poi **Compass** per vedere il
   documento cambiato nel database.

🎤 **Da dire:** *"Chiudo mostrando un salvataggio e poi lo stesso documento in
MongoDB Compass, così si vede che l'app scrive davvero sul database."*

---

## Slide 15 — Punti di forza e possibili estensioni

**Punti di forza**
- Separazione netta web / dati (query tutte in un file).
- Modello a documenti che sfrutta annidamento, array e schema flessibile.
- Copertura completa CRUD + aggregazioni.

**Estensioni possibili (in programma)**
- Nuove aggregazioni: stock per modello, colori più richiesti (stessa forma della
  classifica venditori).

**Estensioni avanzate (oltre il programma)**
- Tempo medio di consegna (`$dateDiff`), dashboard in una query (`$facet`).

🎤 **Da dire:** *"Il progetto è facilmente estendibile: aggiungere una statistica
significa aggiungere una funzione con una query e una card. Grazie."*

---

## Appendice — domande probabili & risposte brevi

- **Perché MongoDB e non SQL?** Dati semi-strutturati e campi variabili (elettriche
  vs termiche): il modello a documenti evita join e tabelle vuote.
- **Cos'è `ObjectId`?** La chiave primaria di 12 byte generata da MongoDB; va avvolta
  in `ObjectId("...")` nelle query per `_id`.
- **Cos'è `$set`?** Aggiorna solo i campi indicati, senza sovrascrivere l'intero
  documento.
- **Perché alcune cose le calcoli in Python e non in Mongo?** Per restare sugli
  operatori visti a lezione; dove servirebbero operatori avanzati (ultimo elemento
  di un array, differenze di date) sposto il lavoro in Python.
- **Come popoli il DB?** Con `datagenerator.py` (Faker); in alternativa import JSON
  con `seed_mongo.py`.
