#!/usr/bin/env bash

# This script is used to run the retriever processor in a kubernetes environment and having a TXT file with the list of IDs to be processed.
python document_retriever_service/full_text_search_retriever_by_file.py --list_ids_path "$PWD/filter_ids.txt" --document_repository pairtree

echo "🎉 Done!"