# Proyecto_ComputoDistribuido
Repositorio para el proyecto de Cómputo Distribuido

## Pasos para ejecutarlo

## Instalar dependencias del proyecto
Primero se instalan las dependencias del proyecto mediante el comando:

```bash
pip install -r requirements.txt
```

## Activar servicio RabbitMQ
Se activa el servicio de mensajeria mediante el siguiente comando:
```bash
docker-compose up -d
```

## Modificación del JSON
Se le realiza las modificaciones al JSON dependiendo de la función y variables involucradas que desee el usuario.

## Ejecutar los archivos.
Para realizar una correcta ejecución, se requiere ejecutar los archivos en el siguiente orden:
- consumidor.py
- productor.py
- visualizador.py
