#!/usr/bin/env bash
# TODO ADD ALL_ITEMS parameter
#if [ $source_resource=='local' ]; then
  # You should use the sample_data_creator.sh script to generate the local folder with the documents you want to process
for line in $(cat "$PWD/ht_utils/sample_data/sample_data_ht_ids.txt")
  do
    ht_id="$line"
    echo "🔁 Processing record $ht_id"
    python document_retriever_service/full_text_search_retriever_service.py --query ht_id:"$ht_id" --document_repository pairtree
    #  docker compose exec document_retriever python document_retriever_service/full_text_search_retriever_service.py --query ht_id:"$ht_id"
  done
#else # This option should work in Kubernetes, not use it locally if you do not have a local folder like a pairtree repository
#    echo "🔁 Processing all the record included in Catalog image"
#    docker compose exec document_retriever python document_retriever_service/full_text_search_retriever_service.py --query "*:*" --document_repository pairtree
#fi

echo "🎉 Done!"