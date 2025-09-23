import subprocess


class KubeSeal:
    """Wrapper for kubeseal command line tool"""

    @staticmethod
    def exists()->bool:
        """Check if kubeseal command line tool is installed and available in PATH"""

        try:
            result = subprocess.run(["which", "kubeseal"],
                                    capture_output=True,
                                    check=True,
                                    text=False)
            return result.stdout.strip() != ""
        except (subprocess.SubprocessError, FileNotFoundError):
            return False