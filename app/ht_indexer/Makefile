# The name of the indexer
IMAGE_NAME := indexer

default: build
.PHONY: all build dep
all: build

# Install dependencies
dep:
	poetry install

# Build the docker image for the indexer
build:
	docker image build --target indexer -t indexer ../../

# Run ht_indexer application in the docker container. The docker compose is in the root directory
run:
	docker compose --profile indexer up -d

# Run ht_indexer tests in the docker container. The docker compose is in the root directory
test:
	DOCKER_COMPOSE_PROFILES=indexer_tests docker compose run --rm indexer_tests