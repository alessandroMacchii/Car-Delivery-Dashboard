from datetime import datetime

from flask import Flask, abort, redirect, render_template, request, url_for

from mongo_repository import (
	build_calendar_events,
	build_filter_options,
	dashboard_summary,
	delete_vehicle_document,
	featured_vehicles,
	format_date,
	get_vehicle_document_by_id,
	get_vehicle_by_id,
	list_vehicles,
	upsert_vehicle_document,
)


app = Flask(__name__)


@app.context_processor
def inject_helpers():
	return {"format_date": format_date}


def _split_multiline(value):
	return [item.strip() for item in value.splitlines() if item.strip()]


def _build_vehicle_document(form, existing_document=None):
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

	status = form.get("stato_attuale", "").strip()
	timeline = list((existing_document or {}).get("logistica_timeline") or [])
	timeline_status = form.get("timeline_stato", "").strip()
	timeline_date = form.get("timeline_data", "").strip()
	timeline_operator = form.get("timeline_operatore", "").strip() or form.get("venditore", "").strip() or "Sistema"

	if timeline_status and timeline_date:
		timeline.append(
			{
				"stato": timeline_status,
				"data": datetime.fromisoformat(timeline_date),
				"operatore": timeline_operator,
			}
		)
	elif existing_document is None:
		timeline.append(
			{
				"stato": status,
				"data": datetime.utcnow(),
				"operatore": timeline_operator,
			}
		)
	elif existing_document.get("stato_attuale") != status:
		timeline.append(
			{
				"stato": status,
				"data": datetime.utcnow(),
				"operatore": timeline_operator,
			}
		)

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


def _vehicle_form_defaults(vehicle):
	vehicle = vehicle or {}
	configuration = vehicle.get("configurazione") or {}
	customer = vehicle.get("assegnato_a_cliente") or {}
	return {
		"vin_telaio": vehicle.get("vin", ""),
		"marca": vehicle.get("brand", ""),
		"modello": vehicle.get("modello", ""),
		"stato_attuale": vehicle.get("status", ""),
		"venditore": vehicle.get("seller", ""),
		"id_cliente": customer.get("id_cliente", ""),
		"nome_cliente": customer.get("nome", ""),
		"email_cliente": customer.get("email", ""),
		"telefono_cliente": customer.get("numero_telefono", ""),
		"allestimento": configuration.get("allestimento", ""),
		"motorizzazione": configuration.get("motorizzazione", ""),
		"colore_esterno": configuration.get("colore_esterno", ""),
		"pacchetti_inclusi": "\n".join(configuration.get("pacchetti_inclusi", [])),
		"pacchetti_aggiuntivi": "\n".join(configuration.get("pacchetti_aggiuntivi", [])),
		"capacita_batteria_kw": configuration.get("capacita_batteria_kw", ""),
		"cavo_ricarica_incluso": configuration.get("cavo_ricarica_incluso", False),
		"timeline_stato": "",
		"timeline_data": "",
		"timeline_operatore": vehicle.get("seller", ""),
	}


@app.route("/")
def home():
	summary = dashboard_summary()
	featured = featured_vehicles(limit=3)
	return render_template(
		"home.html",
		title="Home",
		featured=featured,
		fleet_count=summary["total"],
		ready_count=summary["ready"],
		transit_count=summary["in_transit"],
		preparation_count=summary["in_preparation"],
	)


@app.route("/gestione-auto")
def gestione_auto():
	vehicles = list_vehicles()
	filters = build_filter_options(vehicles)
	return render_template(
		"gestione_auto.html",
		title="Gestione auto",
		cars=vehicles,
		calendar_events=build_calendar_events(vehicles),
		status_options=filters["statuses"],
		brand_options=filters["brands"],
		trim_options=filters["trims"],
	)


@app.route("/catalogo")
def catalogo():
	public_cars = list_vehicles(public_only=True)
	filters = build_filter_options(public_cars)
	return render_template(
		"catalogo.html",
		title="Catalogo",
		cars=public_cars,
		brand_options=filters["brands"],
		trim_options=filters["trims"],
		status_options=filters["statuses"],
	)


@app.route("/auto/<car_id>")
def auto_dettaglio(car_id):
	car = get_vehicle_by_id(car_id)
	if car is None:
		abort(404)

	related = list_vehicles(
		query={"marca": car["brand"]},
		limit=3,
		exclude_id=car["id"],
	)
	return render_template(
		"auto_dettaglio.html",
		title=f"{car['brand']} {car['modello']}",
		car=car,
		related=related,
		vehicle_form=_vehicle_form_defaults(car),
		is_new=False,
	)


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


@app.route("/auto/nuova", methods=["GET", "POST"])
def auto_nuova():
	if request.method == "POST":
		vehicle_document = _build_vehicle_document(request.form)
		new_id = upsert_vehicle_document(vehicle_document)
		return redirect(url_for("auto_dettaglio", car_id=new_id))

	return render_template(
		"auto_dettaglio.html",
		title="Nuova auto",
		car={
			"brand": "",
			"modello": "",
			"status": "",
			"vin": "",
			"timeline": [],
			"timeline_count": 0,
			"arrival_date": "N/D",
			"motorizzazione": "",
			"trim": "",
			"color": "",
			"seller": "",
			"customer_name": "",
			"customer_email": "",
			"customer_phone": "",
			"battery_kwh": "",
			"charging_cable": False,
		},
		related=[],
		vehicle_form=_vehicle_form_defaults({}),
		is_new=True,
	)


if __name__ == "__main__":
	app.run(debug=True)
