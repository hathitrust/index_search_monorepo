import subprocess


class TK:
    """Wrapper for TK command line tool"""

    @staticmethod
    def exists()->bool:
        """Check if TK command line tool is installed and available in PATH"""

        try:
            result = subprocess.run(["which", "tk"],
                                    capture_output=True,
                                    check=True,
                                    text=False)
            return result.stdout.strip() != ""
        except (subprocess.SubprocessError, FileNotFoundError):
            return False