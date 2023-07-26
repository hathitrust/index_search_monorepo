# ht_indexer
Application for indexing (add, delete, update) documents in Solr server

This is a FastApi application for indexing XML files in a Solr server

The application runs on http://localhost:8081. The documentation is automatically generated 
and you can check it in the http://localhost:8081/docs/.

## Setting up the API

1. Clone the repository in your working environment

``git clone git@github.com:hathitrust/ht_indexer.git``

2. Then, go to the folder ``cd ht_indexer``

3. In your workdir:

```docker-compose -f docker-compose.yml up -d```

If everything works well, in your browser you will access to the API documentation

http://localhost:8081/docs/

To test the application indexing XML documents use the following curl commands

Different commands to start the application

``uvicorn main:app --reload``

``python3 ht_indexer/main.py``

To run testing locally you would execute `ht_indexer_api_test.py` 


