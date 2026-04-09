TMP_DIR := $(shell mktemp -d)
# The name of the image for solr query interface
IMAGE_NAME := data_operations

default: build
.PHONY: all build dep
all: build

# Install dependencies
dep:
	poetry install

build:
	docker image build --target data_operations -t data_operations ../../

# Run ht_indexer application in the docker container. The docker compose is in the root directory
run:
	docker compose --profile data_operations up -d

# Run ht_indexer tests in the docker container. The docker compose is in the root directory
test:
	DOCKER_COMPOSE_PROFILES=data_operations docker compose exec data_operations python -m pytest
