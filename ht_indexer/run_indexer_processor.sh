#!/usr/bin/env bash
#echo "Build images"


echo "💎 Setting up document indexer service ..."

#docker compose build document_retriever
docker compose build document_indexer
docker build -t document_generator .

echo "🔥 Starting document indexer service ..."
docker compose up document_indexer -d

docker compose exec document_indexer python document_indexer_service/document_indexer_service.py --solr_indexing_api http://solr-lss-dev:8983/solr/#/core-x/
