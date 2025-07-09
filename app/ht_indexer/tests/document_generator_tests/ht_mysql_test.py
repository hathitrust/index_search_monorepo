from unittest.mock import Mock, patch

import mysql.connector
from document_generator.ht_mysql import get_mysql_conn


class TestHtMysql:

    @patch('document_generator.ht_mysql.HtMysql.get_connection_from_pool')
    def test_create_table(self, mock_connect):

        # Create an instance of HtMysql and call the create_table method
        ht_mysql = get_mysql_conn()

        # Mock the database connection and cursor
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        ht_mysql.get_connection_from_pool = Mock(return_value=mock_conn)

        # SQL statement to create a table
        create_table_sql = """
        CREATE TABLE test_table (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            message VARCHAR(255) UNIQUE NOT NULL,
            status ENUM('pending', 'processing', 'failed', 'completed', 'requeued') NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """


        ht_mysql.create_table(create_table_sql)

        # Assert that the cursor's execute method was called with the correct SQL statement
        mock_cursor.execute.assert_called_once_with(create_table_sql)
        # Assert that the connection's commit method was called
        mock_conn.commit.assert_called_once()

    @patch('document_generator.ht_mysql.HtMysql.get_connection_from_pool')
    def test_table_exits(self, mock_connect):

        ht_mysql = get_mysql_conn()

        # Mock the database connection and cursor
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        ht_mysql.get_connection_from_pool = Mock(return_value=mock_conn)

        # Mock the result of the SHOW TABLES query
        mock_cursor.fetchone.return_value = ('test_table',)
        assert ht_mysql.table_exists('test_table') is True

        # Test when table does not exist
        mock_cursor.fetchone.return_value = None
        assert ht_mysql.table_exists('non_existent_table') is False

        # Test when MySQL raises an error
        mock_cursor.execute.side_effect = mysql.connector.Error("Database error")
        assert ht_mysql.table_exists('error_table') is None