from unittest.mock import patch

from tkseal.tk import TK

class TestTK:
    @patch("tkseal.tk.shutil.which", return_value="/usr/local/bin/tk")
    def test_tk_exists_returns_true_when_installed(self, mock_which):
        """Return True when tk is on PATH.
        This test mocks shutil.which to simulate tk being installed.
        """
        assert TK.exists() is True
        mock_which.assert_called_once_with("tk")

    @patch("tkseal.tk.shutil.which", return_value=None)
    def test_tk_exists_false_when_not_installed(self, _):
        """Return False when tk is not on PATH."""
        assert TK.exists() is False