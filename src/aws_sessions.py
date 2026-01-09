import logging

import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError

from src.exceptions import SSMPortForwardError


class AWSSessions:
    def __init__(self):
        # This is put here due to https://github.com/boto/botocore/issues/1841 -
        # or maybe I should just not use the root logger.
        boto3.set_stream_logger(name="botocore.credentials", level=logging.ERROR)

        self.sessions = {}
        self.default_session = None

    def get_session(self, profile_name=None, region_name=None):
        if profile_name is None:
            if not self.default_session:
                self.default_session = self.create_session()
            return self.default_session
        else:
            if profile_name not in self.sessions:
                self.sessions[profile_name] = self.create_session(
                    profile_name=profile_name, region_name=region_name
                )
            return self.sessions.get(profile_name)

    def create_session(self, profile_name=None, region_name=None):
        try:
            if profile_name is None:
                session = (
                    boto3.Session()
                    if region_name is None
                    else boto3.Session(region_name=region_name)
                )
            else:
                session = (
                    boto3.Session(profile_name=profile_name)
                    if region_name is None
                    else boto3.Session(
                        profile_name=profile_name, region_name=region_name
                    )
                )
            sts = session.client("sts")
            sts.get_caller_identity()
            return session
        except (
            NoCredentialsError,
            PartialCredentialsError,
            ClientError,
            Exception,
        ) as e:
            raise SSMPortForwardError(
                f"Failed to create AWS session with profile '{profile_name}': {e}"
            )
