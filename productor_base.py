''''
    Productor de Escenarios de Simulación
    
    Este script es un productor de escenarios de montecarlo que envía un mensaje de resultados a RabbitMQ.
    ------------------------------------------------
        * Responsable de generar escenarios de simulación y enviarlos a RabbitMQ.
        * Un escenario consiste en un conjunto de valores para las variables aleatorias del modelo de Monte Carlo.
        * Utiliza un exchange directo para enviar mensajes a una cola específica.
        * Los mensajes son persistentes, lo que significa que sobrevivirán a reinicios del broker RabbitMQ.
    ------------------------------------------------
'''

import pika
import time
import json
import sys
from utils import generar_escenario
import uuid # Para generar IDs únicos para los escenarios

# Constantes para RabbitMQ
RABBITMQ_HOST = 'localhost'
EXCHANGE_NAME = 'simulacion_exchange' # Único exchange para la simulación
ESCENARIOS_QUEUE_NAME = 'escenarios_queue'
ESCENARIOS_ROUTING_KEY = 'escenario.nuevo' # Routing key para el exchange directo

# Configuración del modelo
MODEL = 'model_settings_flyweight.json' # Archivo de configuración del modelo

# Cargar la configuración del modelo desde un archivo JSON
# Este archivo contiene la definición de las variables y sus distribuciones.
try:
    with open(MODEL, "r") as f:
        model_settings = json.load(f)
except FileNotFoundError:
    print("Error: El archivo 'model_settings.json' no fue encontrado. Usando configuración por defecto.")
    # Configuración por defecto para evitar que el script falle si no existe el archivo
    model_settings = {
        "formula": "x + y",
        "variables": {
            "x": {"dist": "uniform", "params": {"low": 0, "high": 1}},
            "y": {"dist": "uniform", "params": {"low": 0, "high": 1}}
        }
    }

def iniciar_productor(num_mensajes=100):
    """
    Establece conexión con RabbitMQ, declara un exchange y una cola durable,
    y envía una cantidad especificada de mensajes persistentes.
    """
    try:
        #1. Establecer conexión con RabbitMQ
        connection_parameters = pika.ConnectionParameters(RABBITMQ_HOST)
        connection = pika.BlockingConnection(connection_parameters)
        channel = connection.channel()

        # 2. Declarar un exchange de tipo 'direct'
        # Los exchanges directos enrutan mensajes a colas basadas en la routing key.
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='direct', durable=True)

        # 3. Declarar una cola durable
        # durable=True asegura que la cola sobreviva a reinicios del broker RabbitMQ.
        channel.queue_declare(queue=ESCENARIOS_QUEUE_NAME, durable=True)

        # 4. Vincular la cola al exchange con la routing key
        channel.queue_bind(exchange=EXCHANGE_NAME, queue=ESCENARIOS_QUEUE_NAME, routing_key=ESCENARIOS_ROUTING_KEY)

        print(f"[*] Productor conectado y listo para enviar a la cola '{ESCENARIOS_QUEUE_NAME}' vía exchange '{EXCHANGE_NAME}'.")

        # 5. Enviar múltiples escenarios
        # Generar y enviar un número específico de escenarios 
        for i in range(num_mensajes):
            id_escenario = str(uuid.uuid4()) # Generar un ID único para el escenario

            datos_escenario = generar_escenario(model_settings)
            
            mensaje_escenario = {
                "id_escenario": id_escenario,
                "datos_variables": datos_escenario
            }

            # Publicar el mensaje al exchange especificado con la routing key
            # El exchange se encargará de enviarlo a las colas vinculadas con esa routing key.
            channel.basic_publish(
                exchange=EXCHANGE_NAME,
                routing_key=ESCENARIOS_ROUTING_KEY, # La routing key que usa el exchange para dirigir el mensaje
                body=json.dumps(mensaje_escenario), # Convertir el escenario a JSON
                properties=pika.BasicProperties(
                    delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE # Hace el mensaje persistente
                )
            )
            #print(f" [x] Productor: Enviado Escenario ID: {id_escenario} | Datos: {datos_escenario}")
            print(f" [x] Productor: Enviado Escenario ID: {id_escenario}")
            time.sleep(0.5) # Pequeña pausa entre mensajes
        print(f"[x] Productor: {num_mensajes} escenarios enviados.")

    except pika.exceptions.AMQPConnectionError as e:
        print(f"Error al conectar con RabbitMQ: {e}")
        print("Asegúrate de que el contenedor RabbitMQ esté corriendo y los puertos estén correctamente mapeados.")
    except Exception as e:
        print(f"Ocurrió un error inesperado en el productor: {e}")
    finally:
        # Cerrar la conexión
        if 'connection' in locals() and connection.is_open:
            connection.close()
            print("[x] Todos los escenarios enviados.")
            print("[-] Conexión del productor cerrada.")

if __name__ == '__main__':
    # Esperar un momento para asegurar que RabbitMQ esté completamente iniciado
    print("[-] Productor esperando 5 segundos para que RabbitMQ inicie...")
    time.sleep(5)

    # Permitir especificar el número de mensajes desde la línea de comandos
    if len(sys.argv) > 1:
        try:
            n_msgs = int(sys.argv[1])
        except ValueError:
            print("[-] Argumento inválido. Usando n mensajes por defecto.")

    iniciar_productor(n_msgs)
