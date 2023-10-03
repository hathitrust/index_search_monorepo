# ht_indexer

Application for indexing (add, delete, update) documents in Solr server

This is a FastApi application for indexing XML files in a Solr server

The application runs on http://localhost:8081. The documentation is automatically generated
and you can check it in the http://localhost:8081/docs/.

This application uses the solar server instanted by the **babel-solr-lss-dev-1** container.
Then, this container must be running before load the API.

Run until the Step 4 for setting up babel-local-dev. See in
the [repository](https://github.com/hathitrust/babel-local-dev)

## Setting up the API

1. Clone the repository in your working environment

``git clone git@github.com:hathitrust/ht_indexer.git``

2. Then, go to the folder ``cd ht_indexer``

3. In your workdir:

```docker-compose -f docker-compose.yml up -d```

If everything works well, in your browser you will access to the API documentation

http://localhost:8081/docs/

## Command to use the API

Use this curl command to check if the API is ready to use

``curl --location 'http://localhost:8081/ping/'``

Using this prototype you will be able to index an XML document stored in a data folder inside the server.

Use this curl command to add the XML file

``curl --location --request POST 'http://127.0.0.1:8081/solrIndexing/?path=data%2Fadd' \
--header 'Content-Type: text/plain' \
--data '@'``

Use this curl command to delete the XML file

``curl --location --request POST 'http://127.0.0.1:8081/solrIndexing/?path=data%2Fdelete'``

You can also run the application from your local machine without a docker file using the following command.
However, you will have to set up you python environment.

Use this curl command to query Sorl

``curl http://localhost:9033/solr/catalog/query -d 'json={"query":"ht_id:umn.31951000662660j"}'``

``poetry run python main.py --host 0.0.0.0 --port 8081 --solr_host localhost --solr_port 8983``

## [Optional] How to set up your python environment

On mac,

* Install python
    * You can read this blog to install python in a right way in
      python: https://opensource.com/article/19/5/python-3-default-mac
        * I installed using brew and pyenv
* Install poetry:
    * **Good blog to understand and use poetry
      **: https://blog.networktocode.com/post/upgrade-your-python-project-with-poetry/
    * **Poetry docs**: https://python-poetry.org/docs/dependency-specification/
    * **How to manage Python projects with Poetry
      **: https://www.infoworld.com/article/3527850/how-to-manage-python-projects-with-poetry.html

To run testing locally you would execute `ht_indexer_api_test.py`

## Document generator

Before using this script you should set up the following environment variables

export HOST=something.hathitrust.org
export USER=your_user_name
export PUBLIC_KEY=public_key_name

Reference used for python implementation

Parser XML files
https://lxml.de/tutorial.html#parsing-from-strings-and-files
https://pymotw.com/3/xml.etree.ElementTree/parse.html

MySql
https://www.w3schools.com/python/python_mysql_join.asp

SSH + python script + environment variables to pass user/password
https://www.the-analytics.club/python-ssh-shell-commands/#google_vignette

Pypairtree
https://github.com/unt-libraries/pypairtree/tree/master

Mets fields documentation: https://mets.github.io/METS_Docs/mets_xsd_Attribute_Group_ORDERLABELS.html
Best practices for writing Dockerfiles: https://docs.docker.com/develop/develop-images/dockerfile_best-practices/
Docker reference: https://docs.docker.com/engine/reference/builder/#workdir
Interesting discussion about poetry and docker file:
https://stackoverflow.com/questions/53835198/integrating-python-poetry-with-docker/70161384#70161384
https://github.com/python-poetry/poetry/issues/1178
Poetry & docker good reference: https://github.com/max-pfeiffer/uvicorn-gunicorn-poetry/tree/main/build

* Something I want to test in my Dockerfile: Use poetry for the dependency solver and then use pip for installing the
  final wheel. => Use poetry expert to generate requirements.txt file,
  use this blog as a
  reference: https://medium.com/vantageai/how-to-make-your-python-docker-images-secure-fast-small-b3a6870373a0
* See this video to reduce the size of the container: https://www.youtube.com/watch?v=kx-SeGbkNPU

--solr_url http://localhost:9033/solr/#/catalog/ --mysql_host mudslide.umdl.umich.edu --mysql_user lisepul --mysql_pass
viu8ii39hgq48axf6vzeb62mpes64buh --mysql_database ht --query id:012407877