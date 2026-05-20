# DevOps Project with Docker Compose

This project sets up a monitoring and AI infrastructure using Docker Compose.

## Services

- **NATS**: Messaging system with JetStream enabled
- **Redis**: In-memory data store with persistence
- **Jaeger**: Distributed tracing and monitoring (UI on port 16686)
- **Ollama**: LLM inference service

## Setup

1. Start services:
   ```bash
   docker-compose up -d
   ```

2. Pull LLM model:
   ```bash
   docker-compose exec ollama ollama pull llama3.2:1b
   ```

3. Check status:
   ```bash
   docker-compose ps
   docker-compose logs ollama
   ```

## Networks

All services are connected to `monitoring-net` for inter-service communication.

## Volumes

- `ollama_models`: Persistent storage for Ollama models
