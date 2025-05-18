import pika
import json
import matplotlib.pyplot as plt
import time
import os

# Constantes para RabbitMQ (deben coincidir con el consumidor)
RABBITMQ_HOST = 'localhost'
EXCHANGE_NAME = 'simulacion_exchange' # Mismo exchange que usa el productor y consumidor

# Cola y routing key para el visualizador
RESULTADOS_QUEUE_NAME = 'resultados_queue'
RESULTADOS_ROUTING_KEY = 'resultado.procesado' # Routing key para los mensajes de resultados

# Lista global para almacenar los resultados recibidos
resultados_simulacion = []
fig, ax = plt.subplots() # Crear figura y ejes una sola vez
plt.ion() # Activar modo interactivo de matplotlib

def actualizar_histograma():
    """
    Limpia y redibuja el histograma con los resultados actuales.
    """
    ax.clear() # Limpiar los ejes anteriores
    if resultados_simulacion:
        ax.hist(resultados_simulacion, bins=30, color='skyblue', alpha=0.7, edgecolor='black')
    ax.set_title(f"Histograma de Resultados ({len(resultados_simulacion)} muestras)")
    ax.set_xlabel("Valor del Resultado")
    ax.set_ylabel("Frecuencia")
    plt.tight_layout() # Ajustar layout para que no se corten los títulos
    plt.draw() # Redibujar la figura
    plt.pause(0.01) # Pausa breve para permitir que la GUI se actualice

def callback_visualizador(ch, method, properties, body):
    """
    Función que se ejecuta cuando se recibe un mensaje de resultado.
    Decodifica el mensaje, extrae el resultado, lo añade a la lista
    y actualiza el histograma periódicamente.
    """
    global resultados_simulacion
    pid = os.getpid() # debugging flag(múltiples visualizadores)

    try:
        mensaje_recibido = json.loads(body.decode())
        id_escenario = mensaje_recibido.get("id_escenario", "ID_DESCONOCIDO")
        valor_calculado = mensaje_recibido.get("valor_calculado")

        if valor_calculado is not None:
            print(f" [V:{pid}] Resultado Recibido - Escenario ID: {id_escenario}, Valor: {valor_calculado:.2f}")
            resultados_simulacion.append(valor_calculado)

            # Actualizar el histograma cada N resultados para no sobrecargar
            if len(resultados_simulacion) % 10 == 0 or len(resultados_simulacion) == 1:
                actualizar_histograma()
        else:
            print(f" [V:{pid}] Mensaje recibido no contenía 'valor_calculado': {mensaje_recibido}")

        # Enviar ACK para el mensaje de resultado
        # Esto es importante para confirmar que el mensaje fue procesado correctamente
        # y evitar que se reenvíe en caso de error.
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError:
        print(f" [V:{pid}] Error al decodificar JSON del resultado: {body.decode()}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False) # No reencolar mensajes malformados
    except Exception as e:
        print(f" [V:{pid}] Error procesando resultado (ID: {id_escenario if 'id_escenario' in locals() else 'N/A'}): {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def iniciar_visualizador():
    """
    Establece conexión con RabbitMQ, declara exchange, cola, binding
    y comienza a consumir mensajes de resultados.
    """
    pid = os.getpid()
    connection = None
    print(f" [V:{pid}] Iniciando visualizador...")

    try:
        # Ajuste de credenciales:
        credentials = pika.PlainCredentials('guest', 'guest') # Credenciales por defecto de RabbitMQ
        connection_parameters = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            credentials=credentials
        )

        connection = pika.BlockingConnection(connection_parameters)
        channel = connection.channel()

        # Declarar el exchange (idempotente, debe coincidir con productor/consumidor)
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='direct', durable=True)

        # Declarar la cola de resultados (durable)
        channel.queue_declare(queue=RESULTADOS_QUEUE_NAME, durable=True)
        
        # Vincular la cola de resultados al exchange con la routing key de resultados
        channel.queue_bind(
            exchange=EXCHANGE_NAME,
            queue=RESULTADOS_QUEUE_NAME,
            routing_key=RESULTADOS_ROUTING_KEY
        )

        print(f" [V:{pid}] Visualizador conectado. Exchange '{EXCHANGE_NAME}', consumiendo de '{RESULTADOS_QUEUE_NAME}' (RK: '{RESULTADOS_ROUTING_KEY}').")

        # Configurar el consumo de mensajes
        channel.basic_consume(
            queue=RESULTADOS_QUEUE_NAME,
            on_message_callback=callback_visualizador
        )

        print(f" [V:{pid}] [*] Esperando resultados. La gráfica se actualizará periódicamente.")
        print(f" [V:{pid}] Para salir presione CTRL+C en esta terminal.")
        
        # Mostrar la figura inicialmente vacía
        actualizar_histograma() 
        
        channel.start_consuming() # Bucle

    except pika.exceptions.AMQPConnectionError as e:
        print(f" [V:{pid}] Error de conexión con RabbitMQ (Visualizador): {e}")
        print(f" [V:{pid}] Asegúrate de que RabbitMQ esté corriendo en {RABBITMQ_HOST} y accesible.")
        print(f" [V:{pid}] Si usas Docker, verifica que el contenedor esté activo y los puertos mapeados.")
        time.sleep(5)
    except KeyboardInterrupt:
        print(f" [V:{pid}] Visualización interrumpida por el usuario.")
    except Exception as e:
        print(f" [V:{pid}] Ocurrió un error inesperado en el visualizador: {e}")
    finally:
        if connection and connection.is_open:
            connection.close()
            print(f" [V:{pid}] Conexión del visualizador cerrada.")
        plt.ioff()
        plt.show()
        print(f" [V:{pid}] Visualizador finalizado.")

if __name__ == '__main__':
    iniciar_visualizador()
