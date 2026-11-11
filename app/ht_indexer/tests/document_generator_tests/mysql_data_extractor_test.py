from typing import Any
from unittest.mock import Mock

import pytest
import sqlalchemy.exc
from document_generator.mysql_data_extractor import MysqlMetadataExtractor


class TestMysqlMetadataExtractorBoundParams:
    def test_add_large_coll_id_field_binds_doc_id(self) -> None:
        db_conn = Mock()
        db_conn.query_mysql.return_value = []
        extractor = MysqlMetadataExtractor(db_conn)

        extractor.add_large_coll_id_field("mdp.39015012345678")

        args, kwargs = db_conn.query_mysql.call_args
        query = args[0]
        assert "mdp.39015012345678" not in query
        assert kwargs["params"]["doc_id"] == "mdp.39015012345678"

    def test_add_rights_field_binds_namespace_and_id(self) -> None:
        db_conn = Mock()
        db_conn.query_mysql.return_value = []
        extractor = MysqlMetadataExtractor(db_conn)

        extractor.add_rights_field("mdp.39015012345678")

        args, kwargs = db_conn.query_mysql.call_args
        query = args[0]
        assert "mdp" not in query
        assert "39015012345678" not in query
        assert kwargs["params"] == {"namespace": "mdp", "id": "39015012345678"}

    def test_add_rights_field_query_text_is_constant_regardless_of_sql_injection_payload(
        self,
    ) -> None:

        db_conn = Mock()
        db_conn.query_mysql.return_value = []
        extractor = MysqlMetadataExtractor(db_conn)

        extractor.add_rights_field("mdp.39015012345678")
        benign_query = db_conn.query_mysql.call_args.args[0]

        db_conn.query_mysql.reset_mock()
        extractor.add_rights_field('mdp.39015012345678" OR "1"="1')
        payload_query = db_conn.query_mysql.call_args.args[0]

        assert benign_query == payload_query


class TestMysqlMetadataExtractorDatabaseErrors:
    """A MySQL error must reach the caller (the generator logs it with the ht_id and rejects the
    message) and must not produce a document with missing rights or collection data."""

    @pytest.mark.parametrize(
        "failing_call",
        [
            pytest.param(0, id="rights-query-fails"),
            pytest.param(1, id="large-collection-query-fails"),
        ],
    )
    def test_retrieve_mysql_data_raises_when_a_query_fails(self, failing_call: int) -> None:
        results: list[Any] = [[{"attr": "pd"}], []]
        results[failing_call] = sqlalchemy.exc.SQLAlchemyError("mysql down")
        db_conn = Mock()
        db_conn.query_mysql.side_effect = results
        extractor = MysqlMetadataExtractor(db_conn)

        with pytest.raises(sqlalchemy.exc.SQLAlchemyError, match="mysql down"):
            extractor.retrieve_mysql_data("mdp.39015012345678")

    def test_retrieve_mysql_data_with_empty_results_returns_an_entry(self) -> None:
        db_conn = Mock()
        db_conn.query_mysql.return_value = []
        extractor = MysqlMetadataExtractor(db_conn)

        entry = extractor.retrieve_mysql_data("mdp.39015012345678")

        # Genuinely empty results are not an error: no rights, and the "no large collection" marker
        assert entry == {"coll_id": [0]}
