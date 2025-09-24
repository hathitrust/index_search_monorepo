from unittest.mock import patch

from tkseal.kubectl import KubeCtl


class TestKubectl:
    @patch("tkseal.kubectl.shutil.which", return_value="/usr/local/bin/kubectl")
    def test_kubectl_exists_returns_true_when_installed(self, mock_which):
        """Return True when kubectl is on PATH.
        This test mocks shutil.which to simulate kubectl being installed.
        """
        assert KubeCtl.exists() is True
        mock_which.assert_called_once_with("kubectl")

    @patch("tkseal.kubectl.shutil.which", return_value=None)
    def test_kubectl_exists_false_when_not_installed(self, _):
        """Return False when kubectl is not on PATH."""
        assert KubeCtl.exists() is False