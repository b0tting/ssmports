import subprocess
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError


class ConfigChecker:
    @staticmethod
    def check_session_manager_plugin():
        """Check if session-manager-plugin is installed and accessible."""
        try:
            subprocess.run(
                ["session-manager-plugin", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def validate_all(self, session=None):
        """Perform all configuration checks."""
        results = {
            "session_manager_plugin": self.check_session_manager_plugin(),
        }
        return results
