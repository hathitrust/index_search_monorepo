<br/>
  <p align="center">
    Solr Query
    <br/>
    <br/>
    <a href="https://github.com/hathitrust/index_search_monorepo/tree/main/app/solr_query">README.md</a>
    -
    <a href="https://github.com/hathitrust/index_search_monorepo/tree/main/app/solr_query">Request Feature</a>
  </p>

## Table Of Contents

* [About the Project](#about-the-project)
* [Built With](#built-with)
* [Phases](#phases)
* [Project Set Up](#project-set-up)
  * [Prerequisites](#prerequisites)
  * [Installation](#installation)
  * [Creating A Pull Request](#creating-a-pull-request)
* [Content Structure](#content-structure)
  * [Project Structure](#project-structure)
  * [Site Maps](#site-maps)
* [Design](#design)
* [Functionality](#functionality)
* [Usage](#usage)
* [Tests](#tests)
* [Hosting](#hosting)
* [Resources](#resources)

## About The Project

This application is a command line tool that allows operations task that focus on retriving documents or/and generating datasets. The application was generated
when the `ht_search` and `ht_indexer` projects were merged into a monorepo. The purpose of this application is to group scripts used to retrieve data and generated datasets using python.

## Built With

* [Python](https://www.python.org/)
* [Poetry](https://python-poetry.org/)
* [Pytest](https://docs.pytest.org/en/stable/)
* [Docker](https://www.docker.com/)
* [Makefile](https://www.gnu.org/software/make/)
* [Black](https://black.readthedocs.io/en/stable/)
* [Ruff](https://ruff.rs/)
* 
## Phases
- Phase 1— Create an script to generate a list of metadata for titles with markers indicating they are Dissertations
  - Retrieve the Zephir marc export that have 502 fields from the file src/data/zephir_upd_20260329.json.gz. Pass as a paramater the address to the .json.gz file
  - generate records for titles in HathiTrust from the Zephir marc export with the words Dissertation/dissertation or PhD/Ph.D.
  - Generate a csv or .xlsx file with the list of records.
  - In the following fields title, author, year published, and any field that would potentially allow us to link to other datasets. The ProQuest UMI number could use where it's applicable
    - ProQuest UMI number could likely be found in one of two places. Per MARC it would be in the 502$o field, which is where dissertation numbers should go. But I believe UMich and possibly others put it in the 035, like this: 035: (ProQuest)disstheses AAI3599037 [for ID pqdiss:3599037]. So either place, but that (ProQuest) prepend should be present 
  - Include any fields indicating topic area or discipline if available
  - Include the query used for documentation.
  - Use pymarc to extract the records that meet the requirement.

- Phase 2—Next Steps



## Project Set Up

In your local environment, you can use the `docker-compose.yml` file to set up the environment to run each script.

The application is designed to run in a Docker container. The Makefile is used to build the Docker image and run the 
container.

In the work directory, you can run the following commands to set up the application:
```bash
cd app/data_operations
# Build the Docker image
make build
# Create the Docker container and set up the environment variables
make run
```

### Prerequisites
* Docker
* Python 3 and Poetry (If you want to run the application in your local environment). See the installation section below.
  
In your workdir,
  
      * `cd app/data_operations` # Change to the data_operations directory
      * `poetry init` # It will set up your local environment and repository details
      * `poetry env use python` # To find the virtual environment directory, created by poetry
      * `source ~/solr_query-TUsF9qpC-py3.11/bin/activate` # Activate the virtual environment in Mac
      * `poetry install` # Install the dependencies in the virtual environment
      * `poetry update` # Update poetry.lock file with the latest versions of the dependencies
      * `C:\Users\user_name\AppData\Local\pypoetry\Cache\virtualenvs\solr_query-d4ARlKJT-py3.12\Scripts\Activate.ps1` # Activate the virtual environment in Windows
      * ** Note **: 
              If you are using a Mac, poetry creates their files in the home directory, e.g. /Users/user_name/Library/Caches/pypoetry/.
              If you are using Windows, poetry creates their files in the home directory, e.g. C:\Users\user_name\AppData\Local\pypoetry\


### Project Structure

The project is structured as follows:

```
    ├── data_operations
    ├── documentation
    │   ├── 
    ├── src
        ├── metadata_generator.py
    ├── tests   
    ├── Dockerfile
    ├── poetry.lock
    ├── pyproject.toml
    ├── README.md 
    ├── Makefile
 ```

## Design

The infrastructure of this application consists on different scripts. Each script will be used for a specific purpose. 
For example, the script `metadata_generator.py` will be used to generate a list of metadata for titles with markers indicating they are Dissertations.

Use `pymarc` to manipulate MARC records. `pymarc` lets you treat those records as Python objects instead of raw text/binary.

### Key Components

* Creating `MarcJsonReader` to stream large files 
* Class Record to represent a full bibliografic record
* Dataclass Field to represent a MARC field (like 245 = title)
* The class Field has a method `get_subfields` to access the subfields of each field. e.g. title = record['245]['a']
* Methods to extract specific metadata from the fields, such as title, author, year, ProQuest UMI number, etc.
* Writing the extracted metadata to a CSV or Excel file using `pandas` for easy analysis and sharing.

**Process to extract metadata**

- Reads binary MARC file
- Parses leader and directory to understand the structure of the record
- Splits fields based on MARC structure
- Converts them into Python objects:
    - Record
    - Field
    - Subfield

The JSON serialization supports UTF-8 character encoding, so you do not deal with encoding details. 

### MARC fields used to identify dissertations and to extract relevant metadata:
- 001: Control number
  - It is a unique identifier for the record (record ID).
  - e.g. 001 12345678
- 502: Dissertation note (contains information about the dissertation, including the degree and institution)
  - $a → Dissertation note (free text)
  - $b → Degree
  - $c → Institution
  - $d → Year
  - $o: may contain the ProQuest UMI number, which is a unique identifier for dissertations in the ProQuest database
  - e.g. 502 ##$aPh.D. dissertation--Harvard University, 2020.
- 035: System control number (may contain the ProQuest UMI number, often with a prefix like (ProQuest)disstheses)
- 245: Title statement (contains the title of the work, which may include keywords like "Dissertation" or "PhD")
  - $a title
  - $b remainder of title (subtitle)
  - $c statement of responsibility (may contain the author's name, editors, etc.)
  - e.g. 245 10$aInsurgent Mexico /$cJohn Reed.
- 653: Index term - uncontrolled (may contain keywords related to the dissertation's topic or discipline)
  -  $a → Term
  - e.g. 653 ##$aMachine learning
         653 ##$aArtificial intelligence
- 655: The type or genre of the work, not its subject
  - $a → Genre/form term
  - $2 → Source of term (e.g., LCGFT)
  - e.g. #7$aHistorical fiction.$2lcgft
- 650: Subjects/topics the work is about (controlled vocabulary) - core field for subject searching
  - $a → Topical term or geographic name as entry element
  - $x → General subdivision
  - $y → Chronological subdivision
  - $z → Geographic subdivision
  - $2 → Source (e.g., LCSH)
  - e.g. 650 #0$aMexico$xHistory$y1910-1946.
- 651: Geographic locations as subjects. It is similar to 650, but specifically for places. 
  - $a → Place name
  - $x, $y, $z → subdivisions 
  - e.g. 651 #0$aMexico$xHistory.
- 500: General note - A free-text note used for any important information that doesn’t fit elsewhere.
  - $a → General note text 
  - e.g. 500 ##$aWritten as a doctoral dissertation at Harvard University in 1949-50.
- 533: Reproduction note - May contain information about the original publication or source of the dissertation.
  - $a → Reproduction note text
  - e.g. 533 ##$aReproduction of the original: New York : Harper & Brothers, 1950.
- 035 - System Control number - may contain the ProQuest UMI number, often with a prefix like (ProQuest)disstheses
  - $a → System control number (primary) (e.g., ProQuest UMI number). It is used to track the record across multiple systems.
  - $z → Canceled/invalid control number
  - e.g. 035 ##$a(ProQuest)disstheses AAI3599037
         035 ##$a(OCoLC)625175
         035 ##$a(MnU)notisAAV7279
         035 ##$z(MnU)Aleph002641651
- 260: Publication information (contains the place of publication, publisher, and date)
  - $a → Place of publication
  - $b → Publisher
  - $c → Date of publication
  - e.g. 260 ##$aCambridge, Mass. :$bHarvard University,$c2020.
- 264: Publication information (alternative to 260, with more specific indicators for publication, distribution, etc.)
  - $a → Place of publication
  - $b → Publisher
  - $c → Date of publication
  - e.g. 264 #1$aNew York :$bPenguin,$c2020. 
         264 #4$c©2019

## Usage

Run it locally:

Copy the .json.gz file (`/htapps/archive/catalog`) to your local environment (`metadata_extractor/data`) and run the script with the following command:

```bash
cd app/data_operations/src/metadata_extractor
python metadata_generator.py -i ~/data_operations/src/data/zephir_upd_20260329.json.gz -o ~/data_operations/src/metadata_extractor/output/dissertation_metadata.csv
```

Run in docker environment:
```bash
# Build the Docker image
make build
# Create the Docker container and set up the environment variables
make run
# Run the script inside the container. The `docker-compose` now mounts `src/metadata_extractor/data` and `src/metadata_extractor/output`,
# so you can edit the Zephir export on your host machine and read the generated CSV without copying files out of the container.

docker compose exec data_operations python src/metadata_extractor/metadata_generator.py -i src/metadata_extractor/data/zephir_upd_20260401.json.gz -o src/metadata_extractor/output/yy.csv
```

**Phase 1**
- Initially, run the script locally
- Retrieve the zephir marc export
- Run the script in docker environment
- Generate the list of metadata for titles with markers indicating they are Dissertations and save it in a csv file. The file should be saved in the `data_operations/output/` directory.

Use case 1: Create an script to generate a list of metadata for titles with markers indicating they are Dissertations
  
