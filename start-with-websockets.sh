#!/bin/bash

# Hacer ejecutable el entrypoint de ASGI
chmod +x docker/entrypoint-asgi.sh

# Iniciar los servicios principales
echo "Starting main services (database, redis, web)..."
docker-compose up -d

# Esperar a que los servicios principales estén activos
echo "Waiting for main services to be ready..."
sleep 10

# Iniciar el servicio ASGI para WebSockets
echo "Starting ASGI service for WebSockets..."
docker-compose -f docker-compose.asgi.yml up -d

echo "All services are up and running!"
echo "Web service running at: http://localhost:8000"
echo "WebSocket service running at: ws://localhost:8001"
echo ""
echo "To test WebSockets, open the websocket_test.html file in your browser"
