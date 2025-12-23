import json
import os

try:
    import jsonschema
except ImportError:
    jsonschema = None

from .exceptions import SSMPortForwardError


class ConfigLoader:
    SCHEMA = {
        "type": "object",
        "properties": {
            "default_profile": {"type": "string"},
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
                    },
                    "required": [
                        "target_host",
                        "local_port",
                        "remote_port",
                        "instance_id",
                    ],
                },
            },
        },
        "required": ["connections"],
    }

    def __init__(self, config_path):
        self.config_path = config_path

    def load_config(self):
        """Load and return the configuration from a JSON file."""
        if not os.path.exists(self.config_path):
            raise SSMPortForwardError(f"Config file not found: {self.config_path}")

        with open(self.config_path, "r") as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError as e:
                raise SSMPortForwardError(f"Failed to parse JSON config: {e}")

        # Validate with jsonschema if available
        if jsonschema:
            try:
                jsonschema.validate(instance=config, schema=self.SCHEMA)
            except jsonschema.exceptions.ValidationError as e:
                raise SSMPortForwardError(
                    f"Configuration validation failed: {e.message}"
                )

        # Custom check for unique local_port numbers
        local_ports = []
        connections = config.get("connections", {})
        for name, conn in connections.items():
            port = conn.get("local_port")
            if port in local_ports:
                raise SSMPortForwardError(
                    f"Duplicate local_port found: {port} in connection '{name}'"
                )
            local_ports.append(port)

        return config

    def get_sessions(self):
        """Retrieve the list of session configurations."""
        config = self.load_config()
        connections = config.get("connections", {})
        return list(connections.values())
