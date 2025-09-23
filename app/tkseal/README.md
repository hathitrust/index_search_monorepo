# TKSeal Python

A Python 3.12 port of the Ruby [tkseal](https://github.com/mlibrary/tkseal) CLI tool for managing sealed secrets in Kubernetes environments using Grafana Tanka configuration repositories.

## Development Environment Setup

### Prerequisites
- Python 3.12+
- Poetry (for dependency management)

### Setup Commands

```bash
# Install dependencies and set up virtual environment
poetry install -E dev

# Verify installation
poetry run tkseal --help
poetry run tkseal version
```

## Running Tests

```bash
# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest tests/test_cli.py

# Run specific test with verbose output
poetry run pytest tests/test_cli.py::TestVersionCommand::test_version_command_returns_version -v

# Run tests with coverage
poetry run pytest --cov=tkseal --cov-report=term-missing
```

## Code Quality

```bash
# Run linting
poetry run ruff check src/ tests/

# Format code
poetry run ruff format src/ tests/

# Type checking
poetry run mypy src/
```

## Available Commands

- ✅ `tkseal version` - Show current version
- 👩‍💻 `tkseal ready` - Check dependencies (WIP)
- 🚧 `tkseal diff PATH` - Show differences between plain_secrets.json and cluster
- 🚧 `tkseal pull PATH` - Extract secrets from cluster to plain_secrets.json
- 🚧 `tkseal seal PATH` - Convert plain_secrets.json to sealed_secrets.json
- 

## Previous logic documentation

### ready Command

  **Core Functionality**

  The ready command checks if three critical external dependencies are installed and available in the system PATH:

  1. `kubectl` - Kubernetes command-line tool
  2. `tk` - Grafana Tanka CLI tool
  3. `kubeseal` - Sealed Secrets controller CLI

  **Implementation Details - Detection Method**

 The `ready command` is essentially a health check that ensures the required Kubernetes ecosystem tools are properly installed before
  attempting any secret management operations. It is the foundation for all other `TKSeal` operations. 
 
 Each dependency checker uses the same pattern:
 
 ``def self.exists?
    `which <tool>` != ""
  end
``
  This runs the shell command `which <tool>` and checks if it returns a non-empty string (meaning the tool was found in PATH). 
 Other commands like `diff`, `pull` and `seal` raise an Exception if some of the external tools are not ready

**What each tool does?**

 1. `kubectl (Kubernetes CLI)`

  - Purpose: Interact with Kubernetes clusters
  - Used for: Fetching existing secrets from the cluster
  - Example usage: `kubectl --context=ctx --namespace=ns get secrets -o yaml`

  2. `tk (Grafana Tanka)`

  - Purpose: Kubernetes configuration management using Jsonnet
  - Used for: Getting environment context and namespace info
  - Example usage: `tk status /path/to/environment`
  - Returns: Context and namespace information for the Tanka environment

  3. `kubeseal (Sealed Secrets)`

  - Purpose: Encrypt secrets that can only be decrypted by the cluster
  - Used for: Converting plain text secrets to sealed secrets
  - Example usage: `printf "secret" | kubeseal --raw --namespace ns --name secret-name --context ctx`







