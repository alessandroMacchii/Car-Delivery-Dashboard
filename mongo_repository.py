from __future__ import annotations

import os
from datetime import date, datetime
from functools import lru_cache
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, MongoClient


MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "db_veicoli")
MONGO_COLLECTION_NAME = os.getenv("MONGO_COLLECTION_NAME", "vehicles")


@lru_cache(maxsize=1)
def get_collection():
	client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
	return client[MONGO_DB_NAME][MONGO_COLLECTION_NAME]


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


def _timeline_date(entry: dict[str, Any] | None) -> str:
	if not entry:
		return "N/D"
	return format_date(entry.get("data"))


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


def _timeline_sort_key(vehicle: dict[str, Any]) -> str:
	return vehicle.get("arrival_date_raw") or vehicle.get("arrival_date") or ""


def normalize_vehicle(document: dict[str, Any]) -> dict[str, Any]:
	config = document.get("configurazione") or {}
	customer = document.get("assegnato_a_cliente") or {}
	timeline = document.get("logistica_timeline") or []
	last_step = timeline[-1] if timeline else None
	return {
		"id": str(document.get("_id")),
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
		"timeline": _normalize_timeline(timeline),
		"timeline_count": len(timeline),
		"arrival_date": _timeline_date(last_step),
		"arrival_date_iso": _iso_date(last_step.get("data") if last_step else None),
		"arrival_date_raw": last_step.get("data") if last_step else None,
		"public": document.get("stato_attuale") != "In Preparazione",
	}


def _vehicle_query(query: dict[str, Any] | None = None, public_only: bool = False) -> dict[str, Any]:
	criteria: dict[str, Any] = dict(query or {})
	if public_only:
		criteria["stato_attuale"] = {"$ne": "In Preparazione"}
	return criteria


def list_vehicles(
	query: dict[str, Any] | None = None,
	public_only: bool = False,
	limit: int | None = None,
	exclude_id: str | None = None,
) -> list[dict[str, Any]]:
	criteria = _vehicle_query(query=query, public_only=public_only)
	if exclude_id:
		criteria["_id"] = {"$ne": ObjectId(exclude_id)}
	documents = list(
		get_collection()
		.find(criteria)
		.sort([("marca", ASCENDING), ("modello", ASCENDING), ("vin_telaio", ASCENDING)])
	)
	vehicles = [normalize_vehicle(document) for document in documents]
	vehicles.sort(key=lambda vehicle: (vehicle["brand"], vehicle["modello"], vehicle["vin"]))
	if limit is not None:
		return vehicles[:limit]
	return vehicles


def get_vehicle_by_id(vehicle_id: str) -> dict[str, Any] | None:
	collection = get_collection()
	document = None
	if ObjectId.is_valid(vehicle_id):
		document = collection.find_one({"_id": ObjectId(vehicle_id)})
	if document is None:
		document = collection.find_one({"vin_telaio": vehicle_id})
	return normalize_vehicle(document) if document else None


def get_vehicle_document_by_id(vehicle_id: str) -> dict[str, Any] | None:
	collection = get_collection()
	document = None
	if ObjectId.is_valid(vehicle_id):
		document = collection.find_one({"_id": ObjectId(vehicle_id)})
	if document is None:
		document = collection.find_one({"vin_telaio": vehicle_id})
	return document


def upsert_vehicle_document(document: dict[str, Any], vehicle_id: str | None = None) -> str:
	collection = get_collection()
	if vehicle_id and ObjectId.is_valid(vehicle_id):
		collection.update_one({"_id": ObjectId(vehicle_id)}, {"$set": document})
		return vehicle_id
	result = collection.insert_one(document)
	return str(result.inserted_id)


def delete_vehicle_document(vehicle_id: str) -> bool:
	collection = get_collection()
	if ObjectId.is_valid(vehicle_id):
		result = collection.delete_one({"_id": ObjectId(vehicle_id)})
		return result.deleted_count > 0
	result = collection.delete_one({"vin_telaio": vehicle_id})
	return result.deleted_count > 0


def dashboard_summary() -> dict[str, int]:
	# Raggruppa i veicoli per stato e conta quanti ce ne sono in ciascuno.
	# Stesso schema visto a lezione: $group con _id su un campo + accumulatore $sum.
	pipeline = [
		{"$group": {"_id": "$stato_attuale", "count": {"$sum": 1}}},
	]
	counts = {row["_id"]: row["count"] for row in get_collection().aggregate(pipeline)}

	return {
		"total": sum(counts.values()),
		"ready": counts.get("Pronta per la consegna", 0) + counts.get("Arrivato in Concessionaria", 0),
		"in_transit": counts.get("In Viaggio", 0),
		"in_preparation": counts.get("In Preparazione", 0),
	}


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


def build_filter_options(vehicles: list[dict[str, Any]]) -> dict[str, list[str]]:
	return {
		"statuses": sorted({vehicle["status"] for vehicle in vehicles}),
		"brands": sorted({vehicle["brand"] for vehicle in vehicles}),
		"trims": sorted({vehicle["trim"] for vehicle in vehicles if vehicle["trim"] != "N/D"}),
	}


def build_calendar_events(vehicles: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
				"backgroundColor": {
					"Pronta per la consegna": "#5ee0a0",
					"Arrivato in Concessionaria": "#4f8cff",
					"In Viaggio": "#ffb347",
					"Ordinato in Fabbrica": "#8e9cff",
				}.get(vehicle["status"], "#9eb2cf"),
				"borderColor": "#ffffff22",
				"extendedProps": {
					"status": vehicle["status"],
					"vin": vehicle["vin"],
					"trim": vehicle["trim"],
				},
			}
		)
	return events