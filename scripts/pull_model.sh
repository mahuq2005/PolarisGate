#!/bin/bash
# Pull the Ollama models used by NorthGuard
# To pin a specific version, use: ollama pull llama3.2:1b@sha256:<digest>
docker-compose exec ollama ollama pull llama3.2:1b
docker-compose exec ollama ollama pull tinyllama
