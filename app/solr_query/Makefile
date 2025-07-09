TMP_DIR := $(shell mktemp -d)
# The name of the image for solr query interface
IMAGE_NAME := solr_query

default: build
.PHONY: all build dep
all: build

# Install dependencies
dep:
	poetry install

build:
	docker image build --target solr_query -t solr_query ../../

# Run ht_indexer application in the docker container. The docker compose is in the root directory
run:
	docker compose --profile solr_query up -d

# Run ht_indexer tests in the docker container. The docker compose is in the root directory
test:
	DOCKER_COMPOSE_PROFILES=solr_query_tests docker compose run --rm search_tests
