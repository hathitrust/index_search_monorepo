# ht_full_text_search
Application for full-text search documents in Solr server

This application is a command line tool that allows to search documents in a full-text search Solr server. 
It is based on the [requests](https://docs.python-requests.org/en/latest/) library to access the Solr server.

The application runs in a docker container and it is based on the [python:3.11.0a7-slim-buster](https://hub.docker.com/_/python) image. 
Their dependencies are managing using [poetry](https://python-poetry.org/). 

To run the application, it is necessary to have a Solr server running. A sample of data (150 documents) is indexed 
in the Solr server every time the container is started.

## How to run it
* Create the image
`docker build -t full-text-searcher .`

* Start the container with the service involved in the search
`docker-compose up -d`

* Run the application with different queries
`docker run full-text-searcher:latest --env dev --query_string justice --operator AND --query_config all --solr_url http://localhost:8983/solr/#/core-x/`

 ### Explaining the parameters
* `--env` is the environment where the application is running. It can be `dev` or `prod`
* `--query_string` is the string to search in the documents. In case of a multi-word string, it must be between quotes e.g. `"justice league"`
* `--operator` is the operator to use in the query. It can be `AND` or `OR` or None, that means the query will find exact matches
* `--query_config` is the configuration to use in the query. It can be `all` or `ocronly`
  * `all` means that the query will search the input string in all the fields of the documents
  * `ocronly` means only the ocr field will be used in the query

### Example of queries:

The query below will retrieve only the documents that mention the exact phase `justice blame` in the full text
`docker compose exec full_text_searcher python ht_full_text_search/ht_full_text_searcher.py --env dev --query_string "justice blame" --operator None --query_config ocronly`

### Scripts for running batch of queries, saving the results in a csv file and comparing the results with the expected ones or with the results of another query or search engine

`python3 ht_full_text_search/scripts/generate_query_results.py`
`python3 ht_full_text_search/scripts/compare_results.py`

### Set up development environment with poetry

In your workdir,

`poetry init` # It will set up your local environment and repository details
`poetry env use python` # To find the virtual environment directory, created by poetry
`source ~/ht-full-text-search-TUsF9qpC-py3.11/bin/activate` # Activate the virtual environment
`poetry add pytest` # Add dependencies



## References

Python HTTP libraries: [requests vs urllib3](https://medium.com/@technige/what-does-requests-offer-over-urllib3-in-2022-e6a38d9273d9)
Requests: [Sessions and authentication](https://www.geeksforgeeks.org/python-requests-tutorial/)
