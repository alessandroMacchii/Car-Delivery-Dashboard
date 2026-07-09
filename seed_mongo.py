from __future__ import annotations

import argparse
from pathlib import Path

from bson import json_util
from pymongo import ReplaceOne

from mongo_repository import collection


def load_documents(file_path: Path) -> list[dict]:
	with file_path.open("r", encoding="utf-8") as handle:
		return json_util.loads(handle.read())


def main() -> None:
	parser = argparse.ArgumentParser(description="Importa il JSON delle auto in MongoDB")
	parser.add_argument("--file", required=True, help="Percorso del file JSON da importare")
	parser.add_argument("--drop", action="store_true", help="Svuota la collection prima dell'import")
	args = parser.parse_args()

	file_path = Path(args.file).resolve()
	documents = load_documents(file_path)

	if args.drop:
		collection.drop()

	operations = [ReplaceOne({"_id": document["_id"]}, document, upsert=True) for document in documents]
	result = collection.bulk_write(operations, ordered=False)
	print(f"Import completato: upsert={result.upserted_count}, modified={result.modified_count}")


if __name__ == "__main__":
	main()