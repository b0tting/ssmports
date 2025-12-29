import pytest
import threading
from unittest.mock import MagicMock, patch

from src.forwarder import SSMPortForwarder
from src.exceptions import SSMPortForwardError


class TestSSMPortForwarder:
    @patch("src.forwarder.SSMSession")
    def test_start_session_success(self, mock_ssm_session):
        forwarder = SSMPortForwarder()
        mock_session = MagicMock()
        mock_session.session = {"SessionId": "test-session-id"}
        mock_ssm_session.return_value.__enter__.return_value = mock_session
        mock_ssm_session.return_value.__exit__.return_value = None

        session_id = forwarder.start_session(
            ssm_client=MagicMock(),
            label="test",
            jump_instance="i-123",
            target_host="example.com",
            local_port=8080,
            remote_port=80,
        )

        assert session_id == "test-session-id"
        assert "test-session-id" in forwarder.active_sessions

    @patch("src.forwarder.SSMSession")
    def test_start_session_error(self, mock_ssm_session):
        forwarder = SSMPortForwarder()
        mock_ssm_session.return_value.__enter__.side_effect = Exception("Test error")

        with pytest.raises(Exception, match="Test error"):
            forwarder.start_session(
                ssm_client=MagicMock(),
                label="test",
                jump_instance="i-123",
                target_host="example.com",
                local_port=8080,
                remote_port=80,
            )

    # @patch("src.forwarder.SSMSession")
    # @patch("src.forwarder.threading.Event")
    # def test_start_session_timeout(self, mock_event_class, mock_ssm_session):
    #     forwarder = SSMPortForwarder()
    #     # Mock SSMSession to not set session_id_ready
    #     mock_ssm_session.return_value.__enter__.return_value = MagicMock()
    #     mock_ssm_session.return_value.__exit__.return_value = None

    #     mock_stop_event = MagicMock()
    #     mock_ready_event = MagicMock()
    #     mock_ready_event.wait.return_value = False  # Timeout
    #     mock_event_class.side_effect = [mock_stop_event, mock_ready_event]

    #     with pytest.raises(
    #         SSMPortForwardError, match="Failed to start SSM session within timeout"
    #     ):
    #         forwarder.start_session(
    #             ssm_client=MagicMock(),
    #             label="test",
    #             jump_instance="i-123",
    #             target_host="example.com",
    #             local_port=8080,
    #             remote_port=80,
    #         )

    def test_stop_session_exists(self):
        forwarder = SSMPortForwarder()
        stop_event = threading.Event()
        forwarder.active_sessions["test-id"] = {"stop_event": stop_event}

        result = forwarder.stop_session("test-id")
        assert result is True
        assert stop_event.is_set()

    def test_stop_session_not_exists(self):
        forwarder = SSMPortForwarder()
        result = forwarder.stop_session("nonexistent")
        assert result is False

    def test_stop_all(self):
        forwarder = SSMPortForwarder()
        stop_event1 = threading.Event()
        stop_event2 = threading.Event()
        forwarder.active_sessions = {
            "id1": {"stop_event": stop_event1},
            "id2": {"stop_event": stop_event2},
        }

        forwarder.stop_all()
        assert stop_event1.is_set()
        assert stop_event2.is_set()
