import argparse
import json
import os
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ht_search.config_files import config_files_path
from ht_search.export_all_results import SolrExporter
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_mysql import HtMysql, get_mysql_conn
from ht_utils.ht_utils import get_solr_url

from ht_indexer_monitoring.monitoring_arguments import MonitoringServiceArguments

logger = get_ht_logger(name=__name__)

# MySQL table to track the status of the indexer
PROCESSING_STATUS_TABLE_NAME = "fulltext_item_processing_status"
MYSQL_INSERT_BATCH_SIZE = 500

HT_INDEXER_TRACKTABLE = f"""
        CREATE TABLE IF NOT EXISTS {PROCESSING_STATUS_TABLE_NAME} (
            ht_id VARCHAR(255) UNIQUE NOT NULL,
            record_id VARCHAR(255) NOT NULL,
            status ENUM('pending', 'processing', 'failed', 'completed', 'requeued') NOT NULL DEFAULT 'pending',
            retriever_status ENUM('pending', 'processing', 'failed', 'completed') NOT NULL DEFAULT 'pending',
            generator_status ENUM('pending','processing' ,'failed', 'completed') NOT NULL DEFAULT 'pending',
            indexer_status ENUM('pending', 'processing', 'failed', 'completed') NOT NULL DEFAULT 'pending',
            error TEXT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            processed_at TIMESTAMP NULL DEFAULT NULL
        );
        """


@dataclass
class HTIndexerTrackData:
    """Data class to represent a row of the fulltext_item_processing_status table"""

    record_id: str
    ht_id: str
    status: str = "pending"
    retriever_status: str = "pending"
    generator_status: str = "pending"
    indexer_status: str = "pending"
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    processed_at: datetime | None = None


class HTIndexerTracktable:
    """Class to interact with MySQL table fulltext_item_processing_status"""

    def __init__(self, db_conn: HtMysql) -> None:
        self.mysql_obj = db_conn
        self.solr_exporter = SolrExporter(
            get_solr_url(),
            os.environ.get("HT_ENVIRONMENT", "dev"),
            user=os.getenv("SOLR_USER"),
            password=os.getenv("SOLR_PASSWORD"),
        )
        # importlib.resources.files() is typed as Traversable, which typeshed doesn't declare
        # as PathLike -- but for this package (a regular installed directory, not a zip) it is.
        self.query_config_file_path = Path(
            config_files_path,  # type: ignore[arg-type]
            "catalog_search/config_query.yaml",
        )

    def get_catalog_data(
        self,
        query: str
    ) -> Generator[list[HTIndexerTrackData]]:
        """
        Get the data from the catalog.
        :return: List of data
        """

        # '"good"'
        data: list[HTIndexerTrackData] = []
        for x in self.solr_exporter.run_cursor(
            query,
            self.query_config_file_path,
            conf_query="all",
            list_output_fields=["ht_id", "id"],
        ):
            dict_x = json.loads(x)
            if "ht_id" in dict_x:
                if dict_x["ht_id"] is not None:
                    for ht_id in dict_x["ht_id"]:
                        record = {"ht_id": ht_id, "record_id": dict_x["id"], "status": "pending"}
                        data.append(
                            HTIndexerTrackData(
                                ht_id=record["ht_id"],
                                record_id=record["record_id"],
                                status=record["status"],
                            )
                        )

            # Insert in MySQL a batch size of 500 records
            if len(data) >= MYSQL_INSERT_BATCH_SIZE:
                yield data
                data = []
        if len(data) > 0:
            yield data

    def create_table(self) -> None:
        """
        Create the table fulltext_item_processing_status if it does not exist.
        :return: None
        """

        self.mysql_obj.create_table(HT_INDEXER_TRACKTABLE)

    def insert_batch(self, list_items: list[HTIndexerTrackData]) -> None:
        """Inserts a batch of HTIndexerTrackData objects into the database."""
        if not list_items:
            logger.info("No data to insert.")
            return

        insert_query = f"""INSERT IGNORE INTO {PROCESSING_STATUS_TABLE_NAME} (ht_id, record_id,  status, retriever_status, generator_status, indexer_status, error) 
            VALUES (:ht_id, :record_id,  :status, :retriever_status, :generator_status, :indexer_status, :error);
            """
        batch_values = [
            {
                "ht_id": item.ht_id,
                "record_id": item.record_id,
                "status": item.status,
                "retriever_status": item.retriever_status,
                "generator_status": item.generator_status,
                "indexer_status": item.indexer_status,
                "error": item.error,
            }
            for item in list_items
        ]
        self.mysql_obj.insert_batch(insert_query, batch_values)


def main() -> None:

    # Get parameters
    parser = argparse.ArgumentParser()

    init_args_obj = MonitoringServiceArguments(parser)

    # MySQL connection to retrieve documents from the ht database
    db_conn = get_mysql_conn()
    ht_indexer_tracktable = HTIndexerTracktable(db_conn)

    if not ht_indexer_tracktable.mysql_obj.table_exists(PROCESSING_STATUS_TABLE_NAME):
        logger.info(f"Creating {PROCESSING_STATUS_TABLE_NAME} table.")
        ht_indexer_tracktable.create_table()

    total_documents = 0
    for item in ht_indexer_tracktable.get_catalog_data(init_args_obj.query):
        total_documents += len(item)

        # Add data to the table
        ht_indexer_tracktable.insert_batch(item)

        if total_documents >= int(init_args_obj.args.num_found):
            break


if __name__ == "__main__":
    main()
