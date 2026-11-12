## About The Project

This component includes various scripts to generate ad-hoc reports from catalog
data; including these scripts here allows for re-use of other parts of our
python code for handling data from solr.

## Design

* Use `pymarc` to manipulate MARC records. `pymarc` lets you treat those records as Python objects instead of raw text/binary.
* Relies on overall docker, python, project infrastructure for python & solr and makes use of [our other python libraries](../../libs) where applicable

## Usage

### KBART 3 generation

Creates a tab-delimited file (tsv) in KBART 3 format according to the [specs and examples](src/kbart_file_generator/data/KBART3_base_columns_and_instructions_for_each_Sheet1.tsv)

The generated KBART report contains one row for each title in HathiTrust that matches the given institution's print holdings, regardless of access status, as well as one row for each title where any item is viewable in full-text by US users in HathiTrust.

The script queries the catalog solr to pull all metadata necessary to populate the KBART file. The following environment variables must be set:

* `CATALOG_SOLR_RO_URL` - base URL to catalog solr core, for example http://solr-host:8983/solr/catalog
* `SOLR_USER` - basic auth for accessing solr
* `SOLR_PASSWORD` - basic auth for accessing solr

The final output is a tab-delimited file that can be easily imported into a spreadsheet or database for further analysis.

Run the KBART generator locally with:

```bash
uv run python src/kbart_file_generator/kbart_file_generator.py inst_id -o path/to/output
```

where `inst_id` is a [HathiTrust institution ID](https://www.hathitrust.org/member-libraries/resources-for-librarians/institution-identifiers/)

The main report is written to `path/to/output/kbart_inst_id_YYYY-MM-DD.tsv`
The metadata summary sidecar is written to `path/to/output/kbart_inst_id_YYYY-MM-DD.metadata.json`
Progress is logged to stdout along with details of any errors.


## Language report generator 

Generate ISO 639-3 and ISO 639-5 language report from Zephir marc export
- Running `app/data_operations/src/metadata_extractor/report_generation.py` against a Zephir MARC export to produces a 
TSV report containing only `pd` and `pdus` titles that satisfy either the ISO 639-5 or ISO 639-3 criteria.
- Set 1 matches are driven only by codes listed in `app/data_operations/src/metadata_extractor/data/iso639-5.tsv`, 
not by generic three-letter MARC language-code matching.
- Set 2 matches require `041` second indicator `7` and `$2 iso639-3`.
- Output rows include the requested title identifier, title, OCLC number, matched code, 041 value, 546 value where 
relevant, and rights code, with exactly one row per record.
- Automated tests cover both language sets, rights filtering, overlap handling, and TSV output shape.
Run the language report generator locally with:

```bash
uv run python src/metadata_extractor/report_generation.py \
  -f src/metadata_extractor/data/zephir_full_20260430_vufind.json.gz \
  -o src/metadata_extractor/output/language_report.tsv \
  -m src/metadata_extractor/output/iso639_language_report.metadata.json \
  --iso6395-file src/metadata_extractor/data/iso639-5.tsv
``` 

### MARC fields used to identify language and rights per record:

- 008: It is a fixed-length control field that contains coded information about the bibliographic record
  - It does not use subfields
  - It always has 40 characters and each character position has a predefined meaning.
  - There's a general structure but the interpretation of each position depends on the type of material 
  (book, maps, serials, etc.)
  - Position 35–37 is the Language (3-letter code)
  - e.g. 008 001129s2001 xxu f000 0 eng d -> language = eng

- 041: is the Language Code field. It provides detailed information about the languages associated with 
the content of a resource—more precise than what you get from the 008 field
  - This field is used when  a resource contains multiple languages or there are translations or you want to 
  distinguish between the original language and the language of the text.
  - First indicator:
    - 0 → Item is not a translation
    - 1 → Item is a translation
  - Second indicator:
    - Usually blank (#)
  - $a -> Language of the text
  - $b -> Language of summaries or abstracts
  - e.g. multiple language 041 0# $a eng $a fre $a ger

## Identifying Dissertations


Script to generate a list of metadata for titles with markers indicating they are Dissertations

* Retrieves the Zephir marc export that have 502 fields from the file src/data/zephir_upd_20260329.json.gz. Pass as a paramater the address to the .json.gz file
* Generate records for titles in HathiTrust from the Zephir marc export with the words Dissertation/dissertation or PhD/Ph.D.
* Generates a csv or .xlsx file with the list of records.
* Includes various fields including title, author, year published, and other fields that could allow linking to other datasets.
* Includes fields that could include a ProQuest UMI number. Per MARC it would be in the 502$o field, which is where dissertation numbers should go. But UMich and possibly others put it in the 035, like this: 035: (ProQuest)disstheses AAI3599037 [for ID pqdiss:3599037]. So either place, but that (ProQuest) prepend should be present 
* Includes fields indicating topic area or discipline if available
* Uses pymarc to extract the records that meet the requirement.


### Usage

Run it locally:

Copy the .json.gz file (`/htapps/archive/catalog`) to your local environment (`metadata_extractor/data`) and run the script with the following command:

```bash
cd app/data_operations/src/metadata_extractor
python metadata_generator.py -i ~/data_operations/src/data/zephir_upd_20260329.json.gz -o ~/data_operations/src/metadata_extractor/output/dissertation_metadata.csv
```

Run in docker environment:
```bash
# Build the Docker image
make build APP_NAME=data-operations APP_DIR=data_operations  
# Create the Docker container and set up the environment variables

make up APP_NAME=data-operations

# Run the script inside the container. The `docker-compose` now mounts `src/metadata_extractor/data` and `src/metadata_extractor/output`,
# so you can edit the Zephir export on your host machine and read the generated CSV without copying files out of the container.

docker compose exec data_operations python src/metadata_extractor/metadata_generator.py -i src/metadata_extractor/data/zephir_upd_20260401.json.gz -o src/metadata_extractor/output/yy.csv

docker compose exec data_operations /workspace/.venv/bin/python src/metadata_extractor/report_generation.py -f src/metadata_extractor/data/zephir_full_20260430_vufind.json.gz -o src/metadata_extractor/output/language_report.tsv -m src/metadata_extractor/output/iso639_language_report.metadata.json --iso6395-file src/metadata_extractor/data/iso639-5.tsv

# Run tests using the command below. 
docker compose exec data_operations /workspace/.venv/bin/python -m pytest

```

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
