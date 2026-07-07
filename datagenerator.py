import random
from faker import Faker
from datetime import datetime, timedelta
from pymongo import MongoClient

# Inizializza Faker in italiano
fake = Faker('it_IT')

# 1. STRINGA DI CONNESSIONE (Sostituiscila con la tua di MongoDB Atlas)
MONGO_URI = "mongodb://localhost:27017/"
client = MongoClient(MONGO_URI)
db = client['db_veicoli']
veicoli_collection = db['vehicles']

# 2. DIZIONARIO ESCLUSIVO RENAULT
modelli_renault = [
    {
        "modello": "Rafale", 
        "motori": ["E-Tech Full Hybrid 200", "E-Tech 4x4 300 hp"], 
        "elettrica": False,
        "allestimenti": ["Techno", "Esprit Alpine"]
    },
    {
        "modello": "Scenic E-Tech", 
        "motori": ["170 cv Comfort Range", "220 cv Long Range"], 
        "elettrica": True,
        "allestimenti": ["Evolution", "Techno", "Esprit Alpine", "Iconic"]
    },
    {
        "modello": "Clio", 
        "motori": ["TCe 90", "E-Tech Full Hybrid 145", "Blue dCi 100"], 
        "elettrica": False,
        "allestimenti": ["Evolution", "Techno", "Esprit Alpine"]
    }
]

colori = ["Rosso Passion", "Nero Etoile", "Grigio Scisto", "Bianco Ghiaccio", "Blu Summit", "Blu Iron"]
stati_possibili = ["Ordinato in Fabbrica", "In Viaggio", "Arrivato in Concessionaria", "In Preparazione", "Pronta per la consegna"]
lista_venditori = ["Alessandro Bianchi", "Laura Rossi", "Marco Neri", "Sofia Verdi"]

pacchetti_base = ["Climatizzatore Manuale", "Fari Full LED", "Sensori di parcheggio posteriori", "Cruise Control"]
pacchetti_avanzati = ["4Control Advanced", "Cerchi in lega da 20'' Castellet", "Harman Kardon Premium Sound", "Pack Advanced Driving Assist"]
pacchetti_extra = ["Solarbay (Tetto panoramico opacizzabile)", "Head-up Display 9,3''", "Pompa di calore", "Sensori anteriori e retrocamera"]

# 3. FUNZIONE DI GENERAZIONE
def genera_veicolo():
    auto_scelta = random.choice(modelli_renault)
    allestimento_scelto = random.choice(auto_scelta["allestimenti"])
    motore_scelto = random.choice(auto_scelta["motori"])
    stato_attuale_idx = random.randint(0, len(stati_possibili) - 1)
    
    # Assegnazione logica dei pacchetti in base all'allestimento
    if allestimento_scelto in ["Esprit Alpine", "Iconic"]:
        p_inclusi = random.sample(pacchetti_avanzati, k=random.randint(1, 3))
    else:
        p_inclusi = random.sample(pacchetti_base, k=random.randint(1, 3))
        
    p_aggiuntivi = random.sample(pacchetti_extra, k=random.randint(0, 2))
    
    # Generazione di un VIN plausibile (i telai Renault iniziano spesso con VF1)
    vin_simulato = "VF1" + fake.pystr(min_chars=14, max_chars=14).upper()
    
    veicolo = {
        "vin_telaio": vin_simulato,
        "marca": "Renault",
        "modello": auto_scelta["modello"],
        "stato_attuale": stati_possibili[stato_attuale_idx],
        "venditore": random.choice(lista_venditori),
        "assegnato_a_cliente": {
            "id_cliente": f"CUST-{random.randint(1000, 9999)}",
            "nome": fake.name(),
            "email": fake.email(),
            "numero_telefono": fake.phone_number()
        },
        "configurazione": {
            "allestimento": allestimento_scelto,
            "motorizzazione": motore_scelto,
            "colore_esterno": random.choice(colori),
            "pacchetti_inclusi": p_inclusi,
            "pacchetti_aggiuntivi": p_aggiuntivi
        },
        "logistica_timeline": []
    }

    # Gestione dinamica attributi auto elettriche (Polymorphic Pattern)
    if auto_scelta["elettrica"]:
        veicolo["configurazione"]["capacita_batteria_kw"] = 87 if "220" in motore_scelto else 60
        veicolo["configurazione"]["cavo_ricarica_incluso"] = True

    # 4. GENERAZIONE TIMELINE
    data_evento = datetime.now() - timedelta(days=random.randint(30, 90))
    
    for i in range(stato_attuale_idx + 1):
        veicolo["logistica_timeline"].append({
            "stato": stati_possibili[i],
            "data": data_evento,
            "operatore": "Sistema" if i == 0 else fake.first_name()
        })
        data_evento += timedelta(days=random.randint(2, 10))

    return veicolo

# 5. ESECUZIONE
if __name__ == "__main__":
    NUMERO_VEICOLI = 150
    print(f"Generazione di {NUMERO_VEICOLI} veicoli Renault in corso...")
    
    dati_da_inserire = [genera_veicolo() for _ in range(NUMERO_VEICOLI)]
    
    # Svuota la collezione per evitare accavallamenti durante i test
    veicoli_collection.drop() 
    
    risultato = veicoli_collection.insert_many(dati_da_inserire)
    
    print(f"✅ Database popolato! Inseriti {len(risultato.inserted_ids)} veicoli Renault.")