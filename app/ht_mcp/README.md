# HathiTrust Catalog MCP Server

MCP server giving AI assistants structured access to the HathiTrust catalog volumes API.

## Tools

| Tool               | Description                                                        |
| ------------------ | ------------------------------------------------------------------ |
| `ping`             | Check that the MCP server is running                               |
| `health`           | Check connectivity to the catalog backend                          |
| `describe_catalog` | Return supported identifier fields, rights codes, and URL patterns |
| `lookup_single`    | Look up one catalog record by identifier (`field`, `value`)        |
| `lookup_volumes`   | Batch lookup by list of `"field:value"` strings                    |

Supported identifier fields: `htid`, `oclc`, `isbn`, `lccn`, `issn`, `recordid`.

## Run and test

From the repository root:

```sh
uv run --package ht-mcp python -m ht_mcp.server        # SSE endpoint: http://localhost:8000/sse
uv run --package ht-mcp pytest app/ht_mcp/tests -m "not integration"
```

Integration tests (`-m integration`) need a running catalog at `CATALOG_URL`.

## Connecting an AI client

```sh
claude mcp add --transport sse --scope user hathitrust-catalog http://localhost:8000/sse
```

## Configuration

See `env.example`. Set `CATALOG_URL`, `MCP_HOST`, `MCP_PORT` and `HTTP_TIMEOUT_SECONDS` as environment variables or in a `.env` file. `LOG_LEVEL` is defined but not used yet.
