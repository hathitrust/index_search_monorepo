import threading
import time
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy.exc
from ht_utils.ht_mysql import HtMysql, MissingMysqlConfigError, get_mysql_conn


@pytest.fixture(autouse=True)
def reset_ht_mysql_singleton() -> Generator[None]:
    """HtMysql._engine/_engine_config are class-level singletons; reset them before each
    test so tests don't depend on execution order or leak config across the test session."""
    HtMysql._engine = None
    HtMysql._engine_config = None
    yield
    HtMysql._engine = None
    HtMysql._engine_config = None


@pytest.fixture(autouse=True)
def mysql_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """It runs automatically before every test in this file, so it sets the
    required MySQL credentials for get_mysql_conn(); tests exercising the
    missing-credential path delete them explicitly."""
    monkeypatch.setenv("MYSQL_USER", "test-user")
    monkeypatch.setenv("MYSQL_PASS", "test-pass")


class TestHtMysql:
    @patch("ht_utils.ht_mysql.create_engine")
    def test_create_table(self, mock_create_engine: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_create_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        ht_mysql = get_mysql_conn()

        create_table_sql = """
        CREATE TABLE test_table (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            message VARCHAR(255) UNIQUE NOT NULL,
            status ENUM('pending', 'processing', 'failed', 'completed', 'requeued') NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        ht_mysql.create_table(create_table_sql)

        mock_conn.execute.assert_called_once()
        (executed_stmt,), _ = mock_conn.execute.call_args
        assert str(executed_stmt) == create_table_sql

    @patch("ht_utils.ht_mysql.create_engine")
    def test_table_exits(self, mock_create_engine: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_create_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

        ht_mysql = get_mysql_conn()

        mock_conn.execute.return_value.fetchone.return_value = ("test_table",)
        assert ht_mysql.table_exists("test_table") is True

        mock_conn.execute.return_value.fetchone.return_value = None
        assert ht_mysql.table_exists("non_existent_table") is False

        mock_conn.execute.side_effect = sqlalchemy.exc.SQLAlchemyError("Database error")
        assert ht_mysql.table_exists("error_table") is None

    @patch("ht_utils.ht_mysql.create_engine")
    def test_init_raises_when_database_is_unreachable(self, mock_create_engine: MagicMock) -> None:
        """A bad password or unreachable host must fail at construction time,
        not be silently until the first query happens to run."""
        mock_create_engine.return_value.connect.side_effect = sqlalchemy.exc.SQLAlchemyError(
            "Access denied for user"
        )

        with pytest.raises(sqlalchemy.exc.SQLAlchemyError):
            get_mysql_conn()

    @patch("ht_utils.ht_mysql.create_engine")
    def test_second_construction_with_same_config_reuses_the_engine(
        self, mock_create_engine: MagicMock
    ) -> None:
        HtMysql("host", "user", "pass", "db")
        engine_after_first = HtMysql._engine

        HtMysql("host", "user", "pass", "db")

        assert HtMysql._engine is engine_after_first
        mock_create_engine.assert_called_once()

    @patch("ht_utils.ht_mysql.create_engine")
    def test_second_construction_with_different_config_raises(
        self, mock_create_engine: MagicMock
    ) -> None:
        HtMysql("host", "user", "pass", "db")

        with pytest.raises(
            RuntimeError, match="Engine already created with different configuration"
        ):
            HtMysql("other-host", "user", "pass", "db")

    def test_get_engine_raises_before_any_construction(self) -> None:
        with pytest.raises(RuntimeError, match="HtMysql engine not initialized"):
            HtMysql._get_engine()

    def test_concurrent_construction_with_same_config_creates_engine_exactly_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression test for the _lock: without it, two threads could both observe
        _engine is None and each call create_engine(), leaving the second one to silently
        win. Slowing create_engine down widens the race window so the test would actually
        catch a regression, rather than passing by luck on a fast machine.
        """
        created_engines: list[object] = []

        def slow_create_engine(*args: object, **kwargs: object) -> MagicMock:
            time.sleep(0.01)
            engine = MagicMock()
            created_engines.append(engine)
            return engine

        monkeypatch.setattr("ht_utils.ht_mysql.create_engine", slow_create_engine)

        threads = [
            threading.Thread(target=HtMysql, args=("host", "user", "pass", "db")) for _ in range(8)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(created_engines) == 1

    @patch("ht_utils.ht_mysql.create_engine")
    def test_query_mysql_returns_empty_list_for_blank_query(
        self, mock_create_engine: MagicMock
    ) -> None:
        ht_mysql = get_mysql_conn()

        assert ht_mysql.query_mysql("") == []

    @patch("ht_utils.ht_mysql.create_engine")
    def test_query_mysql_returns_empty_list_on_sqlalchemy_error(
        self, mock_create_engine: MagicMock
    ) -> None:
        # Construct successfully first (the fail-fast connect check in __init__ must
        # pass), then break the *next* connect() call, made by query_mysql itself.
        ht_mysql = get_mysql_conn()
        mock_create_engine.return_value.connect.side_effect = sqlalchemy.exc.SQLAlchemyError("boom")

        assert ht_mysql.query_mysql("SELECT 1") == []


class TestGetMysqlConnRequiredCredentials:
    def test_get_mysql_conn_raises_when_mysql_user_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(
            "MYSQL_USER", raising=False
        )  # undoes what mysql_credentials fixture just set

        with pytest.raises(MissingMysqlConfigError, match="MYSQL_USER"):
            get_mysql_conn()

    def test_get_mysql_conn_raises_when_mysql_pass_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(
            "MYSQL_PASS", raising=False
        )  # undoes what mysql_credentials fixture just set

        with pytest.raises(MissingMysqlConfigError, match="MYSQL_PASS"):
            get_mysql_conn()

    def test_get_mysql_conn_raises_when_mysql_user_is_empty_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An explicitly empty value must be treated the same as unset, not passed
        through as a valid (blank) credential."""
        monkeypatch.setenv(
            "MYSQL_USER", ""
        )  # undoes what mysql_credentials fixture just set to am empty string

        with pytest.raises(MissingMysqlConfigError, match="MYSQL_USER"):
            get_mysql_conn()
