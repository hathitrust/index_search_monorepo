import shutil


class KubeCtl:
    """Wrapper for kubectl command line tool"""

    @staticmethod
    def exists() -> bool:
        """Return True if the 'kubectl' executable is available on PATH."""
        return shutil.which("kubectl") is not None