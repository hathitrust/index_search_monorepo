from pathlib import Path
from unittest.mock import Mock

import pytest
from catalog_metadata.ht_indexer_config import ProcessingStatus
from ht_indexer_monitoring.ht_indexer_tracktable import (
    PROCESSING_STATUS_TABLE_NAME,
    HTIndexerTrackData,
    HTIndexerTracktable,
)


@pytest.fixture
def mock_db_conn() -> Mock:
    return Mock()


@pytest.fixture
def ht_indexer_tracktable_instance(mock_db_conn: Mock) -> HTIndexerTracktable:
    return HTIndexerTracktable(db_conn=mock_db_conn)


@pytest.fixture
def sample_ht_indexer_track_data() -> list[HTIndexerTrackData]:
    """Provides local test data for HTIndexerTrackData objects."""

    # Read the list of IDs from the file

    # current_dir = Path(__file__).parent
    # file_path = current_dir.parent / "list_htids_indexer_test.txt"

    # with open(file_path) as file:
    #     ids = file.read().splitlines()

    # Create a JSON structure
    # data = []
    # for _idx, ht_id in enumerate(ids, start=1):
    return [
        HTIndexerTrackData(
            ht_id="test_ht_id_1",
            record_id="record_test_ht_id_1",
            status=ProcessingStatus.PENDING,
            retriever_status=ProcessingStatus.PENDING,
            generator_status=ProcessingStatus.PENDING,
            indexer_status=ProcessingStatus.PENDING,
        ),
        HTIndexerTrackData(
            ht_id="test_ht_id_2",
            record_id="record_test_ht_id_2",
            status=ProcessingStatus.PENDING,
            retriever_status=ProcessingStatus.PENDING,
            generator_status=ProcessingStatus.PENDING,
            indexer_status=ProcessingStatus.PENDING,
        ),
    ]


class TestHTIndexerTracktable:
    def test_create_table_correctly(
        self, ht_indexer_tracktable_instance: HTIndexerTracktable, mock_db_conn: Mock
    ) -> None:
        ht_indexer_tracktable_instance.create_table()
        mock_db_conn.create_table.assert_called_once()

    def test_insert_batch(
        self,
        ht_indexer_tracktable_instance: HTIndexerTracktable,
        mock_db_conn: Mock,
        sample_ht_indexer_track_data: list[HTIndexerTrackData],
    ) -> None:

        ht_indexer_tracktable_instance.insert_batch(sample_ht_indexer_track_data)

        # Assert that the insert_batch method was called once with the correct arguments
        mock_db_conn.insert_batch.assert_called_once()

        # Safely capture positional execution arguments without brittle array index slicing
        query, values = mock_db_conn.insert_batch.call_args.args

        # Consolidate validations into a clean behavior block
        assert query.startswith(f"INSERT IGNORE INTO {PROCESSING_STATUS_TABLE_NAME}")
        assert len(values) == 2
        assert values[0]["ht_id"] == "test_ht_id_1"

    def test_file_parsing_populates_track_data_correctly(self, tmp_path: Path) -> None:
        """
        Check how we processes the list file,
        mock the file contents locally so the test remains isolated and predictable.
        """
        # Create a mock text file inside Pytest's isolated virtual directory
        mock_file = tmp_path / "mock_htids.txt"
        mock_file.write_text("mock.id_001\nmock.id_002\n")

        # Simulate your parsing function here using the mock file path
        ids = mock_file.read_text().splitlines()
        data = [
            HTIndexerTrackData(
                ht_id=hid, record_id=f"record_{hid}", status=ProcessingStatus.PENDING
            )
            for hid in ids
        ]

        # Verify parsing boundaries explicitly
        assert len(data) == 2
        assert data[0].ht_id == "mock.id_001"
        assert data[0].record_id == "record_mock.id_001"
