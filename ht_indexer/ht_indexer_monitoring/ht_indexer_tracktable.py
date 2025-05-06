import argparse
import inspect
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Any, Generator

from ht_full_text_search.export_all_results import SolrExporter

from ht_indexer_monitoring.monitoring_arguments import MonitoringServiceArguments
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_mysql import HtMysql, get_mysql_conn

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)

logger = get_ht_logger(name=__name__)

# MySQL table to track the status of the indexer
PROCESSING_STATUS_TABLE_NAME = "fulltext_item_processing_status"
MYSQL_INSERT_BATCH_SIZE = 500

HT_INDEXER_TRACKTABLE = f"""
        CREATE TABLE IF NOT EXISTS {PROCESSING_STATUS_TABLE_NAME} (
            ht_id VARCHAR(255) UNIQUE NOT NULL,
            record_id VARCHAR(255) NOT NULL,
            status ENUM('pending', 'processing', 'failed', 'completed', 'requeued') NOT NULL DEFAULT 'Pending',
            retriever_status ENUM('pending', 'processing', 'failed', 'completed') NOT NULL DEFAULT 'Pending',
            generator_status ENUM('pending','processing' ,'failed', 'completed') NOT NULL DEFAULT 'Pending',
            indexer_status ENUM('pending', 'processing', 'failed', 'completed') NOT NULL DEFAULT 'Pending',
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
    status: str = 'pending'
    retriever_status: str = 'pending'
    generator_status: str = 'pending'
    indexer_status: str = 'pending'
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None

class HTIndexerTracktable:
    """Class to interact with MySQL table fulltext_item_processing_status"""

    def __init__(self, db_conn: HtMysql, solr_exporter: SolrExporter = None):
        self.mysql_obj = db_conn
        self.solr_exporter = solr_exporter

    def get_catalog_data(self, query: str,
                         query_config_file_path: Path,
                         conf_query: str,
                         list_output_fields: List[str]) -> Generator[list[HTIndexerTrackData], Any, None]:
        """
        Get the data from the catalog.
        :return: List of data
        """

        # '"good"'
        data = []
        for x in self.solr_exporter.run_cursor(query, query_config_file_path, conf_query=conf_query,
                                          list_output_fields=list_output_fields):
            dict_x = json.loads(x)
            if "ht_id" in dict_x:
                if dict_x["ht_id"] is not None:
                    for ht_id in dict_x["ht_id"]:
                        record = {
                            "ht_id": ht_id,
                            "record_id": dict_x["id"],
                            "status": "pending"
                        }
                        data.append(HTIndexerTrackData(ht_id=record['ht_id'], record_id=record['record_id'],
                                                       status=record['status']))

            # Insert in MySQL a batch size of 500 records
            if len(data) >= MYSQL_INSERT_BATCH_SIZE:
                yield data
                data = []
        if len(data) > 0:
            yield data
    def create_table(self):
        """
        Create the table fulltext_item_processing_status if it does not exist.
        :return: None
        """

        self.mysql_obj.create_table(HT_INDEXER_TRACKTABLE)

    def insert_batch(self, list_items: List[HTIndexerTrackData]):
        """Inserts a batch of HTIndexerTrackData objects into the database."""
        if not list_items:
            logger.info("No data to insert.")
            return

        insert_query = f"""INSERT IGNORE INTO {PROCESSING_STATUS_TABLE_NAME} (ht_id, record_id,  status, retriever_status, generator_status, indexer_status, error) 
            VALUES (%s, %s, %s, %s, %s, %s, %s);
            """
        batch_values = [
                (item.ht_id, item.record_id, item.status, item.retriever_status, item.generator_status, item.indexer_status, item.error)
                for item in list_items
    ]
        self.mysql_obj.insert_batch(insert_query, batch_values)

def main():

    # Get parameters
    parser = argparse.ArgumentParser()

    init_args_obj = MonitoringServiceArguments(parser)

    # MySQL connection to retrieve documents from the ht database
    db_conn = get_mysql_conn()
    ht_indexer_tracktable = HTIndexerTracktable(db_conn, solr_exporter=init_args_obj.solr_exporter)

    if not ht_indexer_tracktable.mysql_obj.table_exists(PROCESSING_STATUS_TABLE_NAME):
        logger.info(f"Creating {PROCESSING_STATUS_TABLE_NAME} table.")
        ht_indexer_tracktable.create_table()

    total_documents = 0
    for item in ht_indexer_tracktable.get_catalog_data(init_args_obj.query,
                                                    init_args_obj.query_config_file_path,
                                                       init_args_obj.conf_query,
                                                       init_args_obj.output_fields):

        total_documents += len(item)

        # Add data to the table
        ht_indexer_tracktable.insert_batch(item)

        if total_documents >= int(init_args_obj.args.num_found):
            break

if __name__ == "__main__":
    main()