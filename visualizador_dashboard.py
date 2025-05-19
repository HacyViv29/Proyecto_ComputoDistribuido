''''
    Visualizador de Resultados de Simulación
    Este script es un visualizador de resultados de las simulaciones de montecarlo en un Dashboard.

    ------------------------------------------------
        * Responsable de generar un Dashboard donde se aprecie los resultados de las simulaciones.
        * Enseña el número de simulaciones realizadas, el promedio de los resultados y un histograma de los resultados.
    ------------------------------------------------
'''

#Importaci[on de librerias necesarias
import dash
from dash import dcc, html
from dash.dependencies import Output, Input
import plotly.express as px
import pika
import json
import threading
import pandas as pd
import webbrowser
from threading import Timer
import os
import numpy as np
from scipy.stats import kurtosis, skew

#Parámetros de configuración
RABBITMQ_HOST = 'localhost' # Host de RabbitMQ
DASHBOARD_EXCHANGE = 'dashboard_exchange' # Exchange para el dashboard
#MODEL_SETTINGS_FILE = 'model_settings_flyweight.json' # Archivo de configuración del modelo

#Inicializar la app Dash
app = dash.Dash(__name__)

# Diseño de la interfaz del dashboard
# Se utiliza un diseño simple con un título, un gráfico y un botón de reinicio
app.layout = html.Div([
    html.H1("📊 Dashboard de Simulaciones en Tiempo Real 🧮"), # Titulo
    
    # Estadisticas generales
    html.Div(id="fórmula", style={"fontSize": 20, "margin": "10px", "fontStyle": "italic"}),
    
    # Sección creada para darle un mejor diseño a las estadísticas 
    html.Div([
        html.Div(id="numero-simulaciones", style={"fontSize": 24, "margin": "10px"}),
        html.Div(id="promedio-simulaciones", style={"fontSize": 24, "margin": "10px"}),
        html.Div(id="mediana-simulaciones", style={"fontSize": 24, "margin": "10px"}),
        html.Div(id="desviacion-simulaciones", style={"fontSize": 24, "margin": "10px"}),
        html.Div(id="minimo-simulaciones", style={"fontSize": 24, "margin": "10px"}),
        html.Div(id="maximo-simulaciones", style={"fontSize": 24, "margin": "10px"}),
        html.Div(id="percentiles-simulaciones", style={"fontSize": 24, "margin": "10px"}),
        html.Div(id="varianza", style={"fontSize": 24, "margin": "10px"}),
        html.Div(id="asimetria", style={"fontSize": 24, "margin": "10px"}),
        html.Div(id="curtosis", style={"fontSize": 24, "margin": "10px"}),
    ], style={
        "display": "grid",
        "gridTemplateColumns": "repeat(3, 1fr)",
        "gap": "10px 20px", # Espacio entre columnas y filas
        "margin": "10px",
    }),
    
    # Histograma de resultados
    dcc.Graph(id="histograma"),
    
    # Botón para reiniciar el dashboard
    html.Button("🔄 Reiniciar Dashboard", id="boton-reiniciar", n_clicks=0, style={"margin": "20px"}),
    
    #Intervalo para actualizar el dashboard
    # Se utiliza un intervalo para actualizar el dashboard cada 2 segundos
    dcc.Interval(id="intervalo-actualizacion", interval=2000, n_intervals=0)  # Actualizar cada 2 segundos
])

# Lista para almacenar los resultados de las simulaciones
resultados = []
formula = ""

# Función para cargar la fórmula del modelo desde un archivo JSON
# Se espera que el archivo contenga una clave "formula" con la fórmula a utilizar
# def cargar_formula():
#     try:
#         with open(MODEL_SETTINGS_FILE, 'r') as f:
#             settings = json.load(f)
#         return settings.get("formula", "Fórmula no encontrada") # Devuelve la fórmula del modelo
#     except Exception:
#         return "Error cargando fórmula"

# Función para consumir mensajes de RabbitMQ
# Se conecta a RabbitMQ y escucha el exchange de dashboard en segundo plano
def consumidor():
    # Conexión a RabbitMQ
    connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
    channel = connection.channel()
    
    # Declaración del exchange
    channel.exchange_declare(exchange=DASHBOARD_EXCHANGE, exchange_type='fanout', durable=True)
    
    # Declaración de la cola temporal para recibir mensajes
    # Se utiliza una cola temporal para recibir mensajes del exchange
    result_queue = channel.queue_declare(queue='', exclusive=True, auto_delete=True)
    queue_name = result_queue.method.queue
    
    # Vinculación de la cola al exchange
    channel.queue_bind(exchange=DASHBOARD_EXCHANGE, queue=queue_name)

    # Callback para procesar los mensajes recibidos
    # Se define una función de callback que se ejecuta cada vez que se recibe un mensaje
    def callback(ch, method, properties, body):
        data = json.loads(body) # Decodifica el mensaje JSON
        resultados.append(data) # Agrega el resultado a la lista de resultados
        ch.basic_ack(delivery_tag=method.delivery_tag) # Envía un ACK para confirmar el procesamiento del mensaje

    # Inicia el consumo de mensajes
    channel.basic_consume(queue=queue_name, on_message_callback=callback)
    channel.start_consuming()

# Ejecutar consumidor en hilo separado para no bloquear la app
threading.Thread(target=consumidor, daemon=True).start()

# Callback para actualizar el dashboard
# Se define un callback que se ejecuta cada vez que se recibe un mensaje o se presiona el botón de reinicio
@app.callback(
    [Output("numero-simulaciones", "children"), # Número de simulaciones
     Output("promedio-simulaciones", "children"), # Promedio de las simulaciones
     Output("mediana-simulaciones", "children"), # Mediana de las simulaciones
     Output("desviacion-simulaciones", "children"), # Desviación estándar de las simulaciones
     Output("minimo-simulaciones", "children"), # Minimo de las simulaciones
     Output("maximo-simulaciones", "children"), # Máximo de las simulaciones
     Output("percentiles-simulaciones", "children"), # Percentiles de las simulaciones
     Output("varianza", "children"), # Varianza de las simulaciones
     Output("asimetria", "children"), # Asimetría de las simulaciones
     Output("curtosis", "children"), # Curtosis de las simulaciones
     Output("histograma", "figure"), # Gráfico de histogramas
     Output("fórmula", "children")], # Fórmula del modelo
    [Input("intervalo-actualizacion", "n_intervals"), # Intervalo de actualización
     Input("boton-reiniciar", "n_clicks")] # Botón de reinicio
)
def actualizar_dashboard(n_intervals, n_clicks):
    # Se obtiene el contexto del callback para saber qué disparó la actualización
    # Se utiliza el contexto para determinar si fue el intervalo o el botón de reinicio
    ctx = dash.callback_context

    # Si no hay disparador, se asigna None
    if not ctx.triggered:
        trigger_id = None
    else:
        # Se obtiene el ID del disparador
        # Se utiliza el ID del disparador para determinar qué acción tomar
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    # Si se presiona el botón de reinicio, se limpian los resultados
    if trigger_id == "boton-reiniciar":
        resultados.clear()

    num = len(resultados) # Número de simulaciones
    formula_actual_display = "Esperando datos..." # Placeholder
    # Si no hay resultados, se muestra un mensaje de "N/A"
    if num == 0:
        return (
            f"🧮 Número de simulaciones: {num}",
            "📈 Promedio de las simulaciones: N/A",
            "📊 Mediana: N/A",
            "📉 Desviación estándar: N/A",
            "🔽 Mínimo: N/A",
            "🔼 Máximo: N/A",
            "📐 Percentiles (25-50-75): N/A",
            "🧾 Varianza: 0.0000",
            "↩️ Asimetría: 0.0000",
            "🎯 Curtosis: 0.0000",
            {}, # Gráfico vacío 
            f"🧪 Fórmula actual: {formula_actual_display}"
        )

    # Se obtiene la fórmula del primer resultado
    formula = resultados[0].get("formula", "Fórmula no encontrada") # Se obtiene la fórmula del primer resultado
    # Si hay resultados, se calcula el promedio y se genera el gráfico
    # Se extraen los valores calculados de los resultados
    valores = [r["valor_calculado"] for r in resultados]
    df = pd.DataFrame(valores, columns=["Valores"]) # Se crea un DataFrame con los valores calculados

    if not valores: # Si no hay 'valor_calculado' en ningún resultado
        return (
            f"🧮 Número de simulaciones: {num} (0 con 'valor_calculado')",
            "📈 Promedio de las simulaciones: N/A",
            "📊 Mediana: N/A",
            "📉 Desviación estándar: N/A",
            "🔽 Mínimo: N/A",
            "🔼 Máximo: N/A",
            "📐 Percentiles (25-50-75): N/A",
            "🧾 Varianza: 0.0000",
            "↩️ Asimetría: 0.0000",
            "🎯 Curtosis: 0.0000",
            {},
            f"🧪 Fórmula actual: {formula_actual_display}"
        )

    # Se calculan las estadísticas
    promedio = df["Valores"].mean() # Promedio de los resultados
    mediana = df["Valores"].median() # Mediana de los resultados
    desviacion = df["Valores"].std() # Desviación estándar de los resultados
    minimo = df["Valores"].min() # Mínimo de los resultados
    maximo = df["Valores"].max() # Máximo de los resultados
    percentiles = df["Valores"].quantile([0.25, 0.5, 0.75]).to_dict() # Percentiles 25, 50 y 75 de los resultados
    varianza = df["Valores"].var() # Varianza de los resultados
    asimetria = skew(valores) # Asimetría de los resultados
    curtosis = kurtosis(valores) # Curtosis de los resultados
    
    # Se genera el gráfico de histogramas
    # Se utiliza Plotly Express para generar el gráfico de histogramas
    fig = px.histogram(df, x="Valores", nbins=20, title="Histograma de Resultados")

    # Se devuelve el número de simulaciones, el promedio, el gráfico y la fórmula
    return (
        f"🧮 Número de simulaciones: {num}",
        f"📈 Promedio de las simulaciones: {promedio:.4f}",
        f"📊 Mediana: {mediana:.4f}",
        f"📉 Desviación estándar: {desviacion:.4f}",
        f"🔽 Mínimo: {minimo:.4f}",
        f"🔼 Máximo: {maximo:.4f}",
        f"📐 Percentiles (25-50-75): {percentiles[0.25]:.4f}, {percentiles[0.5]:.4f}, {percentiles[0.75]:.4f}",
        f"🧾 Varianza: {varianza:.4f}",
        f"↩️ Asimetría: {asimetria:.4f}",
        f"🎯 Curtosis: {curtosis:.4f}",
        fig,
        f"🧪 Fórmula actual: {formula}"
    )

if __name__ == "__main__":
    port = 8050 # Puerto por defecto
    
    # Se inicia el servidor web
    # Se utiliza un temporizador para abrir el navegador automáticamente
    # Se utiliza el módulo webbrowser para abrir el navegador solo una vez
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        Timer(1, lambda: webbrowser.open(f'http://localhost:{port}')).start()  # Abrir navegador automáticamente asegurnando que el servidor ya esté corriendo
    
    # Se inicia la aplicación Dash
    app.run(debug=True)