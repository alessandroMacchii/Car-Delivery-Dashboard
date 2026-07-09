# Car-Delivery-Dashboard

Dashboard Flask collegata a MongoDB per la gestione della flotta auto.

## Funzioni

- home generale con indicatori di stato dalla collection `vehicles`
- pagina gestione auto con calendario arrivi e filtri MongoDB
- pagina catalogo utenti con schede pubbliche filtrabili
- pagina dettaglio singola auto con configurazione e timeline

## Avvio locale

```powershell
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## MongoDB e Compass

Compass non ospita i dati: si collega al server MongoDB che stai usando. In locale puoi usare una URI come `mongodb://localhost:27017` e aprire la stessa connessione in Compass.

Variabili usate dall'app:

- `MONGO_URI` default `mongodb://localhost:27017`
- `MONGO_DB_NAME` default `db_veicoli`
- `MONGO_COLLECTION_NAME` default `vehicles`

## Popolare il database

Modo consigliato: genera dati di esempio (veicoli Renault fittizi) con Faker.
Lo script svuota la collection e la riempie da zero, usando la stessa connessione
dell'app (quindi rispetta le variabili d'ambiente qui sopra):

```powershell
python datagenerator.py
```

## Rotte

- `/` home
- `/gestione-auto` dashboard operativa
- `/catalogo` catalogo pubblico
- `/auto/<car_id>` dettaglio singola auto