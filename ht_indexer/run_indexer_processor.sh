#!/usr/bin/env bash
#echo "Build images"


echo "💎 Setting up document indexer service ..."

#docker compose build document_retriever
docker compose build document_indexer
docker build -t document_generator .

echo "🔥 Starting document indexer service ..."
docker compose up document_indexer -d

docker compose exec document_indexer python document_indexer_service/document_indexer_service.py --solr_indexing_api http://solr-lss-dev:8983/solr/#/core-x/



# **** Commands using the queue
# Retriever service = receive a list of documents
docker compose exec document_retriever python document_retriever_service/full_text_search_retriever_service.py --list_documents chi.096189208,iau.31858049957305,hvd.32044106262314,chi.096415811,hvd.32044020307005,hvd.32044092647320,iau.31858042938971 --query_field item

# Generator service
docker compose exec document_indexer python document_generator/document_generator_service.py

# Indexer service
docker compose exec document_indexer python document_indexer_service/document_indexer_service.py --solr_indexing_api http://solr-lss-dev:8983/solr/#/core-x/

# **** Use case for processing long documents
# Commands using using retriever queue and the rest of the services are running locally
# Retriever service = receive a list of documents
docker compose exec document_retriever python document_retriever_service/full_text_search_retriever_service.py --list_documents chi.096189208,iau.31858049957305,hvd.32044106262314,chi.096415811,hvd.32044020307005,hvd.32044092647320,iau.31858042938971 --query_field item

# Generator service Locally
docker compose exec document_generator python document_generator/document_generator_service_local.py --document_local_path /tmp --document_repository local

# Indexer service Locally
docker compose exec document_indexer python document_indexer_service/document_indexer_local_service.py --solr_indexing_api http://solr-lss-dev:8983/solr/#/core-x/ --document_local_path /tmp/indexing_data

# **** Use case for processing documents retrieved from a file
docker compose exec document_retriever python run_retriever_service_by_file.py