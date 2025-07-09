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
  * Define dependencies in editable mode add `develop = true ==> {common-lib = {path = "../../libs/common_lib", develop = true}`
  * This approach is useful to develop using the docker image, as it allows you to edit the code in the 
  monorepo and see the changes reflected in the Docker container without having to rebuild the image every time.
  * I don't know how to do this yet, but I will figure it out.


## Project Set Up

All the applications and library run in a docker container, and it is based on the [python:3.11.0a7-slim-buster](https://hub.docker.com/_/python) image. 
Their dependencies are managing to use [poetry](https://python-poetry.org/). 


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
	cp -r ../../libs/common_lib/ht_utils $(TMP_DIR)/ht_utils
	cp -r ../../libs/common_lib/ht_search $(TMP_DIR)/ht_search

	docker build -t $(IMAGE_NAME) $(TMP_DIR)

	rm -rf $(TMP_DIR)
```

In the `Makefile`, a temporary directory is created with the project and its dependencies to build the local package.
Then, in Dockerfile, we copy the project files maintaining the same structure as in the temporary directory. Then, we 
use a multistage Dockerfile to build the image. The first stage is used to install the dependencies, and the second 
stage is used to copy the code into the image.

**Steps to add a dependency**:

In the Dockerfile,
* Copy the dependency on the base stage of the Docker image. `COPY ./ht_search /libs/ht_search/`
* Copy the dependency on the final stage of the Docker image. `COPY --chown=${UID}:${GID} ht_search/ ht_search/`
* In the pyproject.toml file, add the dependency to the [tool.poetry.dependencies] section.
       ```ht-search = {path = "../../libs/ht_search"}```

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
These libraries are installed in non-editable mode, that does not allow real-time updates during development. Right now,
we have a multistage Dockerfile that builds the image in two stages. The first stage is used to install the dependencies,
and the second stage is used to copy the code into the image. On the second stage, we copy the code into `site-packages`,
then the code won't reflect the changes made in the monorepo unless we rebuild the image.

For simplicity, I decided to install dependencies using relative paths. It has been a challenge managing 
the package paths locally and in the Docker image. As the relative paths become problematic, I have followed the process described
[here](https://medium.com/@mtakanobu2/python-monorepo-centralizing-multiple-projects-and-sharing-code-3c1ab496340a) and
use `Makefile` and `Dockerfile` to create the image simulating equivalent paths in the Docker image and locally.


3. Independent Projects
Each project in the app directory is self-contained with its own `pyproject.toml`, `Dockerfile`, `src` and `tests` 
directories. Projects can depend on shared libraries in the libs directory using relative paths. 

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

2. Set up a development environment with poetry

  In your workdir,
  
      * `poetry init` # It will set up your local environment and repository details
      * `poetry env use python` # To find the virtual environment directory, created by poetry
      * `source ~/index_search_monorepo-TUsF9qpC-py3.11/bin/activate` # Activate the virtual environment in Mac
      * `C:\Users\user_name\AppData\Local\pypoetry\Cache\virtualenvs\index_search_monorepo-d4ARlKJT-py3.12\Scripts\Activate.ps1` # Activate the virtual environment in Windows
      * ** Note **: 
              If you are using a Mac, poetry creates their files in the home directory, e.g. /Users/user_name/Library/Caches/pypoetry/.
              If you are using Windows, poetry creates their files in the home directory, e.g. C:\Users\user_name\AppData\Local\pypoetry\



## Usage

To use the monorepo, follow these steps:
1. Clone the repository:
```git clone go.github.com/hathitrust/index_search_monorepo.git```
2. Navigate to the project directory:
```cd index_search_monorepo```
3. Create the Docker image:
 ```
   cd app/ht_indexer
   make build
 ```
4. Run the Docker container:
```
   cd app/ht_indexer
   make run
```

5. Run the tests:
```
   cd app/ht_indexer
   make test
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



To update or istall the dependencies of the monorepo, you can use the `poetry update` command in each project directory:

```
cd app/ht_indexer
poetry install
poetry run pytest
poetry update
```

* Follow these steps to run Ruff for a check on the code style and linting issues:

On the monorepo root directory, run the following commands:

```bash
`poetry env use python ` # To find the virtual environment directory, created by poetry
`source ~/index_search_monorepo-TUsF9qpC-py3.11/bin/activate` # Activate the virtual environment in Mac
`ruff check . --fix` # To check and fix the code style and linting issues
```

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
