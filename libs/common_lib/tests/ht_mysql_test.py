import threading
import time
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy.exc
from ht_utils.ht_env_config import HtEnvConfigMissingError
from ht_utils.ht_mysql import HtMysql, get_mysql_conn
from ht_utils.testing import capture_logs
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool


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
    monkeypatch.setenv("MYSQL_HT_RO_USERNAME", "test-user")
    monkeypatch.setenv("MYSQL_HT_RO_PASSWORD", "test-pass")


class TestHtMysql:
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
    def test_query_mysql_raises_on_sqlalchemy_error(self, mock_create_engine: MagicMock) -> None:
        # Construct successfully first (the fail-fast connect check in __init__ must
        # pass), then break the *next* connect() call, made by query_mysql itself.
        ht_mysql = get_mysql_conn()
        mock_create_engine.return_value.connect.side_effect = sqlalchemy.exc.SQLAlchemyError("boom")

        with pytest.raises(sqlalchemy.exc.SQLAlchemyError, match="boom"):
            ht_mysql.query_mysql("SELECT 1")

    def test_connection_error_is_logged_and_raised_without_the_password(self) -> None:
        # Real mysql-connector error (no mock): nothing is listening for these made-up
        # credentials, so the driver refuses or rejects the connection. The password is
        # deliberately different from the username so a leak can't hide behind it.
        secret = "S3cr3t-Pa55word-do-not-log"

        with capture_logs() as entries, pytest.raises(sqlalchemy.exc.SQLAlchemyError) as exc_info:
            HtMysql("localhost", "some-user", secret, "some_database")

        errors = [e for e in entries if e["log_level"] == "error"]
        assert errors
        assert all(secret not in str(e) for e in errors)
        assert secret not in str(exc_info.value)

    def test_query_mysql_raises_when_connection_pool_is_exhausted(self) -> None:
        # A real (SQLite) pool of one connection with no overflow: the second caller waits
        # pool_timeout seconds and SQLAlchemy raises. This must reach the caller, not become [].
        engine = create_engine(
            "sqlite://",
            poolclass=QueuePool,
            pool_size=1,
            max_overflow=0,
            pool_timeout=0.1,
            connect_args={"check_same_thread": False},
        )
        HtMysql._engine = engine
        ht_mysql = HtMysql.__new__(HtMysql)

        with engine.connect(), pytest.raises(sqlalchemy.exc.TimeoutError):
            ht_mysql.query_mysql("SELECT 1")

        assert issubclass(sqlalchemy.exc.TimeoutError, sqlalchemy.exc.SQLAlchemyError)

    @patch("ht_utils.ht_mysql.create_engine")
    def test_query_mysql_returns_empty_list_when_no_rows_match(
        self, mock_create_engine: MagicMock
    ) -> None:
        ht_mysql = get_mysql_conn()
        conn = mock_create_engine.return_value.connect.return_value.__enter__.return_value
        conn.execute.return_value = []

        assert ht_mysql.query_mysql("SELECT 1 WHERE 0") == []

    @patch("ht_utils.ht_mysql.create_engine")
    def test_query_mysql_returns_rows_as_dicts(self, mock_create_engine: MagicMock) -> None:
        ht_mysql = get_mysql_conn()
        row = MagicMock()
        row._mapping = {"member_id": "umich"}
        conn = mock_create_engine.return_value.connect.return_value.__enter__.return_value
        conn.execute.return_value = [row]

        assert ht_mysql.query_mysql("SELECT member_id FROM t") == [{"member_id": "umich"}]


class TestGetMysqlConnRequiredCredentials:
    def test_get_mysql_conn_raises_when_mysql_user_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(
            "MYSQL_HT_RO_USERNAME", raising=False
        )  # undoes what mysql_credentials fixture just set

        with pytest.raises(HtEnvConfigMissingError, match="MYSQL_HT_RO_USERNAME"):
            get_mysql_conn()

    def test_get_mysql_conn_raises_when_mysql_pass_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(
            "MYSQL_HT_RO_PASSWORD", raising=False
        )  # undoes what mysql_credentials fixture just set

        with pytest.raises(HtEnvConfigMissingError, match="MYSQL_HT_RO_PASSWORD"):
            get_mysql_conn()

    def test_get_mysql_conn_raises_when_mysql_user_is_empty_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An explicitly empty value must be treated the same as unset, not passed
        through as a valid (blank) credential."""
        monkeypatch.setenv(
            "MYSQL_HT_RO_USERNAME", ""
        )  # undoes what mysql_credentials fixture just set to am empty string

        with pytest.raises(HtEnvConfigMissingError, match="MYSQL_HT_RO_USERNAME"):
            get_mysql_conn()
