import subprocess


class KubeCtl:
    """Wrapper for kubectl command line tool"""

    @staticmethod
    def exists()->bool:
        """Check if kubectl command line tool is installed and available in PATH"""

        try:
            result = subprocess.run(["which", "kubectl"],
                                    capture_output=True,
                                    check=True,
                                    text=False)
            return result.stdout.strip() != ""
        except (subprocess.SubprocessError, FileNotFoundError):
            return False