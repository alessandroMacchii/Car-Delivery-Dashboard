# Query MongoDB del progetto — guida spiegata

Questo file raccoglie **tutte le query usate dall'applicazione** (definite in
`mongo_repository.py`) riscritte in sintassi **mongosh**, cioè quella che puoi
digitare direttamente nella shell `mongosh` o nella scheda *>_MONGOSH* di
MongoDB Compass. Per ogni query trovi: cosa fa, la spiegazione riga per riga,
un esempio di risultato e una frase pronta da dire a voce.

---

## Concetti di base (da tenere a mente)

- **Database → collection → documenti.** Qui il database è `db_veicoli`, la
  collection è `vehicles`, e ogni documento è un veicolo. Un documento è in
  pratica un oggetto JSON (tecnicamente **BSON**, cioè JSON binario con qualche
  tipo in più come `ObjectId` e le date).
- **`_id`** è la chiave primaria: MongoDB la genera in automatico come
  `ObjectId`, un identificatore unico di 12 byte. Non è una stringa, quindi nelle
  query va sempre avvolta in `ObjectId("...")`.
- **Il `$` davanti a un nome** dentro le aggregazioni significa "il **valore** di
  quel campo". Esempio: `"$stato_attuale"` = *il contenuto del campo
  `stato_attuale` di quel documento*. Senza `$` è invece un valore fisso scritto
  da noi.
- **Operatori** (iniziano con `$`): sono le "parole chiave" di MongoDB.
  `$ne`, `$in`, `$or`, `$eq`, `$regex`, `$group`, `$sum`, `$cond`... li vediamo
  uno per uno più sotto.

### Python vs mongosh (perché il codice sembra diverso)

Nel codice (`mongo_repository.py`) le query sono scritte come **dizionari
Python**, non come stringhe. Non è un modo diverso di interrogare il database:
è **la stessa identica query**, solo scritta con la sintassi che pretende la
libreria `pymongo`. Le uniche differenze sono cosmetiche:

| Nel codice Python (pymongo)      | Nella shell MongoDB (mongosh) |
| -------------------------------- | ----------------------------- |
| `True` / `False` / `None`        | `true` / `false` / `null`     |
| `ASCENDING` / `DESCENDING`       | `1` / `-1`                    |
| `{"marca": "Renault"}`           | `{ marca: "Renault" }`        |

> **In sintesi:** pymongo **non** accetta stringhe tipo `db.vehicles.find("...")`;
> vuole dizionari. Ma quel dizionario *è* la query MongoDB, spedita al server
> così com'è.

### Nota sul programma svolto

Le query di questo progetto usano **solo** operatori/metodi visti a lezione
(`find`, `findOne`, proiezione, `$ne`, dot notation, `.sort()`, `insertOne`,
`updateOne` con `$set`, `$group` con `$sum`). Le uniche **due eccezioni**,
consapevoli, sono:

- **`deleteOne`** (sezione 6) → la cancellazione non è stata trattata a lezione,
  ma è la controparte diretta di `insertOne`/`updateOne`: è il "D" del CRUD.
- **`ObjectId`** → serve per cercare un documento per `_id`; il concetto che
  l'`_id` è un ObjectId è comunque stato introdotto nelle prime lezioni.

Dove una funzionalità richiederebbe operatori non visti (estrarre l'ultimo
elemento di un array, contare con una condizione), il lavoro è spostato **in
Python** invece di usare operatori MongoDB avanzati.

### Struttura di un documento `vehicles`

Utile averla sott'occhio: molte query pescano dentro i campi annidati.

```js
{
  _id: ObjectId("64b0c1f2a3d4e5f600112233"),
  vin_telaio: "VF1ABCDE12345678",
  marca: "Renault",
  modello: "Clio",
  stato_attuale: "In Viaggio",
  venditore: "Laura Rossi",
  assegnato_a_cliente: {            // campo annidato (sotto-oggetto)
    id_cliente: "CUST-1234",
    nome: "Mario Rossi",
    email: "mario@example.com",
    numero_telefono: "+39 333 1234567"
  },
  configurazione: {                 // campo annidato
    allestimento: "Techno",
    motorizzazione: "TCe 90",
    colore_esterno: "Rosso Passion",
    pacchetti_inclusi: ["Fari Full LED", "Cruise Control"],
    pacchetti_aggiuntivi: []
  },
  logistica_timeline: [             // array di eventi (in ordine cronologico)
    { stato: "Ordinato in Fabbrica", data: ISODate("2026-04-01"), operatore: "Sistema" },
    { stato: "In Viaggio",           data: ISODate("2026-04-08"), operatore: "Marco" }
  ]
}
```

### Preparazione: selezionare il database

Prima di lanciare qualsiasi query, nella shell:

```js
use db_veicoli
```

---

## 1. Elenco veicoli ordinato — `list_vehicles()`

**Cosa fa:** restituisce tutti i veicoli, ordinati per marca.

```js
db.vehicles.find({}).sort({ marca: 1 })
```

**Spiegazione:**
- `db.vehicles` → la collection su cui lavoriamo.
- `find({})` → cerca i documenti che rispettano il filtro. Il filtro `{}` è
  **vuoto**, quindi non filtra nulla: prende **tutti** i documenti.
- `.sort({ marca: 1 })` → ordina il risultato per marca. `1` = crescente (A→Z),
  `-1` = decrescente (Z→A).

**Da dire a voce:** *"Prendo tutti i veicoli e li ordino alfabeticamente per
marca."*

### Variante A — solo veicoli "pubblici" (pagina Catalogo)

Il catalogo pubblico non deve mostrare le auto ancora in lavorazione.

```js
db.vehicles.find({ stato_attuale: { $ne: "In Preparazione" } })
           .sort({ marca: 1 })
```

- `{ stato_attuale: { $ne: "In Preparazione" } }` → il filtro ora c'è: tieni solo
  i documenti in cui `stato_attuale` è **diverso da** `"In Preparazione"`.
- `$ne` = *not equal*, "diverso da".

### Variante B — filtrare per un campo annidato

Nella pagina di dettaglio mostriamo le auto correlate con la **dot notation** per
entrare dentro un sotto-oggetto (es. tutte le auto assegnate a un certo cliente):

```js
db.vehicles.find({ "assegnato_a_cliente.nome": "Mario Rossi" })
```

- `"assegnato_a_cliente.nome"` → la **dot notation** (`.`) permette di entrare
  dentro un campo annidato: qui filtriamo sul `nome` dentro l'oggetto
  `assegnato_a_cliente`.

---

## 2. Singolo veicolo — `get_vehicle_by_id()`

**Cosa fa:** recupera un veicolo. Prova prima per `_id`; se non lo trova, prova
per numero di telaio (`vin_telaio`).

```js
db.vehicles.findOne({ _id: ObjectId("64b0c1f2a3d4e5f600112233") })
db.vehicles.findOne({ vin_telaio: "VF1ABCDE12345678" })
```

- `findOne(...)` → come `find`, ma restituisce **un solo documento** (il primo che
  combacia) invece di una lista. Se non trova nulla restituisce `null`.
- `ObjectId("...")` → ricordati che l'`_id` è un ObjectId, non una stringa: se
  scrivessi `{ _id: "64b0..." }` non troverebbe niente.

**Da dire a voce:** *"Cerco un singolo veicolo per identificatore; se l'utente ha
usato il numero di telaio invece dell'id interno, lo trovo comunque."*

---

## 3. Veicoli correlati (stessa marca, escluso quello aperto)

**Cosa fa:** nella pagina di dettaglio mostra altre auto della stessa marca,
escludendo quella che sto già guardando.

```js
db.vehicles.find({
  marca: "Renault",
  _id: { $ne: ObjectId("64b0c1f2a3d4e5f600112233") }
})
```

- Due condizioni nello stesso filtro sono in **AND** implicito: marca uguale a
  "Renault" **e** `_id` diverso da quello corrente.
- `$ne` esclude il veicolo che stiamo visualizzando (altrimenti comparirebbe tra
  i "correlati" a sé stesso).

---

## 4. Riepilogo dashboard — `dashboard_summary()`

**Cosa fa:** calcola i numeri della home: totale veicoli e quanti sono pronti, in
viaggio, in preparazione. Qui si usa una **aggregation pipeline**: una sequenza di
"stadi" in cui i documenti passano da uno stadio all'altro come su un nastro
trasportatore. Usiamo un solo stadio, `$group`, esattamente come visto a lezione
("conta le aziende per anno di fondazione").

```js
db.vehicles.aggregate([
  { $group: { _id: "$stato_attuale", count: { $sum: 1 } } }
])
```

**Spiegazione:**
- `$group` → raggruppa i documenti; la chiave del gruppo è `_id`.
- `_id: "$stato_attuale"` → un gruppo (= una riga) **per ogni stato diverso**. Il
  `$` davanti significa "il valore del campo `stato_attuale`".
- `count: { $sum: 1 }` → dentro ogni gruppo aggiungi `1` per ogni documento:
  ottieni **quanti veicoli** hanno quello stato. `$sum` è l'accumulatore visto a
  lezione.

**Risultato (una riga per stato):**

```js
{ _id: "Pronta per la consegna", count: 42 }
{ _id: "In Viaggio",            count: 30 }
{ _id: "In Preparazione",       count: 18 }
{ _id: "Arrivato in Concessionaria", count: 25 }
{ _id: "Ordinato in Fabbrica",  count: 35 }
```

Poi il **totale** e il raggruppamento "pronte" (pronta + arrivato) li calcoliamo
in Python sommando questi conteggi — nessun operatore extra:

```python
counts = {row["_id"]: row["count"] for row in collection.aggregate(pipeline)}
total          = sum(counts.values())
ready          = counts.get("Pronta per la consegna", 0) + counts.get("Arrivato in Concessionaria", 0)
in_transit     = counts.get("In Viaggio", 0)
in_preparation = counts.get("In Preparazione", 0)
```

**Da dire a voce:** *"Raggruppo per stato e conto quanti veicoli ci sono in
ciascuno; il totale e la categoria 'pronte' li ricavo sommando i conteggi."*

---

## 5. Auto in evidenza — `featured_vehicles()`

**Cosa fa:** mostra in home le **3 auto con l'attività più recente**, cioè quelle
il cui ultimo evento nella timeline logistica è il più recente.

La data che ci interessa è dentro l'**ultimo elemento** dell'array
`logistica_timeline`: estrarla e ordinarci sopra dentro MongoDB richiederebbe
operatori non visti a lezione. Perciò usiamo solo un `find()` normale e facciamo
**ordinamento e selezione in Python**.

```js
// MongoDB: prende semplicemente tutti i veicoli
db.vehicles.find({})
```

```python
# Python: ordino per data dell'ultimo evento (gia' calcolata in normalize_vehicle)
# e tengo i primi 3
vehicles = list_vehicles()
vehicles.sort(
    key=lambda vehicle: vehicle["arrival_date_raw"] or datetime.min,
    reverse=True,
)
featured = vehicles[:3]
```

- `find({})` → recupera tutti i veicoli (nessun operatore speciale).
- `arrival_date_raw` → è la data dell'ultimo evento della timeline, che
  `normalize_vehicle` calcola già prendendo l'ultimo elemento dell'array in
  Python (`timeline[-1]`).
- `sort(..., reverse=True)` + `[:3]` → ordino dal più recente e prendo i primi 3.

**Da dire a voce:** *"Prendo tutte le auto, in Python le ordino per data
dell'ultimo evento logistico e tengo le prime tre."*

---

## 6. Scrittura: inserimento, modifica, cancellazione

Le operazioni che modificano i dati (usate dai form dell'app).

```js
// INSERIMENTO — crea un nuovo veicolo
db.vehicles.insertOne({
  vin_telaio: "VF1NUOVO000000001",
  marca: "Renault",
  modello: "Clio",
  stato_attuale: "Ordinato in Fabbrica",
  logistica_timeline: []
})

// MODIFICA — cambia alcuni campi di un veicolo esistente
db.vehicles.updateOne(
  { _id: ObjectId("64b0c1f2a3d4e5f600112233") },   // filtro: QUALE documento
  { $set: { stato_attuale: "In Viaggio", venditore: "Laura Rossi" } }  // COSA cambiare
)

// CANCELLAZIONE — elimina un veicolo
db.vehicles.deleteOne({ _id: ObjectId("64b0c1f2a3d4e5f600112233") })
```

- `insertOne(documento)` → inserisce **un** documento; MongoDB gli assegna un
  `_id` in automatico.
- `updateOne(filtro, modifica)` → il primo argomento dice **quale** documento
  aggiornare, il secondo **cosa** fare. `$set` cambia (o aggiunge) solo i campi
  elencati e **lascia intatti** tutti gli altri.
- `deleteOne(filtro)` → cancella **un** documento (il primo che combacia).
- Esistono anche `insertMany`, `updateMany`, `deleteMany` per operare su più
  documenti in colpo solo.

---

## Appendice — come ottenere un `_id` vero da usare nei test

Gli `ObjectId("64b0...")` qui sopra sono inventati. Per provare le query con un
id reale, prendine uno dalla collection:

```js
db.vehicles.findOne()._id      // stampa un ObjectId reale: copialo nelle query
```

Oppure, per vedere id e modello di qualche veicolo:

```js
db.vehicles.find({}, { modello: 1, stato_attuale: 1 }).limit(5)
```

- Il secondo argomento di `find`, `{ modello: 1, stato_attuale: 1 }`, è la
  **proiezione**: mostra solo quei campi (più l'`_id`, incluso di default). Serve
  per alleggerire l'output quando non servono tutti i campi.
