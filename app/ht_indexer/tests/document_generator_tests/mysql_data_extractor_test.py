from unittest.mock import Mock

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
