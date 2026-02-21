import asyncio
import json
import urllib.parse
import websockets

HOST = "172.20.10.2"
PORT = 8081

SENSORS = [
    "android.sensor.accelerometer",
    "android.sensor.gyroscope",
    # add more here:
    # "android.sensor.rotation_vector",
    # "android.sensor.magnetic_field",
]

def build_uri(host: str, port: int, sensors: list[str]) -> str:
    base = f"ws://{host}:{port}/sensors/connect?types="
    types_json = json.dumps(sensors)  # e.g. ["android.sensor.accelerometer","android.sensor.gyroscope"]
    return base + urllib.parse.quote(types_json, safe="")

async def run():
    uri = build_uri(HOST, PORT, SENSORS)
    print("Connecting to:", uri)

    # websockets>=11 uses 'open_timeout' etc; this works across common versions
    async with websockets.connect(uri) as ws:
        print("Connected.")

        async for message in ws:
            # SensorServer sends JSON messages
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                print("Non-JSON message:", message)
                continue

            # Typical fields per the wiki: type + values (+ timestamp, accuracy, etc.)
            sensor_type = data.get("type")
            values = data.get("values")
            ts = data.get("timestamp")  # may or may not exist depending on server settings

            print(f"type={sensor_type} values={values} timestamp={ts}")

if __name__ == "__main__":
    asyncio.run(run())