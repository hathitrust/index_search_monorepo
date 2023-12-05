#!/usr/bin/env bash

Checking out into $PWD

echo 📥 Creating the image

docker build -f ht_utils/sample_data/Dockerfile -t data_generator:2 .

echo Sampling data

echo $PWD

# Python script to sampling data and to obtain the pairtree path
# The script creates a file with the path of the file to download
# A volume is used to be able to read the created file to download the documents via scp
#docker run -e SAMPLE_PERCENTAGE -e ALL_ITEMS -e  -v $(PWD)/ht_utils/sample_data:/app/ht_utils/sample_data --name=data_generation data_generator:2  /ht_utils/sample_data/sample_data_generator.py

docker run -e SAMPLE_PERCENTAGE -e ALL_ITEMS -v $(PWD)/ht_utils/sample_data:/app/ht_utils/sample_data --name=data_generation data_generator:2 ht_utils/sample_data/sample_data_generator.py

parentdir="$(dirname "$PWD")"

echo $parentdir

echo "Creating sample_data folder if it does not exist"

mkdir -p "$parentdir/sample_data/sdr1/obj"

target_path="$parentdir/sample_data/sdr1/obj"

echo $target_path

for line in $(cat "$PWD/ht_utils/sample_data/sample_data_path.txt")
do
	path="$line"
	echo "$path"

	echo "🔽 Downloading "$path" from $HT_REPO_HOST to $target_path"

	scp "$HT_REPO_HOST":"$path" $target_path

done

