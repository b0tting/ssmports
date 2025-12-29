import json
import os
import re
from .aws_sessions import AWSSessions
from .ecs_id_resolver import ECSIDResolver

try:
    import jsonschema
except ImportError:
    jsonschema = None

from .exceptions import SSMPortForwardError


class ConfigLoader:
    DEFAULT_CONFIG = """{
      "profile": "my-jump-account",
      "region": "eu-west-1",
      "jump_instance": "my-bastion-container",
      "connections": {
        "Production Database": {
          "target_host": "prod-db.cluster-xxxx.eu-west-1.rds.amazonaws.com",
          "local_port": 5432,
          "remote_port": 5432,
          "autostart": true
        },
        "Staging Database": {
          "target_host": "test-db.cluster-xxxx.eu-west-1.rds.amazonaws.com",
          "local_port": 5433,
          "remote_port": 5432,
          "profile": "my-test-account",
          "jump_instance": "i-0123456789abcdef0"
        },
        "Staging Database over ECS": {
          "target_host": "test-db.cluster-xxxx.eu-west-1.rds.amazonaws.com",
          "local_port": 5434,
          "remote_port": 5432,
          "profile": "my-test-account",
          "jump_instance": "ecs:my-cluster_12345678901234567890123456789012_12345678901234567890123456789012-0151737364"
        }
      }
    }"""

    SCHEMA = {
        "type": "object",
        "properties": {
            "profile": {"type": "string"},
            "region": {"type": "string"},
            "jump_instance": {"type": "string"},
            "connections": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "target_host": {"type": "string"},
                        "local_port": {"type": "integer"},
                        "remote_port": {"type": "integer"},
                        "instance_id": {"type": "string"},
                        "link": {"type": "string"},
                        "profile": {"type": "string"},
                        "autostart": {"type": "boolean"},
                    },
                    "required": [
                        "target_host",
                        "local_port",
                        "remote_port",
                    ],
                },
            },
        },
        "required": ["connections"],
    }

    def __init__(self, config_path):
        self.config_path = config_path
        self.ecs_id_resolver = ECSIDResolver()
        self.aws_sessions = AWSSessions()

    def validate_schema(self, config):
        try:
            jsonschema.validate(instance=config, schema=self.SCHEMA)
        except jsonschema.exceptions.ValidationError as e:
            raise SSMPortForwardError(f"Configuration validation failed: {e.message}")

    def validate_no_double_ports(self, config):
        local_ports = []
        connections = config.get("connections", {})
        for name, conn in connections.items():
            port = conn.get("local_port")
            if port in local_ports:
                raise SSMPortForwardError(
                    f"Duplicate local_port found: {port} in connection '{name}'"
                )
            local_ports.append(port)

    def validate_instance_id(self, instance_id):
        ec2_instance_regex = r"^i-[0-9a-fA-F]{8,17}$"
        # See https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-sessions-start.html
        # for ECS instance format
        ecs_instance_regex = (
            r"^ecs:[A-Za-z0-9-]{1,255}_[a-f0-9]{32}_[a-f0-9]{32}-[\d]{10}$"
        )
        if not re.match(ec2_instance_regex, instance_id) and not re.match(
            ecs_instance_regex, instance_id
        ):
            raise SSMPortForwardError(f"Invalid instance_id format: {instance_id}")

    def validate_or_load_instance_ids(self, config):
        for name in config.get("connections", {}):
            connection = config["connections"][name]
            instance_id = connection.get("jump_instance", "")
            try:
                self.validate_instance_id(instance_id)
            except SSMPortForwardError:
                session = self.aws_sessions.get_session(
                    profile_name=connection.get("profile"),
                    region_name=connection.get("region"),
                )
                connection["jump_instance"] = self.ecs_id_resolver.resolve_task_name(
                    connection["jump_instance"], session.client("ecs")
                )

    def fold_defaults_into_connections(self, config):
        defaults = {}
        for default in ["profile", "region", "jump_instance"]:
            if default in config:
                defaults[default] = config[default]

        for name in config["connections"]:
            connection = config["connections"][name]
            for key, value in defaults.items():
                if key not in connection:
                    connection[key] = value

    def create_default_config_file(self, config_path):
        if not os.path.exists(config_path):
            with open(config_path, "w") as f:
                f.write(self.DEFAULT_CONFIG)
            full_path = os.path.abspath(config_path)
            print(
                f"No sessions.json found, created default configuration at {full_path}"
            )

    def load_config(self):
        """Load and return the configuration from a JSON file."""
        if not os.path.exists(self.config_path):
            self.create_default_config_file(self.config_path)

        with open(self.config_path, "r") as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError as e:
                raise SSMPortForwardError(f"Failed to parse JSON config: {e}")

        self.validate_schema(config)
        self.fold_defaults_into_connections(config)
        self.validate_no_double_ports(config)
        self.validate_or_load_instance_ids(config)

        return config, self.aws_sessions
