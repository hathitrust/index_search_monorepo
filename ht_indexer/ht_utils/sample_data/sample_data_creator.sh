#!/usr/bin/env bash

Checking out into $PWD

echo 📥 Creating the image

docker build -f ht_utils/sample_data/Dockerfile -t data_generator:2 .

echo Sampling data

echo $PWD

arg1_percentage="$1"
SAMPLE_PERCENTAGE="${arg1_percentage:-0.01}"

arg2_folder="$2"
SDR_DIR="${arg2_folder:-/sdr1/obj}"

arg3_items="$3"
ALL_ITEMS="${arg3_folder:-False}"

if [ -f .env ]
then
  echo "Creating .env file to store python environment variables"
  echo "\n"
  echo "SDR_DIR=$SDR_DIR" >> ht_utils/sample_data/.env
  echo "SAMPLE_PERCENTAGE=$SAMPLE_PERCENTAGE" >> ht_utils/sample_data/.env
fi

# Python script to sampling data and to obtain the pairtree path
# The script creates a file with the path of the file to download
# A volume is used to be able to read the created file to download the documents via scp

docker run -e SAMPLE_PERCENTAGE=$SAMPLE_PERCENTAGE -e ALL_ITEMS=$ALL_ITEMS -e SDR_DIR=$SDR_DIR -v $(PWD)/ht_utils/sample_data:/app/ht_utils/sample_data --name=data_generation data_generator:2 ht_utils/sample_data/sample_data_generator.py

parentdir="$(dirname "$PWD")"

echo $parentdir

echo "🔥 Creating sample_data folder if it does not exist"

mkdir -p "$parentdir$SDR_DIR"

target_path="$parentdir$SDR_DIR"

echo $target_path

for line in $(cat "$PWD/ht_utils/sample_data/sample_data_path.txt")
do
	path="$line"
	echo "$path"

	echo "🔽 Downloading "$path" from $HT_REPO_HOST to $target_path"

	scp "$HT_REPO_HOST":"$path" $target_path

done

rm ht_utils/sample_data/.env

echo "🎉 Done!"