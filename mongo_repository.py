import os
from datetime import datetime

from bson import ObjectId
from pymongo import ASCENDING, MongoClient


# --- Connessione al database ---------------------------------------------
# Ci si connette una volta sola: "collection" e' la collezione "vehicles"
# su cui facciamo tutte le operazioni (find, insert, update, delete).
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "db_veicoli")
MONGO_COLLECTION_NAME = os.getenv("MONGO_COLLECTION_NAME", "vehicles")

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
collection = client[MONGO_DB_NAME][MONGO_COLLECTION_NAME]


def format_date(value):
    # Trasforma una data (o stringa) nel formato leggibile gg/mm/aaaa.
    if not value:
        return "N/D"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    return str(value)[:10]


def normalize_vehicle(document):
    # Traduce un documento del DB (campi in italiano e annidati) in un
    # dizionario semplice con nomi in inglese, pronto per i template.
    config = document.get("configurazione") or {}
    customer = document.get("assegnato_a_cliente") or {}
    timeline = document.get("logistica_timeline") or []
    last_step = timeline[-1] if timeline else None
    last_date = last_step["data"] if last_step else None

    return {
        "id": str(document["_id"]),
        "vin": document.get("vin_telaio", ""),
        "brand": document.get("marca", ""),
        "modello": document.get("modello", ""),
        "status": document.get("stato_attuale", ""),
        "seller": document.get("venditore", ""),
        "customer_name": customer.get("nome", ""),
        "customer_email": customer.get("email", ""),
        "customer_phone": customer.get("numero_telefono", ""),
        "trim": config.get("allestimento", "N/D"),
        "motorizzazione": config.get("motorizzazione", "N/D"),
        "color": config.get("colore_esterno", "N/D"),
        "included_packages": config.get("pacchetti_inclusi", []),
        "extra_packages": config.get("pacchetti_aggiuntivi", []),
        "battery_kwh": config.get("capacita_batteria_kw"),
        "charging_cable": config.get("cavo_ricarica_incluso"),
        "timeline": [
            {
                "status": step.get("stato", ""),
                "date": format_date(step.get("data")),
                "operator": step.get("operatore", ""),
            }
            for step in timeline
        ],
        "timeline_count": len(timeline),
        "arrival_date": format_date(last_date),
        "arrival_date_iso": last_date.date().isoformat() if isinstance(last_date, datetime) else None,
        "arrival_date_raw": last_date,
        "public": document.get("stato_attuale") != "In Preparazione",
    }


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


def get_vehicle_document_by_id(vehicle_id):
    # Cerca un veicolo per _id oppure, se non lo trova, per numero di telaio.
    if ObjectId.is_valid(vehicle_id):
        document = collection.find_one({"_id": ObjectId(vehicle_id)})
        if document:
            return document
    return collection.find_one({"vin_telaio": vehicle_id})


def get_vehicle_by_id(vehicle_id):
    # Come sopra, ma restituisce il veicolo gia' normalizzato (per mostrarlo).
    document = get_vehicle_document_by_id(vehicle_id)
    return normalize_vehicle(document) if document else None


def upsert_vehicle_document(document, vehicle_id=None):
    # Se c'e' un id -> aggiorna (update_one), altrimenti crea (insert_one).
    if vehicle_id and ObjectId.is_valid(vehicle_id):
        collection.update_one({"_id": ObjectId(vehicle_id)}, {"$set": document})
        return vehicle_id
    result = collection.insert_one(document)
    return str(result.inserted_id)


def delete_vehicle_document(vehicle_id):
    # Cancella per _id oppure per numero di telaio.
    if ObjectId.is_valid(vehicle_id):
        result = collection.delete_one({"_id": ObjectId(vehicle_id)})
    else:
        result = collection.delete_one({"vin_telaio": vehicle_id})
    return result.deleted_count > 0


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


def featured_vehicles(limit=3):
    # Le auto con l'ultimo aggiornamento piu' recente: prendo tutti i veicoli
    # e li ordino per data dell'ultimo evento, tenendo solo i primi.
    vehicles = list_vehicles()
    vehicles.sort(key=lambda vehicle: vehicle["arrival_date_raw"] or datetime.min, reverse=True)
    return vehicles[:limit]


def build_filter_options(vehicles):
    # Valori unici (senza duplicati) per riempire i menu a tendina dei filtri.
    return {
        "statuses": sorted({vehicle["status"] for vehicle in vehicles}),
        "brands": sorted({vehicle["brand"] for vehicle in vehicles}),
        "trims": sorted({vehicle["trim"] for vehicle in vehicles if vehicle["trim"] != "N/D"}),
    }


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
                "dateLabel": vehicle["arrival_date"],
                "vehicleId": vehicle["id"],
                "backgroundColor": colori_stato.get(vehicle["status"], "#9eb2cf"),
                "borderColor": "#ffffff22",
                "extendedProps": {
                    "status": vehicle["status"],
                    "vin": vehicle["vin"],
                    "trim": vehicle["trim"],
                },
            }
        )
    return events
