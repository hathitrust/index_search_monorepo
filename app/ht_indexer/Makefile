TMP_DIR := $(shell mktemp -d)
# The name of the indexer
IMAGE_NAME := ht_indexer

default: build
.PHONY: all build dep
all: build

# Install dependencies
dep:
	poetry install

build:
    # Copy project files
	cp -r src $(TMP_DIR)/src

	cp Dockerfile .dockerignore $(TMP_DIR)
	cp pyproject.toml poetry.lock README.md $(TMP_DIR)

	# Copy the shared package written in pyproject.toml
	cp -r ../../libs/common_lib $(TMP_DIR)/common_lib
	cp -r ../../libs/ht_search $(TMP_DIR)/ht_search

	docker build -t $(IMAGE_NAME) $(TMP_DIR)

	rm -rf $(TMP_DIR)

# Run ht_indexer application in the docker container. The docker compose is in the root directory
run:
	docker compose --profile indexer up -d

# Run ht_indexer tests in the docker container. The docker compose is in the root directory
test:
	docker compose --profile indexer_tests up -d --wait
	DOCKER_COMPOSE_PROFILES=indexer_tests docker compose run --rm all_tests
	docker compose --profile indexer_tests down -d