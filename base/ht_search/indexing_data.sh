#!/usr/bin/env bash

# This script is used to index the sample data into the Solr core

# Example: ./indexing_data.sh http://localhost:8983 solr_pass ~/mydata core-x

# shellcheck disable=SC2034
solr_url="$1"

#Solr URL
solr_pass="$2"
sample_data_directory="$3" #Directory where the sample data is located (XML files)
collection_name="$4" #Solr collection name

echo "$solr_pass"
for file in "$sample_data_directory/"*.xml
    do
        echo "Indexing $file 🌞!!!"
        curl -u admin:"$solr_pass" "$solr_url/solr/$collection_name/update?commit=true" -H "Content-Type: text/xml" --data-binary @"$file"
    done