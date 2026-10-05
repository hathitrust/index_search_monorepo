# index_search_monorepo

<br/>
  <p align="center">
    index_search_monorepo
    <br/>
    <br/>
    <a href="https://github.com/hathitrust/index_search_monorepo/issues">Report Bug</a>
    -
    <a href="https://github.com/hathitrust/index_search_monorepo/issues">Request Feature</a>
  </p>

## Table Of Contents

* [About the Project](#about-the-project)
* [Built With](#built-with)
* [Phases](#phases)
* [Project Set Up](#project-set-up)
    * [Prerequisites](#prerequisites)
    * [Installation](#installation)
* [Content Structure](#content-structure)
    * [Project Structure](#project-structure)
    * [Site Maps](#site-maps)
* [Design](#design)
* [Functionality](#functionality)
* [Usage](#usage)
* [Tests](#tests)
* [Hosting](#hosting)
* [Experiments](#experiments)
* [Resources](#resources)

## About the Project

This repository is a monorepo for all the Python code for HathiTrust full-text indexing and search.
It contains multiple subprojects, each with its own functionality and purpose. 

For example, the `ht_search` project is responsible for searching documents in Solr, while the `ht_indexer` 
project is responsible for indexing data in Solr full-text index. There are other projects for
monitoring and tracking the indexing process.

The monorepo structure allows for better organization and management of shared code and dependencies.
The monorepo structure is to maintain and supports collaborative development, and scale new projects and features.

## Getting Started

### Local development (running python outside a container)

1. Clone the repo

```bash
git clone https://github.com/hathitrust/index_search_monorepo.git
```

2. Install dependencies and run tests

See instructions to install uv in the [official documentation](https://docs.astral.sh/uv/getting-started/installation/). On Mac OS, use [homebrew](https://brew.sh/) to install uv, and then use uv to install and manage python versions; see [more info on uv and python on MacOS](https://github.com/hathitrust/index_search_monorepo/wiki/Installing-uv-and-python-on-Mac-OS).

In the checked-out repository:

```bash
make test-all
```

This will:
* install dependencies and create a virtual environment
* build and start containers needed for running tests
* run the tests

If you want to run only specific tests in your local environment, use for
example:

```bash
uv run pytest libs/common_lib/tests/ht_utils_test.py
``` 

### Running tests in containers

This setup does not require installing python or uv locally.

1. Clone the repository:

```bash
git clone github.com/hathitrust/index_search_monorepo.git
```

2. Build containers and run tests

In the checked-out repository:

```bash
docker compose run --rm ht-indexer-tests
docker compose run --rm solr-query-tests
```

### Creating A Pull Request

1. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
2. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
3. Squash your commits (`git rebase -i HEAD~n` where n is the number of commits you want to squash)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Built With
* [Python](https://www.python.org/)
* [UV](https://docs.astral.sh/uv/)
* [Pytest](https://docs.pytest.org/en/stable/)
* [Docker](https://www.docker.com/)
* [Makefile](https://www.gnu.org/software/make/)
* [Black](https://black.readthedocs.io/en/stable/)
* [Ruff](https://ruff.rs/)
* [mypy](https://mypy.readthedocs.io/en/stable/)

* Python development tools
  * UV—Dependency management and packaging tool for Python
  * Pytest—Testing framework
  * Mypy—Static type checker
  * Ruff—Multi-purpose tool that combines linting (including docstring checks) and formatter for Python code


## Project Set Up

All the applications and library run in a docker container, and it is based on the [python:3.11.0a7-slim-buster](https://hub.docker.com/_/python) image. 
Their dependencies are managing to use [UV](https://docs.astral.sh/uv/). 

We use `Makefile` and `Dockerfile` to manage the environment set up and build the image simulating equivalent paths 
in the Docker image and locally.

In the `Makefile` in the root of the monorepo, we have defined commands to build the Docker image, run the containers, 
and execute tests for each project. Each command receives the project name (`APP_NAME`) and project directory (`APP_DIR`) as arguments, 
which are used to build the image and run the container for the specific project.

**Steps to add a dependency for docker images**:

In the Dockerfile,
* In the docker file, we have three stages: `base`, `deps` and `runtime`. 
* `base` stage is used to install the dependencies used by the others stages.
* `deps` stage is used to install the dependencies of the project, and it is based on the `base` stage.
* `runtime` stage is used to copy the code and the virtual environment into the image, and it is based on the `deps` stage.

* In the docker-compose file, we have defined `profiles` for each project, which allows us to run 
the specific project without having to run all the projects in the monorepo. 
* To build the image we define the arguments `APP_NAME` and `APP_DIR` that are used to build the image for the specific project.


## Design 

The design of the `index_search_monorepo` is structured to ensure uniformity between projects and to avoid duplicated 
code. 

1. Monorepo Structure
The monorepo is organized into two main directories: `libs` and `app`. 

* `libs`: Contains shared libraries and utilities that are reused across multiple projects.
* `app`: Contains independent projects, each with its own functionality and dependencies.

2. Shared Libraries
`Shared libraries` are placed in the libs directory (e.g., common_lib and ht_search).
Each shared library has its own `pyproject.toml` file for dependency management.
These libraries are installed in editable mode, that does allow real-time updates during development. Right now,
we have a multistage Dockerfile that builds the image in 3 stages. The first stage is used to install the basic dependencies,
the second stage is used to install each specific application and to create the virtual environment, and the third stage
is to copy the code and the virtual environment into the image. On the second stage, we copy the code into the `workspace` 
folder, which simulates the monorepo structure in the Docker image, then the code won't reflect the changes made 
in the monorepo unless we rebuild the image.

As we are using `UV` for dependency management and this monorepo has multiple applications, in the image we have created
the workspace folder that simulates the monorepo structure. 
* For example an image for the `ht_indexer` project will have the following structure:

```
workspace
├── libs
│   ├── common_lib
│   ├── ht_search
├── app
│   ├── ht_indexer
```

On this monorepo we use the concept of `workspace` to manage the dependencies between the projects. In a workspace, 
each package defines its own `pyproject.toml`, but the workspace shares a single lockfile, ensuring that the workspace 
operates with a consistent set of dependencies. On the `pyproject.toml` file in the root of the monorepo, 
we have defined the members of the workspace.

```
[tool.uv.workspace]
members = ["app/*", "libs/*"]
```

In the `pyproject.toml` file of each application, we define their dependencies inside the monorepo as follows:

```
[tool.uv.sources]
ht-search = {workspace = true, editable = true}
ht-utils = {workspace = true, editable = true}
```

We also add the dependencies in the dependencies section of the `pyproject.toml` file of each application as follows:
```
[tool.poetry.dependencies]
"ht-search",
"ht-utils"
```

For additional information about how using workspaces with UV, you can check [here](https://docs.astral.sh/uv/concepts/projects/workspaces/)

3. Independent Projects
Each project in the app directory is self-contained with its own `pyproject.toml`, `src` and `tests` 
directories. Projects can depend on shared libraries in the libs directory using relative paths. 

To add a new package, you must:

* Add it to the `pyproject.toml` file in the root of this project.
* Update the `Dockerfile` to copy the dependency into the Docker image.
* Update the virtual environment using `uv update`.
* Run tests to ensure everything works as expected.

4. Environment Set up
The monorepo uses `Makefile` and `Dockerfile` to define clear steps for setting up the development environment and 
building Docker images. Docker images are used for deployment, ensuring consistency across environments.
 
5. Testing
Each project and shared library includes a `tests directory` for unit tests.
`pytest` is used as the testing framework, and tests can be run individually for each project or across the entire monorepo.

7. CI/CD Integration
The monorepo is designed to support CI/CD pipelines for automated testing and deployment.
Each project can have its own pipeline configuration, ensuring independent development and deployment.

8. Versioning and Compatibility
By using relative paths for dependencies, all projects share a single version of shared libraries, ensuring compatibility.
Breaking changes in shared libraries are addressed across all dependent projects in a single pull request.

9. Scalability
The modular design allows for the easy addition of new projects or shared libraries without disrupting the existing structure.
The use of Docker ensures that new projects can be deployed independently.

## Struction of the monorepo:

```aiignore
index_search_monorepo
├── README.md
├── Makefile
├── .gitignore
├── libs
├── common_lib
  │   ├── ht_utils
  │   │   ├── pyproject.toml
  │   │   ├── __init__.py
  │   │   ├── src
  │   │   ├── tests
  │   ├── ht_search
  │       ├── pyproject.toml
  │       ├── Dockerfile
  │       ├── src
  │           ├── ht_search
  │           ├── solr_dataset
  │           ├── indexing_data.sh
│   │   ├── tests    
├── app
│   ├── ht_indexer
│       ├── pyproject.toml
│       ├── Dockerfile
│       ├── Makefile
│       ├── src
│           ├── ht_indexer_monitoring
│               ├── ht_indexer_tracktable.py
│       ├── tests
│   ├── ht_searcher
│       ├── pyproject.toml
│       ├── Dockerfile
│       ├── tests
│       ├── src
│           ├── ht_searcher
```

To update or install the dependencies of the monorepo, you can use the `uv sync` command in each project directory:

```
cd app/ht_indexer
uv install
```

`uv sync` # It will install the dependencies of the project and create a virtual environment for the project
`uv run pytest` # It will run the tests of the project using the virtual environment created


* Follow these steps to run Ruff for a check on the code style and linting issues:

On the monorepo root directory, run the following commands:

```bash
uv run -- ruff check $(APP_DIR) # e.g uv run -- ruff check app/ht_indexer
`ruff check . --fix` # To check and fix the code style and linting issues
`mypy .` # To check the type hints and static typing issues
```

Ruff separates fixes issues into Safe fixes and Unsafe fixes. 
Safe fixes are those that can be automatically fixed without any risk of breaking the code, 
while Unsafe fixes are those that may require manual review and testing to ensure they do not introduce new issues.
In the Makefile we have 3 separate commands:

1- `make check-code APP_PATH=app/ht_indexer` - check the code style and linting issues without fixing them.
2- `make fix-code APP_PATH=app/ht_indexer` - check and fix the code style and linting issues.
3- `make fix-code-unsafe APP_PATH=app/ht_indexer` - check and fix the code style and linting issues, including unsafe fixes that may require manual review.

**Note**: Apply the command `fix-code-unsafe` with caution, as it may introduce changes that require manual review and testing to ensure they do not break the code.

* `ruff check` lint all files in the current directory or a directory specified by the user. 
   - It checks for code style and linting issues based on the configured rules.
   - The rules are defined in the `pyproject.toml` file under the `[tool.ruff]` section. 
   - Adding `--fix` flag will automatically fix the issues based on the configured rules. 
   - It modifies the code to adhere to the specified style guidelines.
   - It will fix logical errors, such as unused imports, unused variables, and other code issues that can be automatically resolved.
* `ruff format` formats the code according to the configured style rules. 
   - It is used to ensure consistent code formatting across the project. 
   - It modifies the code to adhere to the specified style guidelines, such as indentation, line length, and spacing.
   - It is focused on formatting the code rather than fixing logical errors.
   - Adding `--diff` flag will show the differences between the original code and the formatted code without modifying the files.


## Resources

- Enter inside the docker file: `docker compose exec full_text_searcher /bin/bash`
- Running the scripts: `docker compose exec full_text_searcher python ht_full_text_search/export_all_results.py --env dev --query '"good"'`

- [Upgrading python, uv, and dependencies](https://github.com/hathitrust/index_search_monorepo/wiki/Upgrading-python,-uv,-and-dependencies)
