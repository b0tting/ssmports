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

    @staticmethod
    def check_aws_credentials(session=None):
        """Check if AWS credentials are set and valid."""
        if session is None:
            session = boto3.Session()

        try:
            sts = session.client("sts")
            sts.get_caller_identity()
            return True
        except (NoCredentialsError, PartialCredentialsError, Exception):
            return False

    def validate_all(self, session=None):
        """Perform all configuration checks."""
        results = {
            "session_manager_plugin": self.check_session_manager_plugin(),
            "aws_credentials": self.check_aws_credentials(session),
        }
        return results
