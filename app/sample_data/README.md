#### Data Sampling: Create a sample of data:

Use this module if you want to download data from pairtree-based repository via scp and store it in your local
environment.

FY: This logic was adopted because it is complex to set up permission in the docker to access to pairtree repository via
scp

Find this module in: `ht_indexer/ht_utils/sample_data/`. All the logic is implemented in the
script `sample_data_creator.sh`.
The script will use the JSON file `full-output-catalog-index.json`, that contains an extract of the Catalog Solr index
to generate the list of items to index. The file `sample_data_ht_ids.txt` is generated to load the list of items.
The file `sample_data_path.txt` is also generated with the list of paths. We decided to get the pair-tree path using
python and use a shell script to download the documents via scp.

The script will generate the folder /sdr1/obj to download the .zip and .mets.xml file for the list of records.
The folder will be created in the parent directory of ht_indexer repository.

`sample_data_creator.sh` by default,

* 1% of the documents indexed in Catalog image will be added to the sample. You can change the default value
  passing a different value to the script `sample_data_creator.sh`, e.g., 0.50 to retrieve 50% of the documents in
  Catalog.
* only one item per Catalog record will be added to the sample. You can add all the items if you pass True as an
  argument
* sdr_dir=/sdr1/obj, you can also change this value passing a different argument.

I have had some issues running the python script with the docker (line 34 of `sample_data_creator.sh`). It seems python
is not able to receive the arguments defined as environment variables in the console.

To overcome it, I recommend using the python script directly to create the sample of data and before that you should
define the environment variables SAMPLE_PERCENTAGE and ALL_ITEMS.

``python ht_indexer/ht_utils/sample_data/sample_data_generator.py``

Once you have the list of documents, you want to include in the sample, comment line 34 of
the `sample_data_creator.sh` script and run it to download the files through scp protocol.

Steps to download a sample pairtree-based repository in your local environment:

In your workdir,

1. Set up the environment variable
   ```export HT_REPO_HOST=some.host.hathitrust.org```
2. Use a default set up for generating the folder with the documents to process:
   ```./ht_utils/sample_data/sample_data_creator.sh```
3. Passing arguments to generate the sample of data:
   ```./ht_utils/sample_data/sample_data_creator.sh 0.0011 /sdr1/obj```

Note: Follow the command below if you want to download files from pairtree repository data for testing

   ```
   $HT_SSH_HOST=some.host.hathitrust.org
   scp $HT_SSH_HOST:/sdr1/obj/umn/pairtree_root/31/95/1d/03/01/41/20/v/31951d03014120v/31951d03014120v{.zip,mets.xml} ../sdr1/obj
   ```
