TMP_DIR := $(shell mktemp -d)
# The name of the image for solr query interface
IMAGE_NAME := solr_query_interface

default: build
.PHONY: all build dep
all: build

# Install dependencies
dep:
	poetry install

build:
    # Copy project files
	cp -r src $(TMP_DIR)/src
	cp -r tests $(TMP_DIR)/tests

	cp Dockerfile .dockerignore $(TMP_DIR)
	cp pyproject.toml poetry.lock README.md $(TMP_DIR)

	# Copy the shared package written in pyproject.toml
	cp -r ../../libs/common_lib $(TMP_DIR)/common_lib
	cp -r ../../libs/ht_search $(TMP_DIR)/ht_search

	docker build -t $(IMAGE_NAME) $(TMP_DIR)

	rm -rf $(TMP_DIR)

# Run ht_indexer application in the docker container. The docker compose is in the root directory
run:
	docker compose --profile solr_query_interface up -d

# Run ht_indexer tests in the docker container. The docker compose is in the root directory
test:
	docker compose --profile solr_query_interface_tests up -d --wait
	DOCKER_COMPOSE_PROFILES=solr_query_interface_tests docker compose run --rm ht_search_tests
