
echo "Build images"
docker build -t document_generator .

echo "💎 Setting up document retriever service ..."
docker compose build document_retriever

echo "🔥 Starting document retriever service ..."
docker compose up document_retriever

for line in $(cat "$PWD/ht_utils/sample_data/sample_data_ht_ids.txt")
do
	ht_id="$line"

	echo "Processing $ht_id record"

	docker compose exec document_retriever python document_retriever_service/full_text_search_retriever_service.py --query ht_id:"$ht_id"
done

echo "🎉 Done!"