
echo "Build images"
docker build -t document_generator .

echo "Setting up document_retriever"

docker compose build document_retriever
docker compose build document_indexer

#echo "Starting document indexer service"
docker compose up document_indexer -d

#parentdir="$(dirname "$PWD")"
#docker compose exec document_indexer document_indexer_service/document_indexer_service.py --solr_indexing_api http://solr-lss-dev:8983/solr/#/core-x/

echo "Starting document retriever service"
docker compose up document_retriever -d


for line in $(cat "$PWD/ht_utils/sample_data/sample_data_ht_ids.txt")
do
	ht_id="$line"

	echo "Processing $ht_id"

	docker compose exec document_retriever python document_retriever_service/full_text_search_retriever_service.py --query ht_id:"$ht_id"
done