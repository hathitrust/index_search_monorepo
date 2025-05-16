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
* [Poetry](https://python-poetry.org/)
* [Pytest](https://docs.pytest.org/en/stable/)
* [Docker](https://www.docker.com/)
* [Makefile](https://www.gnu.org/software/make/)
* [Solr](https://lucene.apache.org/solr/)
* [RabbitMQ](https://www.rabbitmq.com/)
* [MariaDB](https://mariadb.org/)
* [Black](https://black.readthedocs.io/en/stable/)
* [Ruff](https://ruff.rs/)

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
  * Define dependencies in editable mode add `develop = true ==> {ht-utils = {path = "../../base/ht_utils", develop = true}`
  * This approach is useful to develop using the docker image, as it allows you to edit the code in the 
  monorepo and see the changes reflected in the Docker container without having to rebuild the image every time.
  * I don't know how to do this yet, but I will figure it out.


## Project Set Up

We use `Makefile` and `Dockerfile` to manage the environment set up and build the image simulating equivalent paths 
in the Docker image and locally.

The deployment process is done through Docker image as showed below:

```
build:
    # Copy project files
	cp -r src $(TMP_DIR)/src

	cp Dockerfile .dockerignore $(TMP_DIR)
	cp pyproject.toml poetry.lock README.md $(TMP_DIR)

	# Copy the shared package written in pyproject.toml
	cp -r ../../base/ht_utils $(TMP_DIR)/ht_utils
	cp -r ../../base/ht_search $(TMP_DIR)/ht_search

	docker build -t $(IMAGE_NAME) $(TMP_DIR)

	rm -rf $(TMP_DIR)
```

In the `Makefile`, a temporary directory is created with the project and its dependencies to build the local package.
Then, in Dockerfile, we copy the project files maintaining the same structure as in the temporary directory. Then, we 
use a multistage Dockerfile to build the image. The first stage is used to install the dependencies, and the second 
stage is used to copy the code into the image.

**Steps to add a dependency**:

In the Dockerfile,
* Copy the dependency on the base stage of the Docker image. `COPY ./ht_search /base/ht_search/`
* Copy the dependency on the final stage of the Docker image. `COPY --chown=${UID}:${GID} ht_search/ ht_search/`
* In the pyproject.toml file, add the dependency to the [tool.poetry.dependencies] section.
       ```ht-search = {path = "../../base/ht_search"}```

## Design 

The design of the `index_search_monorepo` is structured to ensure uniformity between projects and to avoid duplicated 
code. 

1. Monorepo Structure
The monorepo is organized into two main directories: `base` and `projects`. 

* `base`: Contains shared libraries and utilities that are reused across multiple projects.
* `projects`: Contains independent projects, each with its own functionality and dependencies.

2. Shared Libraries
`Shared libraries` are placed in the base directory (e.g., ht_utils and ht_search).
Each shared library has its own `pyproject.toml` file for dependency management.
These libraries are installed in non-editable mode, that does not allow real-time updates during development. Right now,
we have a multistage Dockerfile that builds the image in two stages. The first stage is used to install the dependencies,
and the second stage is used to copy the code into the image. On the second stage, we copy the code into `site-packages`,
then the code won't reflect the changes made in the monorepo unless we rebuild the image.

For simplicity, I decided to install dependencies using relative paths. It has been a challenge managing 
the package paths locally and in the Docker image. As the relative paths become problematic, I have followed the process described
[here](https://medium.com/@mtakanobu2/python-monorepo-centralizing-multiple-projects-and-sharing-code-3c1ab496340a) and
use `Makefile` and `Dockerfile` to create the image simulating equivalent paths in the Docker image and locally.


3. Independent Projects
Each project in the projects directory is self-contained with its own `pyproject.toml`, `Dockerfile`, `src` and `tests` 
directories. Projects can depend on shared libraries in the base directory using relative paths. 

To add a dependency, you must:

* Add the dependency to the `pyproject.toml` file of the project.
* Update the `Dockerfile` to copy the dependency into the Docker image.
* Install the dependency in non-editable mode using Poetry.
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
The modular design allows for easy addition of new projects or shared libraries without disrupting the existing structure.
The use of Docker ensures that new projects can be deployed independently.

## Usage

To use the monorepo, follow these steps:
1. Clone the repository:
```git clone go.github.com/hathitrust/index_search_monorepo.git```
2. Navigate to the project directory:
```cd index_search_monorepo```
3. Create the Docker image:
 ```
   cd projects/ht_indexer
   make build
 ```
4. Run the Docker container:
```
   cd projects/ht_indexer
   make run
```

5. Run the tests:
```
   cd projects/ht_indexer
   make test
```
## Struction of the monorepo:

```aiignore
index_search_monorepo
├── README.md
├── Makefile
├── .gitignore
├── base
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
├── projects
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
```



You could run in each:

```
cd projects/ht_indexer
poetry install
poetry run pytest
poetry lock
```

* To run Ruff

`ruff check .`

* To fix issues automatically:
`ruff check . --fix` 