import threading
from .session import SSMSession
from .exceptions import SSMPortForwardError


class SSMPortForwarder:
    def __init__(self):
        self.active_sessions = (
            {}
        )  # {session_id: {"thread": thread, "stop_event": event, "config": config}}

    def start_session(self, ssm_client, label, **kwargs):
        instance_id = kwargs.get("jump_instance")
        target_host = kwargs.get("target_host")
        local_port = kwargs.get("local_port")
        remote_port = kwargs.get("remote_port")

        stop_event = threading.Event()
        session_id_ready = threading.Event()
        shared_data: dict[str, Exception | None] = {"session_id": None, "error": None}

        # Either create a new SSM client because a different profile/region is needed,
        # or use the default one

        def run():
            try:
                with SSMSession(
                    ssm_client,
                    label=label,
                    Target=instance_id,
                    DocumentName="AWS-StartPortForwardingSessionToRemoteHost",
                    Parameters={
                        "host": [target_host],
                        "portNumber": [str(remote_port)],
                        "localPortNumber": [str(local_port)],
                    },
                ) as sess:
                    sid = sess.session["SessionId"]
                    shared_data["session_id"] = sid
                    self.active_sessions[sid] = {
                        "thread": threading.current_thread(),
                        "stop_event": stop_event,
                        "config": {
                            "target_host": target_host,
                            "local_port": local_port,
                            "remote_port": remote_port,
                            "instance_id": instance_id,
                        },
                    }
                    session_id_ready.set()
                    stop_event.wait()
                    self.active_sessions.pop(sid, None)
            except Exception as e:
                shared_data["error"] = e
                session_id_ready.set()

        t = threading.Thread(target=run, daemon=True)
        t.start()

        # Wait for session_id or error to be populated
        if session_id_ready.wait(timeout=30):
            if shared_data["error"]:
                raise shared_data["error"]
            return shared_data["session_id"]
        else:
            raise SSMPortForwardError("Failed to start SSM session within timeout")

    def stop_session(self, session_id):
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["stop_event"].set()
            return True
        return False

    def stop_all(self):
        for session in list(self.active_sessions.values()):
            session["stop_event"].set()
