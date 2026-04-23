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

This repository is a monorepo for all the Python code generated as part of the HathiTrust Index Search project. 
It contains multiple subprojects, each with its own functionality and purpose. 

For example, the `ht_search` project is responsible for searching documents in Solr, while the `ht_indexer` 
project is responsible for indexing data in Solr full-text index. There are other projects for
monitoring and tracking the indexing process.

The monorepo structure allows for better organization and management of shared code and dependencies.
The monorepo structure is to maintain and supports collaborative development, and scale new projects and features.

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


## Phases

The project is divided into several phases, each focusing on different aspects of the indexing and searching process.

* **Phase 1**: Create a monorepo merging `ht_search` and `ht_indexer` projects. The script here has used to keep the 
previous commit history of both projects.
* **Phase 1.1**: Create a Docker image for the monorepo, which includes all the necessary dependencies and configurations.
* **Phase 1.2**: Structure the monorepo to include shared libraries and projects, making it easier to manage dependencies and code reuse.
* **Phase 1.3**: Structure `ht_indexer` to ensure all the features are working as expected with the new monorepo structure.
* **Phase 2**: Set up a CI/CD pipeline to automate testing, and deployment for `ht_indexer` project.
* **Phase 3**: Structure `ht_search` project to ensure all the features are working as expected with the new monorepo structure.
* **Phase 4**: Set up a CI/CD pipeline to automate testing, and deployment for `ht_search` project.
* **Phase 5**: Repeat the process for other projects in the monorepo, ensuring that each project is properly structured and tested.
* **Phase 6**: Install the monorepo in editable mode, allowing for real-time updates during development.
  * Define dependencies in editable mode add `develop = true ==> {common-lib = {path = "../../libs/common_lib", develop = true}`
  * This approach is useful to develop using the docker image, as it allows you to edit the code in the 
  monorepo and see the changes reflected in the Docker container without having to rebuild the image every time.
  * I don't know how to do this yet, but I will figure it out.
* Phase 7: Python dependency management migration from Poetry to UV and docker file refactor to use UV for dependency management and application execution.
  * Refactor the Dockerfile to use UV for dependency management and application execution.
  * Update the documentation to reflect the changes in the dependency management and Dockerfile.
  * Manage all the application of this monorepo using a Makefile in the root of the monorepo, which will include commands to build the Docker image, run the container, and execute tests.
* Phase 8: Migrate to a new Python version (from 3.12 to 3.14) and update the dependencies to ensure compatibility with the new Python version.
  * Upgrade the Docker image to use `3.14-slim-trixie` as the base image. Trixie image is based on Debian 13, which is the latest stable version of Debian and 
  it includes newer kernel and security updates, and it is compatible with the latest Python versions.

## Project Set Up

All the applications and library run in a docker container, and it is based on the [python:3.11.0a7-slim-buster](https://hub.docker.com/_/python) image. 
Their dependencies are managing to use [UV](https://docs.astral.sh/uv/). 

We use `Makefile` and `Dockerfile` to manage the environment set up and build the image simulating equivalent paths 
in the Docker image and locally.

In the `Makefile` in the root of the monorepo, we have defined commands to build the Docker image, run the containers, 
and execute tests for each project. Each command receives the project name (APP_NAME) and project directory (APP_DIR) as arguments, 
which are used to build the image and run the container for the specific project.

**Steps to add a dependency**:

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

## CI/CD architecture

How could we use git diff to detect the changes in the monorepo and decide what the service to deploy are?

Next step: create a script to run `git diff` command to identify the changed paths


If there are changes in the `libs` directory, we need to deploy all the services because all of them depend 
on the shared libraries.

### Installation

1. Clone the repo
   ``` git clone https://github.com/hathitrust/index_search_monorepo.git```

2. Set up a development environment with uv

See instructions to install uv in the [official documentation](https://docs.astral.sh/uv/getting-started/installation/).

  In your workdir,
    * Go to an application: `cd app/ht_indexer`
    * `uv synch` # It will install the dependencies of the project and create a virtual environment for the project
    * `uv run pytest app/ht_indexer -v`  It will run the tests of the project using the virtual environment created
    * Use `uv build` to build the project and create a wheel file in the dist/ directory.

Note: This local environment set up is useful for development. As this application dependens on other resources such as
Solr, MySQL, and RabbitMQ, it is recommended to use the Docker environment for testing and running the application. 
Otherwise, you will need to set up these resources locally and configure the application to connect to them, 
which can be complex and time-consuming.

## Usage

To use the monorepo, follow these steps:
1. Clone the repository:
```git clone go.github.com/hathitrust/index_search_monorepo.git```
2. Navigate to the project directory:
```cd index_search_monorepo```
3. Create the Docker image:
 ```
   make build APP_NAME=ht-indexer APP_DIR=ht_indexer
 ```
4. Run the Docker container:
```
   make up APP_NAME=ht-indexer
```

5. Run the tests:
```
   make test APP_NAME=ht-indexer
```

### Creating A Pull Request

1. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
2. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
3. Squash your commits (`git rebase -i HEAD~n` where n is the number of commits you want to squash)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

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

- Use the command `. $env_name/bin/activate` to activate the virtual environment inside the container $env_name is 
the name of the virtual environment created by poetry.
- Enter inside the docker file: `docker compose exec full_text_searcher /bin/bash`
- Running the scripts: `docker compose exec full_text_searcher python ht_full_text_search/export_all_results.py --env dev --query '"good"'`

### Guides to install python and poetry on macOS

Recommendation: Use brew to install python and pyenv to manage the python versions.

* Install python
    * You can read this blog to install python in the right way in
      python: https://opensource.com/article/19/5/python-3-default-mac
* Install poetry:
    * **Good blog to understand and use poetry
      **: https://blog.networktocode.com/post/upgrade-your-python-project-with-poetry/
    * **Poetry docs**: https://python-poetry.org/docs/dependency-specification/
    * **How to manage Python projects with Poetry
      **: https://www.infoworld.com/article/3527850/how-to-manage-python-projects-with-poetry.html

* Useful poetry commands (Find more information about commands [here](https://python-poetry.org/docs/cli))
    * Inside the application folder: See the virtual environment used by the application `` poetry env use python ``
    * Activate the virtual environment: ``source ~/ht-indexer-GQmvgxw4-py3.11/bin/activate``, in Mac poetry creates
      their files in the home directory, e.g. /Users/user_name/Library/Caches/pypoetry/.
* Python Linter:
* Ruff: https://astral.sh/ruff
* Enhancing Python Code Quality: A Comprehensive Guide to Linting with
* Ruff: https://dev.to/ken_mwaura1/enhancing-python-code-quality-a-comprehensive-guide-to-linting-with-ruff-3d6g

### Guide to upgrade python, uv and dependencies

Every January, we need to upgrade the python version to the latest version. When we upgrade the python version, we 
also need to upgrade the dependencies of the project to ensure that they are compatible with the new python version.

Steps to upgrade the python version and dependencies:
- Upgrade the python version in the local environment and in the Dockerfile. e.g. `3.12 -> 3.13`
- Upgrade `uv` version
- project dependencies (libs and app)

Avoid duplicate tooling versions across apps. Common packages should be centralized in the `pyproject.toml` file in the 
root of the monorepo.

```
[dependency-groups]
dev = [
  "ruff>=0.4.2,<0.5",
  "mypy>=1.10,<2",
  "pytest>=8,<9"
]
```

When we upgrade the python version is recommended to check and fix breaking changes first and then upgrade the dependencies. 
This approach allows us to identify any compatibility issues early on and address them before upgrading all the 
dependencies and reducing the risk of breaking the code. We should update `uv` the last, 
as it is the tool we use to manage the dependencies and virtual environments, 
and we want to ensure that it is compatible with the new python version before upgrading it. Upgrade the dependencies
gradually, starting with the most critical ones, and then upgrading the rest of the dependencies. 

#### Upgrade Python version

**Step 1 — (Optional) Upgrade Python on local environment**

 — Check the current python version
`python --version`
 — Upgrade python to the latest version
`brew update`
`brew upgrade`
`brew install python@3.12`
 — Check the python version again
`python --version`

**Step 2 — Update Dockerfile**

```
    ARG PYTHON_VERSION=3.13
    FROM python:${PYTHON_VERSION}-slim-bookworm
```

**Step 3 — Update `pyproject.toml` (ALL projects)**

`requires-python = ">=3.13,<4"`

**Step 4 — Recreate lockfile**

`uv lock --upgrade` 

**Step 5 — Validate environment**
```
uv sync
uv run python --version
```

#### Upgrade `uv`

**Step 1 — Update Dockerfile**
```
ARG UV_VERSION=0.11.7

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
FROM python:${PYTHON_VERSION}-slim-bookworm

COPY --from=uv /uv /bin/uv
```

**Step 2 — (Optional) Update locally**
`curl -Ls https://astral.sh/uv/install.sh | sh`

**Step 3 — Validate**
`uv --version`

####  Upgrade dependencies (controlled)

This step is necessary to ensure that the dependencies are compatible with the new python version. 
It is recommended to upgrade the dependencies selectively (Step 2), starting with the most critical ones, 
and then upgrading the rest of the dependencies. This approach allows you to identify any compatibility 
issues early on and address them before upgrading all the dependencies and reducing the risk of breaking the code.

**Step 1 — Upgrade selectively (recommended)**

`uv lock --upgrade-package <package>`

Example: `uv lock --upgrade-package ruff`

In `pyproject.toml` file, we control the versions of the dependencies e.g. `ruff>=0.4.2,<0.5`, so when we run 
the command `uv lock --upgrade-package ruff` you won't upgrade to the latest version. My recommendation is to upgrade 
the dependencies one by one updating the pyproject.toml file. 

Use the command `uv tree` to see the dependency tree and check the dependencies that need to be updated. 
You can use `uv tree | grep pytest ` to check the version of pytest and see if it is compatible with the new python version.

Use [pip pages](https://pypi.org/project/openpyxl/) to check the latest version of the dependencies and update the `pyproject.toml` file accordingly.

**Step 2 — Or upgrade everything**
`uv lock --upgrade`

**Step 3 — Sync**
`uv sync`

####  Validate the monorepo

Step 1 — (Optional) Run checks

Run this command for all the applications in the monorepo to check the code style and linting issues, 
and to fix them if possible.
```
make check-code APP_PATH=app/ht_indexer
make fix-code APP_PATH=app/ht_indexer
```

Step 2 — Run typing checks

```
make type-check APP_PATH=app/ht_indexer
```

Step 2 — Run tests
```make test-all
```

#### Build the Docker image and run the container to ensure everything works as expected.

```
make build APP_NAME=ht-indexer APP_DIR=ht_indexer
make up APP_NAME=ht-indexer
make test APP_NAME=ht-indexer
```
