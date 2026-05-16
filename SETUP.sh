#!/bin/bash
set -e

PROJECT_NAME="rag-swarm"
mkdir -p /mnt/data/$PROJECT_NAME
mkdir -p /mnt/data/${PROJECT_NAME}-logs

# Remove local dirs if they exist (before creating symlinks)
[ -d data     ] && rm -rf data
[ -d logs     ] && rm -rf logs
[ -d backend  ] && rm -rf backend
[ -d frontend ] && rm -rf frontend

# Create symlinks to /mnt/data
ln -sf /mnt/data/$PROJECT_NAME/backend  ./backend
ln -sf /mnt/data/$PROJECT_NAME/frontend ./frontend
ln -sf /mnt/data/$PROJECT_NAME/data     ./data
ln -sf /mnt/data/${PROJECT_NAME}-logs/logs ./logs

# Ensure .env exists from example
[ -f backend/.env ] || cp backend/.env.example backend/.env 2>/dev/null || true

echo "Partition separation complete."
echo "  backend  -> /mnt/data/$PROJECT_NAME/backend"
echo "  frontend -> /mnt/data/$PROJECT_NAME/frontend"
echo "  data     -> /mnt/data/$PROJECT_NAME/data"
echo "  logs     -> /mnt/data/${PROJECT_NAME}-logs/logs"