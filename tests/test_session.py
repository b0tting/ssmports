import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.session import SSMSession
from src.exceptions import SSMPortForwardError


class TestSSMSession:
    @patch("src.session.subprocess.Popen")
    @patch("src.session.socket.socket")
    def test_enter_success_no_check(self, mock_socket, mock_popen):
        mock_ssm = MagicMock()
        mock_ssm.start_session.return_value = {"SessionId": "test-id"}
        mock_ssm.meta.region_name = "us-east-1"
        mock_ssm.meta.endpoint_url = "https://ssm.us-east-1.amazonaws.com"
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc

        session = SSMSession(
            mock_ssm,
            check_connection=False,
            Target="i-123",
            DocumentName="test",
            Parameters={"localPortNumber": ["8080"]},
        )
        with session:
            pass

        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        assert "session-manager-plugin" in args[0]
        assert json.loads(args[0][1]) == {"SessionId": "test-id"}
        mock_proc.terminate.assert_called_once()
        mock_ssm.terminate_session.assert_called_once_with(SessionId="test-id")

    @patch("src.session.subprocess.Popen")
    def test_enter_plugin_not_found(self, mock_popen):
        mock_ssm = MagicMock()
        mock_ssm.start_session.return_value = {"SessionId": "test-id"}
        mock_ssm.meta.region_name = "us-east-1"
        mock_ssm.meta.endpoint_url = "https://ssm.us-east-1.amazonaws.com"
        mock_popen.side_effect = FileNotFoundError()

        session = SSMSession(
            mock_ssm,
            Target="i-123",
            DocumentName="test",
            Parameters={"localPortNumber": ["8080"]},
        )
        with pytest.raises(
            SSMPortForwardError, match="The AWS session-manager-plugin is required"
        ):
            with session:
                pass

    @patch("src.session.subprocess.Popen")
    @patch("src.session.socket.socket")
    def test_enter_connection_check_success(self, mock_socket_class, mock_popen):
        mock_ssm = MagicMock()
        mock_ssm.start_session.return_value = {"SessionId": "test-id"}
        mock_ssm.meta.region_name = "us-east-1"
        mock_ssm.meta.endpoint_url = "https://ssm.us-east-1.amazonaws.com"
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0  # Success
        mock_socket_class.return_value = mock_sock

        session = SSMSession(
            mock_ssm, Target="i-123", Parameters={"localPortNumber": ["8080"]}
        )
        with session:
            pass

        mock_sock.connect_ex.assert_called_with(("127.0.0.1", 8080))

    @patch("src.session.subprocess.Popen")
    @patch("src.session.socket.socket")
    @patch("src.session.time.perf_counter")
    def test_enter_connection_check_timeout(
        self, mock_perf_counter, mock_socket_class, mock_popen
    ):
        mock_ssm = MagicMock()
        mock_ssm.start_session.return_value = {"SessionId": "test-id"}
        mock_ssm.meta.region_name = "us-east-1"
        mock_ssm.meta.endpoint_url = "https://ssm.us-east-1.amazonaws.com"
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 1  # Fail
        mock_socket_class.return_value = mock_sock
        mock_perf_counter.side_effect = [
            0,
            10,
            20,
            30,
            40,
            50,
            60,
            70,
        ]  # Simulate time passing

        session = SSMSession(
            mock_ssm,
            timeout=60,
            Target="i-123",
            Parameters={"localPortNumber": ["8080"]},
        )
        with pytest.raises(SSMPortForwardError, match="Unable to connect to 8080"):
            with session:
                pass

    @patch("src.session.subprocess.Popen")
    @patch("src.session.socket.socket")
    def test_enter_process_dies_during_check(self, mock_socket_class, mock_popen):
        mock_ssm = MagicMock()
        mock_ssm.start_session.return_value = {"SessionId": "test-id"}
        mock_ssm.meta.region_name = "us-east-1"
        mock_ssm.meta.endpoint_url = "https://ssm.us-east-1.amazonaws.com"
        mock_proc = MagicMock()
        mock_proc.poll.side_effect = [None, 1]  # Dies
        mock_proc.communicate.return_value = (b"Error output", None)
        mock_popen.return_value = mock_proc
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 1
        mock_socket_class.return_value = mock_sock

        session = SSMSession(
            mock_ssm, Target="i-123", Parameters={"localPortNumber": ["8080"]}
        )
        with pytest.raises(
            SSMPortForwardError, match="session-manager-plugin exited: Error output"
        ):
            with session:
                pass

    @patch("src.session.subprocess.Popen")
    def test_exit_terminate_success(self, mock_popen):
        mock_ssm = MagicMock()
        mock_proc = MagicMock()
        mock_proc.wait.return_value = None
        mock_popen.return_value = mock_proc

        session = SSMSession(mock_ssm)
        session.session = {"SessionId": "test-id"}
        session.proc = mock_proc

        session.__exit__(None, None, None)

        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once_with(timeout=5)
        mock_ssm.terminate_session.assert_called_once_with(SessionId="test-id")

    @patch("src.session.subprocess.Popen")
    def test_exit_kill_on_timeout(self, mock_popen):
        mock_ssm = MagicMock()
        mock_proc = MagicMock()
        mock_proc.wait.side_effect = subprocess.TimeoutExpired("cmd", 5)
        mock_popen.return_value = mock_proc

        session = SSMSession(mock_ssm)
        session.session = {"SessionId": "test-id"}
        session.proc = mock_proc

        session.__exit__(None, None, None)

        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()
        mock_ssm.terminate_session.assert_called_once_with(SessionId="test-id")

    def test_log_with_label(self, capsys):
        mock_ssm = MagicMock()
        session = SSMSession(mock_ssm, label="TestLabel")
        session._log("Test message")
        captured = capsys.readouterr()
        assert "[TestLabel] Test message" in captured.out

    def test_log_without_label(self, capsys):
        mock_ssm = MagicMock()
        session = SSMSession(mock_ssm)
        session._log("Test message")
        captured = capsys.readouterr()
        assert "Test message" in captured.out
