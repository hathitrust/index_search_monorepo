#!/usr/bin/env bash

# This script is used to index the sample data into the Solr core

# Example: ./indexing_data.sh http://localhost:8983 ~/mydata core-x

# shellcheck disable=SC2034
solr_url="$1"

#Solr URL
#solr_pass="$2"
sample_data_directory="$2" #Directory where the sample data is located (XML files)
collection_name="$3" #Solr collection name

echo "$SOLR_PASSWORD" # The script expects the SOLR_PASSWORD environment variable to be set
for file in "$sample_data_directory/"*.xml
    do
        echo "Indexing $file 🌞!!!"
        curl -u admin:"$SOLR_PASSWORD" "$solr_url/solr/$collection_name/update?commit=true" -H "Content-Type: text/xml" --data-binary @"$file"
    done