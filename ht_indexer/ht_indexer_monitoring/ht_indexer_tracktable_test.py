import inspect
import sys
from unittest.mock import Mock

import pytest
import time
import os

from ht_indexer_monitoring.ht_indexer_tracktable import HTIndexerTrackData, HTIndexerTracktable, PROCESSING_STATUS_TABLE_NAME

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)

@pytest.fixture
def mock_db_conn():
    return Mock()

@pytest.fixture
def ht_indexer_tracktable_instance(mock_db_conn):
    return HTIndexerTracktable(db_conn=mock_db_conn)

@pytest.fixture
def create_ht_indexer_track_data():

    # Read the list of IDs from the file
    with open('/'.join([parent, 'document_retriever_service/list_htids_indexer_test.txt']), 'r') as file:
        ids = file.read().splitlines()

    # Create a JSON structure
    data = []
    for idx, ht_id in enumerate(ids, start=1):
        record = {
            "ht_id": ht_id,
            "record_id": f"record_{ht_id}",
            "status": "pending",
            "retriever_status": "pending",
            "generator_status": "pending",
            "indexer_status": "pending",
            "retriever_error": None,
            "generator_error": None,
            "indexer_error": None,
            "created_at": time.strftime('%Y-%m-%d %H:%M:%S'),
            "updated_at": None,
            "processed_at": None
        }
        data.append(HTIndexerTrackData(ht_id=record['ht_id'], record_id=record['record_id'], status=record['status']))

    return data

class TestHTIndexerTracktable:

    def test_create_ht_indexer_track_data_object(self, create_ht_indexer_track_data):
        assert create_ht_indexer_track_data[0].ht_id == "nyp.33433082002258"
        assert create_ht_indexer_track_data[0].record_id == 'record_nyp.33433082002258'
        assert create_ht_indexer_track_data[0].status == 'pending'

    def test_create_table(self, ht_indexer_tracktable_instance, mock_db_conn):
        ht_indexer_tracktable_instance.create_table()
        mock_db_conn.create_table.assert_called_once()

    def test_insert_batch(self, ht_indexer_tracktable_instance, mock_db_conn):
        data = [
            HTIndexerTrackData(
                ht_id="test_ht_id_1",
                record_id="test_record_id_1",
                status="pending",
                retriever_status="pending",
                generator_status="pending",
                indexer_status="pending"
            ),
            HTIndexerTrackData(
                ht_id="test_ht_id_2",
                record_id="test_record_id_2",
                status="pending",
                retriever_status="pending",
                generator_status="pending",
                indexer_status="pending"
            )
        ]
        ht_indexer_tracktable_instance.insert_batch(data)
        assert mock_db_conn.insert_batch.called_once()
        # Check the arguments passed to the insert_batch method, position 0 is the query, position 1 is the data
        assert mock_db_conn.insert_batch.call_args[0][0].startswith(f"INSERT IGNORE INTO {PROCESSING_STATUS_TABLE_NAME}")
        # Check the number of items to be inserted (position 1)
        assert len(mock_db_conn.insert_batch.call_args[0][1]) == 2
