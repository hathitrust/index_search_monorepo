APPS_NAME = ht-indexer
APPS_DIR = ht_indexer
APP_PATH = app/$(APP_DIR)

# TODO: Check install
install:
	uv install

# Check the code with ruff. The first command checks for linting errors, while the second command checks for formatting issues.
# Both commands target the application path defined by APP_PATH.
check-code:
	uv run --no-project -- ruff check $(APP_PATH)
	uv run --no-project -- ruff format --check $(APP_PATH)

# Fix the code with ruff.
# The first command attempts to fix linting errors, while the second command formats the code.
# Both commands target the application path defined by APP_PATH.
# The '|| true' part ensures that even if the first command fails (e.g., due to unfixable issues), the second command will still run to format the code.
# Apply safe fixes only
fix-code:
	uv run --no-project -- ruff check --fix $(APP_PATH) || true
	uv run --no-project -- ruff format $(APP_PATH)

# Apply unsafe fixes as well. Use with caution, as it may change the behavior of the code.
fix-code-unsafe:
	uv run --no-project -- ruff check --fix --unsafe-fixes $(APP_PATH)
	uv run --no-project -- ruff format $(APP_PATH)

# Explicit typing check
type-check:
	uv run --no-project -- mypy $(APP_PATH)

test-all:
	pytest .

build-all:
	for app in $(APPS_NAME); do \
		for directory in $(APPS_DIR); do \
			$(MAKE) build APP_NAME=$$app APP_DIR=$$directory; \
		done \
	done

# Build the docker image for each application
build:
	docker image build \
	--build-arg ENV=dev \
	--build-arg APP_NAME=$(APP_NAME) \
	--build-arg APP_DIR=$(APP_DIR) \
	--target runtime -t $(APP_NAME) \
	.

# Run ht_indexer application in the docker container. The docker compose is in the root directory
# TODO: run build-all before up to ensure the images are built before running the containers
up: # build-all
	docker compose --profile $(APP_NAME) up -d

# Run ht_indexer tests in the docker container. The docker compose is in the root directory
test:
	DOCKER_COMPOSE_PROFILES=$(APP_NAME)_tests docker compose run --rm $(APP_NAME)_tests

