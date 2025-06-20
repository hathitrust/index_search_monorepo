# The name of the indexer
IMAGE_NAME := ht_indexer

default: build
.PHONY: all build dep
all: build

# Install dependencies
dep:
	poetry install

# Build the docker image for the indexer
build:
	docker image build --target ht_indexer -t ht_indexer ../../

# Run ht_indexer application in the docker container. The docker compose is in the root directory
run:
	docker compose --profile indexer up -d

# Run ht_indexer tests in the docker container. The docker compose is in the root directory
test:
	docker compose --profile indexer_tests up -d --wait
	DOCKER_COMPOSE_PROFILES=indexer_tests docker compose run --rm ht_indexer_tests
	docker compose --profile indexer_tests down -d