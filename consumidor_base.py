''''
    Consumidor de Escenarios de Simulación
    
    Este script es un consumidor de escenarios de simulación que recibe mensajes de RabbitMQ y publica resultados.
    ------------------------------------------------
        * Responsable de recibir escenarios de simulación y calcular resultados.
        * Utiliza un exchange directo para recibir mensajes de una cola específica.
        * Publica resultados en el mismo exchange pero con una routing key diferente.
        * También publica resultados en un exchange fanout para el visualizador.
    ------------------------------------------------
'''

import pika
import time
import os # Para obtener el PID
import json

from utils import evaluar_formula

# Constantes para RabbitMQ (deben coincidir con el productor)
RABBITMQ_HOST = 'localhost'
EXCHANGE_NAME = 'simulacion_exchange' # Único exchange para la simulación

# Cola y routing key para el consumidor
ESCENARIOS_QUEUE_NAME = 'escenarios_queue'
ESCENARIOS_ROUTING_KEY = 'escenario.nuevo' # Necesario si el consumidor también declara y vincula la cola

# Nueva cola y routing key para resultados
RESULTADOS_QUEUE_NAME = 'resultados_queue'
RESULTADOS_ROUTING_KEY = 'resultado.procesado' # Nueva routing key para resultados

# Exhange fanout sin routing key
DASHBOARD_EXCHANGE = 'dashboard_exchange' # Exchange para el visualizador

MODEL = 'model_settings_flyweight.json' # Archivo de configuración del modelo

# Cargar la configuración del modelo para obtener la fórmula
try:
    with open(MODEL, "r") as f:
        model_settings = json.load(f)
    formula_modelo = model_settings["formula"]
except FileNotFoundError:
    print("Error: El archivo 'model_settings.json' no fue encontrado. Usando fórmula por defecto 'x+y+z'.")
    formula_modelo = "x + y + z" # Fórmula por defecto
except KeyError:
    print("Error: 'formula' no encontrada en 'model_settings.json'. Usando fórmula por defecto 'x+y+z'.")
    formula_modelo = "x + y + z"

def callback_consumidor(ch, method, properties, body):
    """
    Procesa un escenario recibido, calcula el resultado y lo publica.
    """
    pid = os.getpid()
    try:
        escenario_recibido = json.loads(body.decode())
        id_escenario = escenario_recibido.get("id_escenario", "ID_DESCONOCIDO")
        datos_variables = escenario_recibido.get("datos_variables", {})

        print(f" [C:{pid}] Recibido Escenario ID: {id_escenario} | Datos: {datos_variables}")

        # Calcular el resultado usando la fórmula del modelo
        resultado_calculado = evaluar_formula(formula_modelo, datos_variables)
        
        print(f" [C:{pid}] Escenario ID: {id_escenario} | Resultado: {resultado_calculado}")

        # Preparar mensaje de resultado
        mensaje_resultado = {
            "id_escenario": id_escenario,
            "valor_calculado": resultado_calculado
        }

        # Publicar el resultado al mismo exchange pero con la routing key de resultados
        ch.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=RESULTADOS_ROUTING_KEY,
            body=json.dumps(mensaje_resultado),
            # properties=pika.BasicProperties(
            #     delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE # Si resultados_queue es durable
            # )
        )
        print(f" [C:{pid}] Resultado para Escenario ID: {id_escenario} publicado en '{RESULTADOS_QUEUE_NAME}'.")
        
        # Publicar el resultado en el exchange del dashboard
        ch.basic_publish(
            exchange=DASHBOARD_EXCHANGE,
            routing_key='',  # fanout no usa routing key
            body=json.dumps(mensaje_resultado)
        )
        print(f" [C:{pid}] Resultado reenviado a '{DASHBOARD_EXCHANGE}' para dashboard.")

        # Enviar ACK para el mensaje de escenario original
        ch.basic_ack(delivery_tag=method.delivery_tag)
        # print(f" [C:{pid}] ACK enviado para Escenario ID: {id_escenario}")

    except json.JSONDecodeError:
        print(f" [C:{pid}] Error al decodificar JSON: {body.decode()}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False) # Rechazar mensaje si no se puede procesar
    except Exception as e:
        print(f" [C:{pid}] Error procesando mensaje ID {id_escenario if 'id_escenario' in locals() else 'DESCONOCIDO'}: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False) # Rechazar en caso de otros errores


def iniciar_consumidor():

    """
    Establece conexión con RabbitMQ, declara la cola (idempotente),
    y comienza a consumir mensajes.
    """

    pid = os.getpid()
    connection = None
    try:
        # 1. Establecer conexión con RabbitMQ
        connection_parameters = pika.ConnectionParameters(RABBITMQ_HOST)
        connection = pika.BlockingConnection(connection_parameters)
        channel = connection.channel()

        # 2. Declarar el exchange (idempotente, debe coincidir con el productor) principal y para el visualizador
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='direct', durable=True)
        channel.exchange_declare(exchange=DASHBOARD_EXCHANGE, exchange_type='fanout', durable=True) #Exchange para el visualizador

        # 3. Declarar y vincular la cola de escenarios
        channel.queue_declare(queue=ESCENARIOS_QUEUE_NAME, durable=True)
        channel.queue_bind(exchange=EXCHANGE_NAME, queue=ESCENARIOS_QUEUE_NAME, routing_key=ESCENARIOS_ROUTING_KEY)
        
        # 4. Declarar y vincular la cola de resultados
        channel.queue_declare(queue=RESULTADOS_QUEUE_NAME, durable=True) # Será consumida por el visualizador
        channel.queue_bind(exchange=EXCHANGE_NAME, queue=RESULTADOS_QUEUE_NAME, routing_key=RESULTADOS_ROUTING_KEY)

        print(f" [C:{pid}] Consumidor conectado. Exchange '{EXCHANGE_NAME}', consumiendo de '{ESCENARIOS_QUEUE_NAME}', publicando a '{RESULTADOS_QUEUE_NAME}'.")

        # Esto le dice a RabbitMQ que no envíe más de un mensaje a este worker a la vez.
#       # El worker no recibirá un nuevo mensaje hasta que haya procesado y acusado el anterior.
#       # Ayuda a distribuir la carga de manera más uniforme entre múltiples consumidores.
        channel.basic_qos(prefetch_count=1)

        # 5. Especificar la función de callback para consumir mensajes de la cola
        channel.basic_consume(queue=ESCENARIOS_QUEUE_NAME, on_message_callback=callback_consumidor)

        print(f" [C:{pid}] [*] Esperando escenarios. Para salir presione CTRL+C")
        channel.start_consuming()

    except pika.exceptions.AMQPConnectionError as e:
        print(f" [C:{pid}] Error de conexión con RabbitMQ (Consumidor): {e}")
        time.sleep(5)
    except KeyboardInterrupt:
        print(f" [C:{pid}] Consumo interrumpido.")
    except Exception as e:
        print(f" [C:{pid}] Ocurrió un error inesperado en el consumidor: {e}")
    finally:
        if connection and connection.is_open:
            connection.close()
            print(f" [C:{pid}] Conexión del consumidor cerrada.")

if __name__ == '__main__':
    iniciar_consumidor()
