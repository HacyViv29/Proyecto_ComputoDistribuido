import json
import pika
from utils import generar_escenario

with open("config_modelo.json") as f:
    config = json.load(f)

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host="localhost", credentials=pika.PlainCredentials("user", "pass"))
)
channel = connection.channel()
channel.queue_declare(queue="cola_escenarios")

for _ in range(config["num_simulaciones"]):
    escenario = generar_escenario(config)
    channel.basic_publish(
        exchange="",
        routing_key="cola_escenarios",
        body=json.dumps(escenario)
    )
print("Todos los escenarios enviados.")
connection.close()
