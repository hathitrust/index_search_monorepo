from unittest.mock import patch
from tkseal.kubeseal import KubeSeal


class TestKubeSeal:
    @patch("tkseal.kubeseal.shutil.which", return_value="/usr/local/bin/kubeseal")
    def test_kubeseal_exists_returns_true_when_installed(self, mock_which):
        """Return True when kubectl is on PATH.
        This test mocks shutil.which to simulate kubectl being installed.
        """
        assert KubeSeal.exists() is True
        mock_which.assert_called_once_with("kubeseal")

    @patch("tkseal.kubeseal.shutil.which", return_value=None)
    def test_kubeseal_exists_false_when_not_installed(self, _):
        """Return False when kubeseal is not on PATH."""
        assert KubeSeal.exists() is False