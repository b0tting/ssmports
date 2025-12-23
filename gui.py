import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import sys
import queue
import webbrowser
import os
from boto3.session import Session
from src.forwarder import SSMPortForwarder
from src.config_loader import ConfigLoader
from src.checker import ConfigChecker

import datetime


class StdoutRedirector:
    def __init__(self, text_widget, log_queue):
        self.text_widget = text_widget
        self.log_queue = log_queue

    def write(self, string):
        if string.strip():
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            self.log_queue.put(f"[{timestamp}] {string}")
        else:
            self.log_queue.put(string)

    def flush(self):
        pass


# TK Code is mostly generated, which Junie is great at.
class SSMPortForwarderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SSM Port Forwarder")
        self.root.geometry("800x600")

        self.checker = ConfigChecker()
        self.forwarder = None
        self.session_configs = {}
        self.active_session_ids = {}  # label -> session_id
        self.buttons = {}  # label -> {start_btn, stop_btn}
        self.ssm_clients = {}  # profile_name -> ssm_client
        self._autostart_triggered = False

        self.log_queue = queue.Queue()
        self._setup_ui()
        self._load_config()
        self._init_forwarder()
        self._render_connections()
        self.root.after(0, self._autostart_sessions)
        self.root.after(100, self._process_logs)

    def _setup_ui(self):
        # Top Controls Frame
        controls_frame = tk.Frame(self.root, padx=10, pady=5)
        controls_frame.pack(fill="x")

        self.reload_btn = tk.Button(
            controls_frame, text="Reload Config", command=self._reload_config
        )
        self.reload_btn.pack(side="left")

        # Connection List Frame
        list_frame = tk.LabelFrame(self.root, text="Connections", padx=10, pady=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Scrollable area for connections
        self.canvas = tk.Canvas(list_frame, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(
            list_frame, orient="vertical", command=self.canvas.yview
        )
        self.scrollable_frame = tk.Frame(self.canvas)

        def _on_scrollable_configure(_):
            bbox = self.canvas.bbox("all")
            if bbox:
                self.canvas.configure(scrollregion=(0, 0, bbox[2], bbox[3]))

        self.scrollable_frame.bind("<Configure>", _on_scrollable_configure)

        container_id = self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw"
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.bind(
            "<Configure>", lambda e: self.canvas.itemconfig(container_id, width=e.width)
        )

        # Mouse wheel support
        def _on_mousewheel(event):
            if self.canvas.yview() == (0.0, 1.0):
                return
            if event.num == 4:  # Linux scroll up
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:  # Linux scroll down
                self.canvas.yview_scroll(1, "units")
            elif sys.platform == "darwin":  # macOS
                self.canvas.yview_scroll(int(-1 * event.delta), "units")
            else:  # Windows
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.canvas.bind_all("<Button-4>", _on_mousewheel)
        self.canvas.bind_all("<Button-5>", _on_mousewheel)

        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.connections_container = self.scrollable_frame

        # Log Window Frame
        log_frame = tk.LabelFrame(self.root, text="Logs", padx=10, pady=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, state="disabled", height=10
        )
        self.log_text.pack(fill="both", expand=True)

        # Redirect stdout
        sys.stdout = StdoutRedirector(self.log_text, self.log_queue)
        sys.stderr = StdoutRedirector(self.log_text, self.log_queue)

    def _load_config(self):
        try:
            config_path = "sessions.json"
            loader = ConfigLoader(config_path)
            config = loader.load_config()
            self.session_configs = config.get("connections", {})
            self.default_profile = config.get("default_profile", "default")
            abs_path = os.path.abspath(config_path)
            print(f"Loaded configuration from: {abs_path}")
        except Exception as e:
            print(f"Error loading config: {e}")
            messagebox.showerror("Config Error", str(e))

    def _reload_config(self):
        # Stop all sessions before reloading if necessary, or just update the list
        # For now, let's just reload the list. If a session is active, it stays active.
        self._load_config()
        self._render_connections()
        print("Configuration reloaded.")

    def _init_forwarder(self, profile=None):
        profile = profile or self.default_profile
        try:
            if not self.checker.check_session_manager_plugin():
                print("Error: session-manager-plugin is not installed.")
                return None

            if profile in self.ssm_clients:
                return self.ssm_clients[profile]

            session = Session(profile_name=profile)
            if not self.checker.check_aws_credentials(session):
                print(f"Error: Invalid AWS credentials for profile '{profile}'.")
                return None

            ssm = session.client("ssm")
            self.ssm_clients[profile] = ssm
            print(f"Successfully initialized AWS profile '{profile}'.")

            if self.forwarder is None:
                self.forwarder = SSMPortForwarder(ssm)

            return ssm
        except Exception as e:
            print(f"Initialization error for profile '{profile}': {e}")
            return None

    def _render_connections(self):
        # Clear existing connections
        for widget in self.connections_container.winfo_children():
            widget.destroy()
        self.buttons = {}

        # Sort labels for consistent display
        sorted_labels = sorted(self.session_configs.keys())

        for label in sorted_labels:
            config = self.session_configs[label]
            frame = tk.Frame(self.connections_container)
            frame.pack(fill="x", pady=2)

            lbl = tk.Label(frame, text=label, width=40, anchor="w")
            lbl.pack(side="left")

            port_lbl = tk.Label(
                frame, text=f"Port {config['local_port']}", width=10, anchor="w"
            )
            port_lbl.pack(side="left")

            start_btn = tk.Button(
                frame,
                text="Start",
                width=10,
                command=lambda l=label: self._start_session(l),
            )
            start_btn.pack(side="left", padx=5)

            stop_btn = tk.Button(
                frame,
                text="Stop",
                width=10,
                state="disabled",
                command=lambda l=label: self._stop_session(l),
            )
            stop_btn.pack(side="left", padx=5)

            self.buttons[label] = {
                "start": start_btn,
                "stop": stop_btn,
            }

            # Link
            if "link" in config:
                link_template = config["link"]
                actual_link = link_template.format(
                    local_port=config["local_port"], remote_port=config["remote_port"]
                )
                link_btn = tk.Label(
                    frame, text="Open Link", fg="blue", cursor="hand2", padx=5
                )
                link_btn.pack(side="left")
                link_btn.bind(
                    "<Button-1>", lambda e, url=actual_link: webbrowser.open(url)
                )

                self.buttons[label]["link"] = link_btn

            # If already active (on reload), update UI
            if label in self.active_session_ids:
                self._update_ui_to_active(label)

    def _autostart_sessions(self):
        """Start any sessions marked with autostart on initial launch."""
        if self._autostart_triggered:
            return
        self._autostart_triggered = True

        for label, config in self.session_configs.items():
            if config.get("autostart") and label not in self.active_session_ids:
                self._start_session(label)

    def _update_ui_to_active(self, label):
        self.buttons[label]["start"].config(state="disabled", text="Start")
        self.buttons[label]["stop"].config(state="normal", text="Stop")

    def _start_session(self, label):
        config = self.session_configs[label]
        profile = config.get("profile", self.default_profile)
        ssm_client = self._init_forwarder(profile)

        if ssm_client is None:
            messagebox.showerror(
                "Error",
                f"Forwarder not initialized. Check AWS credentials for profile '{profile}'.",
            )
            return

        self.buttons[label]["start"].config(state="disabled", text="Starting...")

        def run():
            print(f"Starting session for {label} using profile '{profile}'...")
            try:
                # Filter out 'profile' and 'link' from config before passing to start_session
                session_params = {
                    k: v
                    for k, v in config.items()
                    if k not in ["profile", "link", "autostart"]
                }
                sid = self.forwarder.start_session(
                    ssm_client=ssm_client, label=label, **session_params
                )
                self.active_session_ids[label] = sid
                print(f"Session started: {sid} for {label}")

                def update_ui():
                    self._update_ui_to_active(label)

                self.root.after(0, update_ui)
            except Exception as e:
                print(f"Failed to start {label}: {e}")

                def reset_ui():
                    self.buttons[label]["start"].config(state="normal", text="Start")

                self.root.after(0, reset_ui)

        threading.Thread(target=run, daemon=True).start()

    def _stop_session(self, label):
        sid = self.active_session_ids.get(label)
        if sid:
            print(f"Stopping session {sid} for {label}...")
            self.buttons[label]["stop"].config(state="disabled", text="Stopping...")

            def run_stop():
                if self.forwarder.stop_session(sid):
                    self.active_session_ids.pop(label, None)
                    print(f"Session {sid} stopped.")

                def update_ui():
                    self.buttons[label]["stop"].config(state="disabled", text="Stop")
                    self.buttons[label]["start"].config(state="normal", text="Start")

                self.root.after(0, update_ui)

            threading.Thread(target=run_stop, daemon=True).start()

    def _process_logs(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, msg)
            self.log_text.see(tk.END)
            self.log_text.config(state="disabled")
        self.root.after(100, self._process_logs)

    def on_closing(self):
        if self.forwarder:
            self.forwarder.stop_all()
        self.root.destroy()


if __name__ == "__main__":
    root_tk = tk.Tk()
    app = SSMPortForwarderGUI(root_tk)
    root_tk.protocol("WM_DELETE_WINDOW", app.on_closing)
    root_tk.mainloop()
