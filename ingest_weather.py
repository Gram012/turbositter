import argparse
import json
import os
import sys
from typing import Any, Dict, Optional

import psycopg2
from psycopg2.extras import execute_values

SCHEMA = "turbositter"
TABLE = "mro_weather"

VALUE_MAP = {
    "averageperiod": "avgperiod",
    "cloudcover": "cloudcover",
    "dewpoint": "dewpoint",
    "humidity": "humidity",
    "pressure": "pressure",
    "rainrate": "rainrate",
    "skybrightness": "skybrightness",
    "skyquality": "skyquality",      
    "skytemperature": "skytemp",
    "starfwhm": "starfwhm",
    "temperature": "temperature",
    "winddirection": "winddirection",
    "windgust": "windgust",
    "windspeed": "windspeed",
}

COLS = [
    "clienttransactionid",
    "servertransactionid",
    "errornumber",
    "errormessage",
    "avgperiod",
    "cloudcover",
    "dewpoint",
    "humidity",
    "pressure",
    "rainrate",
    "skybrightness",
    "skyquality",        
    "skytemp",
    "starfwhm",
    "temperature",
    "winddirection",
    "windgust",
    "windspeed",
]

def connect2db():
    try:
        return psycopg2.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5432"),
            dbname=os.environ.get("PGDATABASE", "turbo"),
            user=os.environ.get("PGUSER", "turbo"),
            password=os.environ.get("PGPASSWORD", "TURBOTURBO"),
        )
    except Exception as e:
        print(f"ERROR: Could not connect to Postgres: {e}", file=sys.stderr)
        sys.exit(2)

def typeSafeCheck(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None

def build_row(doc: Dict[str, Any]) -> list:
    #Metadata
    client_tx = typeSafeCheck(doc.get("ClientTransactionID"))
    server_tx = typeSafeCheck(doc.get("ServerTransactionID"))
    err_num = typeSafeCheck(doc.get("ErrorNumber"))
    err_msg = doc.get("ErrorMessage", "")

    #Sensor data
    val = doc.get("Value", {}) or {}
    mapped = {dst: typeSafeCheck(val.get(src)) for src, dst in VALUE_MAP.items()}

    return [
        client_tx,
        server_tx,
        err_num,
        err_msg,
        mapped["avgperiod"],
        mapped["cloudcover"],
        mapped["dewpoint"],
        mapped["humidity"],
        mapped["pressure"],
        mapped["rainrate"],
        mapped["skybrightness"],
        mapped["skyquality"],
        mapped["skytemp"],
        mapped["starfwhm"],
        mapped["temperature"],
        mapped["winddirection"],
        mapped["windgust"],
        mapped["windspeed"],
    ]

def main():
    ap = argparse.ArgumentParser(description="Ingest weather JSON into Postgres")
    ap.add_argument("file", help="Path to input JSON file")
    args = ap.parse_args()

    try:
        with open(args.file, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"ERROR: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    row = build_row(doc)
    if len(row) != len(COLS):
        print(f"ERROR: Column/value count mismatch: {len(COLS)} columns vs {len(row)} values", file=sys.stderr)
        sys.exit(1)

    conn = connect2db()
    try:
        col_list = ", ".join(COLS)
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"INSERT INTO {SCHEMA}.{TABLE} ({col_list}) VALUES %s",
                [tuple(row)],
            )
        conn.commit()
        print("Insert OK")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
