import pika
import json
import matplotlib.pyplot as plt

resultados = []

def callback(ch, method, properties, body):
    global resultados
    resultado = json.loads(body)["resultado"]
    resultados.append(resultado)
    
    if len(resultados) % 50 == 0:
        plt.clf()
        plt.hist(resultados, bins=30, color='blue', alpha=0.7)
        plt.title(f"Histograma de resultados ({len(resultados)} muestras)")
        plt.pause(0.01)
    ch.basic_ack(delivery_tag=method.delivery_tag)

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host="localhost", credentials=pika.PlainCredentials("user", "pass"))
)
channel = connection.channel()
channel.queue_declare(queue="cola_resultados")

plt.ion()
plt.figure()

channel.basic_consume(queue="cola_resultados", on_message_callback=callback)
print("Visualizador en ejecución...")
channel.start_consuming()


