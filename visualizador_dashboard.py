''''
    Visualizador de Resultados de Simulación con Dash y Bootstrap
    
    Este script implementa un dashboard interactivo para visualizar los resultados
    de las simulaciones Montecarlo en tiempo real. Utiliza Dash para la interfaz web,
    Plotly Express para los gráficos, y Dash Bootstrap Components para mejorar el diseño.
    Consume mensajes de resultados desde un exchange fanout de RabbitMQ.
    ------------------------------------------------
        * Muestra estadísticas descriptivas clave en tarjetas (Cards).
        * Presenta un histograma dinámico de los resultados.
        * Permite reiniciar la visualización de datos.
        * Muestra la fórmula del modelo de simulación que se está ejecutando.
        * Manejo de reconexión a RabbitMQ en el hilo consumidor.
        * Acceso seguro a datos compartidos entre hilos.
    ------------------------------------------------
'''

# Importación de librerías necesarias
import dash
from dash import dcc, html 
from dash.dependencies import Output, Input, State 
import plotly.express as px
import pika
import json
import threading
import pandas as pd
import webbrowser
from threading import Timer, Lock 
import os
import time 
import numpy as np
from scipy.stats import kurtosis, skew
import dash_bootstrap_components as dbc 

# Parámetros de configuración de RabbitMQ
RABBITMQ_HOST = 'localhost'
DASHBOARD_EXCHANGE = 'dashboard_exchange' 

# Inicializar la app Dash con un tema de Bootstrap (oscuro)
# Otros temas oscuros: CYBORG, SLATE, VAPOR
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY]) 

# Variables globales compartidas
resultados_lock = Lock()
resultados_simulacion = [] 
formula_actual_global = "Esperando datos del modelo..." 
ultimo_n_clicks_reinicio = 0


# --- Diseño de la interfaz del dashboard con Dash Bootstrap Components ---
app.layout = dbc.Container([
    dbc.Row(
        dbc.Col(
            html.H1("📊 Dashboard de Simulaciones Montecarlo en Tiempo Real 🧮", className="my-4"), 
            width=12, 
            className="text-center"
        )
    ),
    
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("ℹ️ Información de la Simulación Actual"),
                dbc.CardBody([
                    html.P(id="formula-display", className="card-text fst-italic mb-2"), 
                    html.H5(id="numero-simulaciones", className="card-title"),
                ])
            ], className="shadow-sm mb-4") 
        ], width=12)
    ]),

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("📈 Estadísticas Clave"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col(dbc.Label("Promedio:", html_for="promedio-simulaciones"), width="auto", className="fw-bold"),
                        dbc.Col(html.Div(id="promedio-simulaciones")),
                    ], className="mb-2 align-items-center"),
                    dbc.Row([
                        dbc.Col(dbc.Label("Mediana:", html_for="mediana-simulaciones"), width="auto", className="fw-bold"),
                        dbc.Col(html.Div(id="mediana-simulaciones")),
                    ], className="mb-2 align-items-center"),
                    dbc.Row([
                        dbc.Col(dbc.Label("Desv. Est.:", html_for="desviacion-simulaciones"), width="auto", className="fw-bold"),
                        dbc.Col(html.Div(id="desviacion-simulaciones")),
                    ], className="mb-2 align-items-center"),
                    dbc.Row([
                        dbc.Col(dbc.Label("Varianza:", html_for="varianza-simulaciones"), width="auto", className="fw-bold"),
                        dbc.Col(html.Div(id="varianza-simulaciones")),
                    ], className="align-items-center"),
                ])
            ], className="shadow-sm mb-4")
        ], lg=4, md=6), 

        dbc.Col([
            dbc.Card([
                dbc.CardHeader("↔️ Rango y Extremos"),
                dbc.CardBody([
                     dbc.Row([
                        dbc.Col(dbc.Label("Mínimo:", html_for="minimo-simulaciones"), width="auto", className="fw-bold"),
                        dbc.Col(html.Div(id="minimo-simulaciones")),
                    ], className="mb-2 align-items-center"),
                    dbc.Row([
                        dbc.Col(dbc.Label("Máximo:", html_for="maximo-simulaciones"), width="auto", className="fw-bold"),
                        dbc.Col(html.Div(id="maximo-simulaciones")),
                    ], className="align-items-center"),
                ])
            ], className="shadow-sm mb-4")
        ], lg=4, md=6),

        dbc.Col([
            dbc.Card([
                dbc.CardHeader("📐 Características de la Distribución"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col(dbc.Label("Percentiles (P25, P50, P75):", html_for="percentiles-simulaciones"), width="auto", className="fw-bold"),
                        dbc.Col(html.Div(id="percentiles-simulaciones")),
                    ], className="mb-2 align-items-center"),
                     dbc.Row([
                        dbc.Col(dbc.Label("Asimetría:", html_for="asimetria-simulaciones"), width="auto", className="fw-bold"),
                        dbc.Col(html.Div(id="asimetria-simulaciones")),
                    ], className="mb-2 align-items-center"),
                    dbc.Row([
                        dbc.Col(dbc.Label("Curtosis:", html_for="curtosis-simulaciones"), width="auto", className="fw-bold"),
                        dbc.Col(html.Div(id="curtosis-simulaciones")),
                    ], className="align-items-center"),
                ])
            ], className="shadow-sm mb-4")
        ], lg=4, md=12) 
    ]),
    
    dbc.Row(dbc.Col(dcc.Graph(id="histograma-resultados"), width=12, className="mb-3")),
    
    dbc.Row(dbc.Col(
        dbc.Button("🔄 Reiniciar Dashboard", id="boton-reiniciar", color="danger", className="mt-3 mb-3", n_clicks=0),
        width={"size": "auto"}, 
        className="d-grid gap-2 col-6 mx-auto" 
    )),
    
    dcc.Interval(id="intervalo-actualizacion", interval=1500, n_intervals=0) 
], fluid=True, className="p-4") 


# --- Lógica del Consumidor RabbitMQ (en un hilo separado) ---
def consumidor_rabbitmq():
    global resultados_simulacion, formula_actual_global 
    
    connection = None
    while True: 
        try:
            print("[Consumidor RabbitMQ] Intentando conectar...")
            credentials = pika.PlainCredentials('guest', 'guest')
            connection_parameters = pika.ConnectionParameters(
                RABBITMQ_HOST, 
                credentials=credentials,
                heartbeat=60, 
                blocked_connection_timeout=300 
            )
            connection = pika.BlockingConnection(connection_parameters)
            channel = connection.channel()
            
            channel.exchange_declare(exchange=DASHBOARD_EXCHANGE, exchange_type='fanout', durable=True)
            
            result_queue = channel.queue_declare(queue='', exclusive=True, auto_delete=True)
            queue_name = result_queue.method.queue
            channel.queue_bind(exchange=DASHBOARD_EXCHANGE, queue=queue_name)
            print(f"[Consumidor RabbitMQ] Conectado y suscrito a la cola '{queue_name}' del exchange '{DASHBOARD_EXCHANGE}'.")

            def callback(ch, method, properties, body):
                global formula_actual_global 
                try:
                    data = json.loads(body.decode())
                    with resultados_lock: 
                        resultados_simulacion.append(data) 
                        formula_actual_global = data.get("formula", formula_actual_global) 
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except json.JSONDecodeError:
                    print(f"[Consumidor RabbitMQ] Error al decodificar JSON: {body.decode()}")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                except Exception as e:
                    print(f"[Consumidor RabbitMQ] Error en callback: {e}")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            channel.basic_consume(queue=queue_name, on_message_callback=callback)
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as e:
            print(f"[Consumidor RabbitMQ] Error de conexión AMQP: {e}. Reintentando en 5 segundos...")
        except Exception as e:
            print(f"[Consumidor RabbitMQ] Error inesperado: {e}. Reintentando en 5 segundos...")
        finally: 
            if connection and connection.is_open:
                try:
                    connection.close()
                    print("[Consumidor RabbitMQ] Conexión RabbitMQ cerrada.")
                except Exception as e_close:
                    print(f"[Consumidor RabbitMQ] Error al cerrar conexión: {e_close}")
            time.sleep(5)


thread_consumidor = threading.Thread(target=consumidor_rabbitmq, daemon=True)
thread_consumidor.start()


# --- Callback de Dash para actualizar la interfaz ---
@app.callback(
    [Output("numero-simulaciones", "children"),
     Output("promedio-simulaciones", "children"),
     Output("mediana-simulaciones", "children"),
     Output("desviacion-simulaciones", "children"),
     Output("minimo-simulaciones", "children"),
     Output("maximo-simulaciones", "children"),
     Output("percentiles-simulaciones", "children"),
     Output("varianza-simulaciones", "children"),
     Output("asimetria-simulaciones", "children"),
     Output("curtosis-simulaciones", "children"),
     Output("histograma-resultados", "figure"),
     Output("formula-display", "children")],
    [Input("intervalo-actualizacion", "n_intervals")],
    [State("boton-reiniciar", "n_clicks")] 
)
def actualizar_dashboard(n_intervals, n_clicks_actual_reiniciar):
    global resultados_simulacion, formula_actual_global, ultimo_n_clicks_reinicio

    if n_clicks_actual_reiniciar > ultimo_n_clicks_reinicio:
        with resultados_lock:
            resultados_simulacion.clear()
            formula_actual_global = "Dashboard Reiniciado - Esperando datos..."
        ultimo_n_clicks_reinicio = n_clicks_actual_reiniciar 
        print("[Dashboard] Resultados y fórmula reiniciados por el usuario.")

    with resultados_lock:
        resultados_copia = list(resultados_simulacion) 
        formula_para_mostrar = formula_actual_global
    
    num_muestras = len(resultados_copia)
    default_na = "N/A"
    # Para temas oscuros, es mejor definir un template para Plotly Express
    plotly_template = "plotly_dark" # O "plotly" para el tema claro por defecto de Plotly
    empty_fig = {'data': [], 'layout': {'title': 'Histograma de Resultados (Esperando datos)', 'template': plotly_template}}
    
    if num_muestras == 0:
        return (
            f"Simulaciones: {num_muestras}", default_na, default_na, default_na, default_na, default_na,
            default_na, default_na, default_na, default_na, empty_fig, f"Fórmula: {formula_para_mostrar}"
        )

    valores_calculados = [r.get("valor_calculado") for r in resultados_copia if r.get("valor_calculado") is not None]
    
    if not valores_calculados:
        empty_fig_no_values = {'data': [], 'layout': {'title': 'Histograma de Resultados (Sin valores válidos)', 'template': plotly_template}}
        return (
            f"Simulaciones: {num_muestras} (0 con 'valor_calculado')", default_na, default_na, default_na,
            default_na, default_na, default_na, default_na, default_na, default_na, empty_fig_no_values,
            f"Fórmula: {formula_para_mostrar}"
        )

    df = pd.DataFrame(valores_calculados, columns=["Valores"])
    
    promedio = f"{df['Valores'].mean():.2f}"
    mediana = f"{df['Valores'].median():.2f}"
    desviacion = f"{df['Valores'].std():.2f}" if num_muestras > 1 else default_na
    minimo = f"{df['Valores'].min():.2f}"
    maximo = f"{df['Valores'].max():.2f}"
    
    if num_muestras > 1:
        percentiles_dict = df["Valores"].quantile([0.25, 0.50, 0.75]).to_dict()
        percentiles_str = f"P25: {percentiles_dict.get(0.25, 0):.2f}, P50: {percentiles_dict.get(0.50, 0):.2f}, P75: {percentiles_dict.get(0.75, 0):.2f}"
        varianza = f"{df['Valores'].var():.2f}"
        asimetria_val = f"{skew(df['Valores'].dropna()):.4f}" if not df['Valores'].dropna().empty else default_na
        curtosis_val = f"{kurtosis(df['Valores'].dropna()):.4f}" if not df['Valores'].dropna().empty else default_na
    else:
        percentiles_str = default_na
        varianza = default_na
        asimetria_val = default_na
        curtosis_val = default_na

    # Usar el template oscuro para el histograma de Plotly Express
    fig = px.histogram(df, x="Valores", nbins=30, title=f"Distribución de Resultados ({len(valores_calculados)} valores válidos)",
                       template=plotly_template)
    fig.update_layout(bargap=0.1, title_x=0.5) 

    return (
        f"Simulaciones: {num_muestras}",
        promedio, mediana, desviacion, minimo, maximo,
        percentiles_str, varianza, asimetria_val, curtosis_val,
        fig, f"Fórmula: {formula_para_mostrar}"
    )

def abrir_navegador(port):
    if not os.environ.get("WERKZEUG_RUN_MAIN"): 
        webbrowser.open_new_tab(f"http://localhost:{port}")

if __name__ == "__main__":
    PUERTO_DASH = 8050
    Timer(1.5, abrir_navegador, args=(PUERTO_DASH,)).start() 
    print(f"Dashboard corriendo en http://localhost:{PUERTO_DASH}")
    app.run(debug=True, port=PUERTO_DASH)
