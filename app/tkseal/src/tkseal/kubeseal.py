import shutil

class KubeSeal:
    """Wrapper for kubeseal command line tool"""

    @staticmethod
    def exists()->bool:
        """Return True if 'kubeseal' executable is available on PATH."""
        return shutil.which('kubeseal') is not None