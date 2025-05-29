install:
	poetry install

#lint:
#	black --config .black.toml . && \
#	ruff --config .ruff.toml --fix .

test:
	pytest .