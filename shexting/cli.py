import argparse
import ctypes
import itertools
import json
import os
import struct
import syslog
import time
from datetime import datetime, timedelta
from typing import Optional

import requests
from netifaces import AF_INET, ifaddresses, interfaces


class Monitor:
    def __init__(
        self, run_history_file: str, discord_webhook: str, message_prefix: str
    ):
        self._run_history = run_history_file
        self._discord_webhook = discord_webhook
        self._message_prefix = message_prefix
        self._initial_state = None
        self._load_initial_state()

    def _load_initial_state(self):
        if self._initial_state is None:
            metadata = self._metadata()
            if not os.path.isfile(self._run_history):
                self._save_meta(metadata)
        with open(self._run_history) as run_history_file:
            self._initial_state = json.loads(run_history_file.read())

    def _save_meta(self, metadata):
        with open(self._run_history, "w") as run_history_file:
            run_history_file.write(json.dumps(metadata))

    def _metadata(
        self,
        local_ip: Optional[str] = None,
        public_ip: Optional[str] = None,
        uptime: Optional[str] = None,
    ):
        return {"local_ips": local_ip, "public_ip": public_ip, "uptime": uptime}

    def _get_public_ip(self):
        return requests.get("https://httpbin.org/get").json().get("origin")

    def _get_local_ips(self):
        ips = []
        for ifaceName in interfaces():
            addresses = [
                i["addr"]
                for i in ifaddresses(ifaceName).setdefault(AF_INET, [{"addr": "NA"}])
            ]
            ips.append(addresses)
        return sorted(list(filter(lambda l: l != "NA", list(itertools.chain(*ips)))))

    def _sync_send_discord_message(self, message: str):
        headers = {
            "Accept": "application/json",
        }

        json_data = {
            "content": f"{self._message_prefix}:\n{message}",
        }
        try:
            response = requests.post(
                self._discord_webhook, headers=headers, json=json_data
            )
            if response.status_code < 300:
                return True
        except Exception as e:
            syslog.syslog(syslog.LOG_ERR, f"unable to send message: {str(e)}")
        return False

    def _get_uptime(self):
        libc = ctypes.CDLL("libc.so.6")
        buf = ctypes.create_string_buffer(4096)
        if libc.sysinfo(buf) != 0:
            return -1
        uptime = struct.unpack_from("@l", buf.raw)[0]
        sec = timedelta(seconds=uptime)
        d = datetime(1, 1, 1) + sec
        return f"Uptime: {d.day - 1} days, {d.hour} hours, {d.minute} minutes, {d.second} seconds."

    def run(self):
        while True:
            try:
                current_state = self._metadata()
                current_state["public_ip"] = self._get_public_ip()
                current_state["local_ips"] = self._get_local_ips()
                if current_state != self._initial_state:
                    self._initial_state = current_state
                    current_state["uptime"] = self._get_uptime()
                    self._sync_send_discord_message(json.dumps(current_state, indent=4))
                    self._save_meta(current_state)
                    self._initial_state["uptime"] = None
            except Exception as e:
                syslog.syslog(syslog.LOG_ERR, f"unable to obtain info: {str(e)}")
            time.sleep(10)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--history-file",
        required=True,
        type=str,
        help="history file for when the last time ",
    )
    parser.add_argument(
        "--discord-channel",
        required=True,
        type=str,
        help="Discord channel webhook address.",
    )
    parser.add_argument(
        "--message-prefix",
        required=True,
        type=str,
        help="Something to identify this shit.",
    )
    args, _ = parser.parse_known_args()
    m = Monitor(args.history_file, args.discord_channel, args.message_prefix)
    m.run()
