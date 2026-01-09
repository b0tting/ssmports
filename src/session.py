import json
import socket
import subprocess
import time


from .exceptions import SSMPortForwardError


class SSMSession:
    """SSM Session Manager context manager class."""

    def __init__(
        self,
        ssm_client,
        logger,
        label: str = None,
        check_connection: bool = True,
        timeout: int = 60,
        **kwargs,
    ):
        self.ssm = ssm_client
        self.logger = logger
        self.label = label
        self.check_connection = check_connection
        self.timeout = timeout
        self.kwargs = kwargs
        self.session = None

    def _log(self, message):
        prefix = f"[{self.label}] " if self.label else ""
        self.logger.info(f"{prefix}{message}")

    def __enter__(self):
        self._log(f"Starting SSM session for target: {self.kwargs.get('Target')}")
        self.session = self.ssm.start_session(**self.kwargs)
        try:
            try:
                self._log("Launching session-manager-plugin...")
                self.proc = subprocess.Popen(
                    (
                        "session-manager-plugin",
                        json.dumps(self.session),
                        self.ssm.meta.region_name,
                        "StartSession",
                        "",
                        json.dumps(self.kwargs),
                        self.ssm.meta.endpoint_url,
                    ),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                )
            except FileNotFoundError:
                raise SSMPortForwardError("The AWS session-manager-plugin is required.")

            if self.check_connection:
                try:
                    port_number = int(self.kwargs["Parameters"]["localPortNumber"][0])
                except (KeyError, IndexError, ValueError):
                    pass
                else:
                    self._log(f"Checking connection to 127.0.0.1:{port_number}...")
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    addr = ("127.0.0.1", port_number)
                    t0 = time.perf_counter()
                    while time.perf_counter() - t0 < self.timeout:
                        if self.proc.poll() is not None:
                            # Process died
                            stdout, _ = self.proc.communicate()
                            error_msg = stdout.decode() if stdout else "Unknown error"
                            raise SSMPortForwardError(
                                f"session-manager-plugin exited: {error_msg}"
                            )

                        if sock.connect_ex(addr) == 0:
                            self._log(
                                f"Successfully connected to 127.0.0.1:{port_number}."
                            )
                            sock.close()
                            break
                        time.sleep(0.25)
                        continue
                    else:
                        raise SSMPortForwardError(
                            f"Unable to connect to {port_number} using session manager."
                        )

            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, "proc") and self.proc:
            self._log("Terminating session-manager-plugin...")
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._log("Force killing session-manager-plugin...")
                self.proc.kill()

        if self.session:
            self.ssm.terminate_session(SessionId=self.session["SessionId"])
            self.session = None
