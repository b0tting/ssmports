import json
import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from src.config_loader import ConfigLoader
from src.exceptions import SSMPortForwardError


class TestConfigLoader:
    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary config file."""
        config = {
            "connections": {
                "Test Connection": {
                    "target_host": "example.com",
                    "local_port": 5432,
                    "remote_port": 5432,
                    "jump_instance": "i-1234567890abcdef0",
                }
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    @patch("src.config_loader.ECSIDResolver")
    @patch("src.config_loader.AWSSessions")
    def test_load_config_valid(
        self, mock_aws_sessions, mock_ecs_resolver, temp_config_file
    ):
        mock_aws_sessions.return_value = MagicMock()
        mock_ecs_resolver.return_value = MagicMock()
        loader = ConfigLoader(temp_config_file)
        config, aws_sessions = loader.load_config()
        assert "connections" in config
        assert "Test Connection" in config["connections"]

    def test_load_config_file_not_found(self):
        loader = ConfigLoader("nonexistent.json")
        with pytest.raises(SSMPortForwardError, match="Failed to create AWS session"):
            loader.load_config()

    def test_load_config_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json")
            temp_path = f.name
        try:
            loader = ConfigLoader(temp_path)
            with pytest.raises(
                SSMPortForwardError, match="Failed to parse JSON config"
            ):
                loader.load_config()
        finally:
            os.unlink(temp_path)

    @patch("src.config_loader.ECSIDResolver")
    @patch("src.config_loader.AWSSessions")
    def test_validate_schema_invalid(self, mock_aws_sessions, mock_ecs_resolver):
        mock_aws_sessions.return_value = MagicMock()
        mock_ecs_resolver.return_value = MagicMock()
        loader = ConfigLoader("dummy.json")
        invalid_config = {"invalid": "config"}
        with pytest.raises(
            SSMPortForwardError, match="Configuration validation failed"
        ):
            loader.validate_schema(invalid_config)

    @patch("src.config_loader.ECSIDResolver")
    @patch("src.config_loader.AWSSessions")
    def test_validate_no_double_ports(self, mock_aws_sessions, mock_ecs_resolver):
        mock_aws_sessions.return_value = MagicMock()
        mock_ecs_resolver.return_value = MagicMock()
        loader = ConfigLoader("dummy.json")
        config = {
            "connections": {
                "Conn1": {"local_port": 5432},
                "Conn2": {"local_port": 5432},
            }
        }
        with pytest.raises(SSMPortForwardError, match="Duplicate local_port found"):
            loader.validate_no_double_ports(config)

    @patch("src.config_loader.ECSIDResolver")
    @patch("src.config_loader.AWSSessions")
    def test_validate_instance_id_valid_ec2(self, mock_aws_sessions, mock_ecs_resolver):
        mock_aws_sessions.return_value = MagicMock()
        mock_ecs_resolver.return_value = MagicMock()
        loader = ConfigLoader("dummy.json")
        loader.validate_instance_id("i-1234567890abcdef0")  # Should not raise

    @patch("src.config_loader.ECSIDResolver")
    @patch("src.config_loader.AWSSessions")
    def test_validate_instance_id_valid_ecs(self, mock_aws_sessions, mock_ecs_resolver):
        mock_aws_sessions.return_value = MagicMock()
        mock_ecs_resolver.return_value = MagicMock()
        loader = ConfigLoader("dummy.json")
        loader.validate_instance_id(
            "ecs:my-cluster_12345678901234567890123456789012_12345678901234567890123456789012-0151737364"
        )

    @patch("src.config_loader.ECSIDResolver")
    @patch("src.config_loader.AWSSessions")
    def test_validate_instance_id_invalid(self, mock_aws_sessions, mock_ecs_resolver):
        mock_aws_sessions.return_value = MagicMock()
        mock_ecs_resolver.return_value = MagicMock()
        loader = ConfigLoader("dummy.json")
        with pytest.raises(SSMPortForwardError, match="Invalid instance_id format"):
            loader.validate_instance_id("invalid-id")

    @patch("src.config_loader.ECSIDResolver")
    @patch("src.config_loader.AWSSessions")
    def test_fold_defaults_into_connections(self, mock_aws_sessions, mock_ecs_resolver):
        mock_aws_sessions.return_value = MagicMock()
        mock_ecs_resolver.return_value = MagicMock()
        loader = ConfigLoader("dummy.json")
        config = {
            "profile": "default",
            "region": "us-east-1",
            "jump_instance": "i-123",
            "connections": {
                "Conn1": {"target_host": "host1", "local_port": 1, "remote_port": 1},
                "Conn2": {
                    "target_host": "host2",
                    "local_port": 2,
                    "remote_port": 2,
                    "profile": "other",
                },
            },
        }
        loader.fold_defaults_into_connections(config)
        assert config["connections"]["Conn1"]["profile"] == "default"
        assert config["connections"]["Conn1"]["region"] == "us-east-1"
        assert config["connections"]["Conn1"]["jump_instance"] == "i-123"
        assert config["connections"]["Conn2"]["profile"] == "other"  # Not overwritten

    @patch("src.config_loader.ECSIDResolver")
    @patch("src.config_loader.AWSSessions")
    def test_validate_or_load_instance_ids_resolves_ecs(
        self, mock_aws_sessions, mock_ecs_resolver
    ):
        mock_session = MagicMock()
        mock_aws_sessions.return_value.get_session.return_value = mock_session
        mock_ecs_resolver.return_value.resolve_task_name.return_value = "i-resolved"
        loader = ConfigLoader("dummy.json")
        config = {
            "connections": {
                "Conn1": {
                    "target_host": "host",
                    "local_port": 1,
                    "remote_port": 1,
                    "jump_instance": "some-container",
                    "profile": "test",
                    "region": "us-west-1",
                }
            }
        }
        # Mock validate_instance_id to raise for "some-container"
        with patch.object(
            loader, "validate_instance_id", side_effect=SSMPortForwardError("Invalid")
        ):
            loader.validate_or_load_instance_ids(config)
        assert config["connections"]["Conn1"]["jump_instance"] == "i-resolved"
        mock_ecs_resolver.return_value.resolve_task_name.assert_called_once_with(
            "some-container", mock_session.client("ecs")
        )
