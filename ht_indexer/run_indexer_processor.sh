
#echo "Build images"
#docker build -t document_generator .

echo "Setting up document_indexer"

#docker compose build document_retriever
docker compose build document_indexer

echo "Starting document indexer service"
docker compose up document_indexer

parentdir="$(dirname "$PWD")"
docker compose exec document_indexer python document_indexer_service/document_indexer_service.py --solr_indexing_api http://solr-lss-dev:8983/solr/#/core-x/
