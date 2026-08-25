# Contributing

## Before opening a PR

Run these, in order, from the repo root:

```sh
make fix-code    # ruff check --fix + ruff format
make type-check   # mypy --strict, currently scoped to libs + app/ht_indexer
make test-unit    # fast lane, no Solr/MySQL/RabbitMQ needed
```

If you touched `ht_indexer` or `solr_query`, also run the matching live-service suite:

```sh
docker compose --profile ht-indexer_tests up -d --wait
make test APP_NAME=ht-indexer

docker compose --profile solr-query_tests up -d --wait
make test APP_NAME=solr-query
```

CI runs the same commands (see `.github/workflows/tests.yaml`), and the `lint` job blocks
merging on `libs` + `app/ht_indexer`, so it's worth catching failures locally first.

If you don't have `uv` installed, run any of the above inside Docker instead:

```sh
docker run --rm -v "$PWD":/w -w /w ghcr.io/astral-sh/uv:python3.14-bookworm-slim \
  sh -c 'uv run ruff check app libs && uv run ruff format --check app libs && uv run mypy libs app/ht_indexer'
```

## A couple of conventions mypy --strict enforces here

- Every workspace subpackage needs an empty `py.typed` marker file. Without it, mypy silently
  treats cross-package imports of that code as `Any` instead of type-checking it, which hides
  real errors rather than catching them.
- `# type: ignore[...]` always needs a one-line comment saying why. Usually that's a third-party
  stub bug (e.g. `importlib.resources.files()` isn't typed as `PathLike` even though it behaves
  like one for a real installed package), not something wrong with our code.
