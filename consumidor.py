import pika
import json
from utils import evaluar_formula
import time

with open("config_modelo.json") as f:
    config = json.load(f)

def callback(ch, method, properties, body):
    escenario = json.loads(body)
    resultado = evaluar_formula(config["formula"], escenario)
    
    # Reenviar el resultado
    channel.basic_publish(
        exchange="",
        routing_key="cola_resultados",
        body=json.dumps({"resultado": resultado})
    )
    ch.basic_ack(delivery_tag=method.delivery_tag)

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host="localhost", credentials=pika.PlainCredentials("user", "pass"))
)
channel = connection.channel()
channel.queue_declare(queue="cola_escenarios")
channel.queue_declare(queue="cola_resultados")

channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue="cola_escenarios", on_message_callback=callback)
print("Esperando escenarios... Ctrl+C para salir.")
channel.start_consuming()


