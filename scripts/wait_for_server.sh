#!/bin/bash
HOST=$1
PORT=$2
echo "Waiting for $HOST:$PORT..."
until nc -z "$HOST" "$PORT"; do
  sleep 0.5
done
echo "Server is up!"