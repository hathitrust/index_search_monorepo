import shutil

class TK:
    """Wrapper for TK command line tool"""

    @staticmethod
    def exists()->bool:
        """Check if TK executable is available in PATH"""
        return shutil.which('tk') is not None
