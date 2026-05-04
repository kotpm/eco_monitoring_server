from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import sqlite3
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Eco Monitoring Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "eco_monitoring.db"


class SensorData(BaseModel):
    device_id: str = "lolin32_01"
    gas: int
    dust: int
    temp: float
    hum: float


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            gas INTEGER NOT NULL,
            dust INTEGER NOT NULL,
            temp REAL NOT NULL,
            hum REAL NOT NULL,
            air_index REAL NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def normalize(value, min_value, max_value):
    if value < min_value:
        return 0
    if value > max_value:
        return 1
    return (value - min_value) / (max_value - min_value)


def calculate_air_index(gas, dust, temp, hum):
    gas_norm = normalize(gas, 0, 4095)
    dust_norm = normalize(dust, 0, 4095)

    temp_dev = abs(temp - 22) / 20
    hum_dev = abs(hum - 50) / 50

    temp_dev = min(temp_dev, 1)
    hum_dev = min(hum_dev, 1)

    air_index = (
        0.4 * gas_norm +
        0.4 * dust_norm +
        0.1 * temp_dev +
        0.1 * hum_dev
    )

    return round(air_index, 3)


def define_status(air_index):
    if air_index <= 0.25:
        return "добрий"
    elif air_index <= 0.50:
        return "задовільний"
    elif air_index <= 0.75:
        return "забруднений"
    else:
        return "небезпечний"


@app.on_event("startup")
def startup():
    init_db()


@app.get("/dashboard")
def dashboard():
    return FileResponse("index.html")


@app.post("/data")
def receive_data(data: SensorData):
    air_index = calculate_air_index(
        data.gas,
        data.dust,
        data.temp,
        data.hum
    )

    status = define_status(air_index)

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO measurements 
        (device_id, gas, dust, temp, hum, air_index, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.device_id,
        data.gas,
        data.dust,
        data.temp,
        data.hum,
        air_index,
        status,
        datetime.now().isoformat(timespec="seconds")
    ))

    conn.commit()
    conn.close()

    return {
        "saved": True,
        "air_index": air_index,
        "status": status
    }


@app.get("/data/latest")
def get_latest():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, device_id, gas, dust, temp, hum, air_index, status, created_at
        FROM measurements
        ORDER BY id DESC
        LIMIT 1
    """)

    row = cur.fetchone()
    conn.close()

    if row is None:
        return {"message": "Даних ще немає"}

    return {
        "id": row[0],
        "device_id": row[1],
        "gas": row[2],
        "dust": row[3],
        "temp": row[4],
        "hum": row[5],
        "air_index": row[6],
        "status": row[7],
        "created_at": row[8]
    }


@app.get("/data/history")
def get_history(limit: int = 50):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, device_id, gas, dust, temp, hum, air_index, status, created_at
        FROM measurements
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "device_id": row[1],
            "gas": row[2],
            "dust": row[3],
            "temp": row[4],
            "hum": row[5],
            "air_index": row[6],
            "status": row[7],
            "created_at": row[8]
        }
        for row in rows
    ]