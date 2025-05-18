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

RABBITMQ_HOST = 'localhost'
DASHBOARD_EXCHANGE = 'dashboard_exchange'
MODEL_SETTINGS_FILE = 'model_settings.json'

app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("📊 Dashboard de Simulaciones en Tiempo Real 🧮"),
    html.Div(id="numero-simulaciones", style={"fontSize": 24, "margin": "10px"}),
    html.Div(id="promedio-simulaciones", style={"fontSize": 24, "margin": "10px"}),
    html.Div(id="fórmula", style={"fontSize": 20, "margin": "10px", "fontStyle": "italic"}),
    dcc.Graph(id="histograma"),
    html.Button("🔄 Reiniciar Dashboard", id="boton-reiniciar", n_clicks=0, style={"margin": "20px"}),
    dcc.Interval(id="intervalo-actualizacion", interval=2000, n_intervals=0)  # Actualizar cada 2 segundos
])

resultados = []

def cargar_formula():
    try:
        with open(MODEL_SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
        return settings.get("formula", "Fórmula no encontrada")
    except Exception:
        return "Error cargando fórmula"

def consumidor():
    connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
    channel = connection.channel()
    channel.exchange_declare(exchange=DASHBOARD_EXCHANGE, exchange_type='fanout', durable=True)
    result_queue = channel.queue_declare(queue='', exclusive=True, auto_delete=True)
    queue_name = result_queue.method.queue
    channel.queue_bind(exchange=DASHBOARD_EXCHANGE, queue=queue_name)

    def callback(ch, method, properties, body):
        data = json.loads(body)
        resultados.append(data)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=queue_name, on_message_callback=callback)
    channel.start_consuming()

# Ejecutar consumidor en hilo separado para no bloquear la app
threading.Thread(target=consumidor, daemon=True).start()

@app.callback(
    [Output("numero-simulaciones", "children"),
     Output("promedio-simulaciones", "children"),
     Output("histograma", "figure"),
     Output("fórmula", "children")],
    [Input("intervalo-actualizacion", "n_intervals"),
     Input("boton-reiniciar", "n_clicks")]
)
def actualizar_dashboard(n_intervals, n_clicks):
    ctx = dash.callback_context

    if not ctx.triggered:
        trigger_id = None
    else:
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if trigger_id == "boton-reiniciar":
        resultados.clear()

    num = len(resultados)
    if num == 0:
        return (
            f"🧮 Número de simulaciones: {num}",
            "📈 Promedio de las simulaciones: N/A",
            {},
            f"🧪 Fórmula actual: {cargar_formula()}"
        )

    valores = [r["valor_calculado"] for r in resultados]
    promedio = sum(valores) / num
    df = pd.DataFrame(valores, columns=["Valores"])
    fig = px.histogram(df, x="Valores", nbins=20, title="Histograma de Resultados")

    return (
        f"🧮 Número de simulaciones: {num}",
        f"📈 Promedio de las simulaciones: {promedio:.4f}",
        fig,
        f"🧪 Fórmula actual: {cargar_formula()}"
    )

if __name__ == "__main__":
    port = 8050
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        Timer(1, lambda: webbrowser.open(f'http://localhost:{port}')).start()  # Abrir navegador automáticamente
    app.run(debug=True)