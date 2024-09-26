#!/usr/bin/env bash

echo "🚢 Build docker images"

docker build -t document_generator .

echo "🚢 Run document_retriever"
docker compose up document_retriever -d

echo "🌎 Run document_retriever test"
docker compose exec document_retriever pytest document_retriever_service catalog_metadata ht_utils

echo "🚢 Run document_generator"
docker compose up document_generator -d

echo "🌎 Run document_generator test"
docker compose exec document_generator pytest document_generator ht_document ht_queue_service ht_utils

echo "🚢 Run document_indexer"
docker compose up document_indexer -d

echo "🌎 Run document_indexer test"
docker compose exec document_indexer pytest document_indexer_service ht_indexer_api ht_queue_service