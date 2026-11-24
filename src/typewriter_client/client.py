import argparse
import logging
import math
import shutil
import subprocess
import time
from collections.abc import Callable
from http.client import HTTPException
from pathlib import Path
from urllib.parse import urlsplit

from typewriter_client.events import DEFAULT_EVENTS_URL, Event, fetch_latest
from typewriter_client.vacuum import move, speak


LOG = logging.getLogger(__name__)


def poll(url: str, interval: float, deliver: Callable[[Event], None]) -> None:
    last_handled_id: str | None = None
    while True:
        try:
            event = fetch_latest(url)
        except (OSError, HTTPException, ValueError) as exc:
            LOG.warning("Could not poll events: %s", exc)
        else:
            if event is not None and event.id != last_handled_id:
                try:
                    deliver(event)
                except (OSError, subprocess.SubprocessError) as exc:
                    LOG.warning("Could not deliver event %r: %s", event.id, exc)
                else:
                    last_handled_id = event.id
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Poll for typed text and speak or drive a Valetudo vacuum."
    )
    parser.add_argument("--events-url", default=DEFAULT_EVENTS_URL, help="Full URL of GET /events")
    parser.add_argument(
        "--interval", type=float, default=2, help="Seconds to wait between polls (default: 2)"
    )
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--vacuum-host", help="SSH destination, such as root@192.168.1.67")
    output.add_argument("--dry-run", action="store_true", help="Print new events locally")
    parser.add_argument("--ssh-key", type=Path, help="Optional SSH identity file for the vacuum")
    parser.add_argument("--valetudo-url", help="Valetudo base URL (default: HTTP on the SSH host)")
    args = parser.parse_args()

    try:
        url = urlsplit(args.events_url)
    except ValueError as exc:
        parser.error(f"invalid --events-url: {exc}")
    if url.scheme not in {"http", "https"} or not url.hostname:
        parser.error("--events-url must be an HTTP or HTTPS URL")
    if not math.isfinite(args.interval) or args.interval <= 0:
        parser.error("--interval must be a positive number of seconds")
    if args.vacuum_host is not None:
        missing = [name for name in ("espeak-ng", "ffmpeg", "ssh") if not shutil.which(name)]
        if missing:
            parser.error(f"required commands missing from PATH: {', '.join(missing)}")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    LOG.info("Polling %s every %g seconds", args.events_url, args.interval)

    def deliver(event: Event) -> None:
        if args.dry_run:
            LOG.info("Event %r: %r", event.id, event.text)
        elif event.text.startswith("m:"):
            sequence = event.text[2:].strip()
            try:
                valetudo_url = args.valetudo_url
                if valetudo_url is None:
                    host = args.vacuum_host.rsplit("@", 1)[-1]
                    if args.vacuum_host.startswith("ssh://"):
                        host = urlsplit(args.vacuum_host).hostname
                    if not host:
                        raise ValueError("supply --valetudo-url for this SSH destination")
                    if ":" in host and not host.startswith("["):
                        host = f"[{host}]"
                    valetudo_url = f"http://{host}"
                move(sequence, valetudo_url)
            except (OSError, HTTPException, ValueError) as exc:
                # A failed response may arrive after the robot has already moved.
                LOG.warning("Movement event %r failed: %s", event.id, exc)
            else:
                LOG.info("Moved for event %r (%s)", event.id, sequence)
        else:
            speak(event.text, args.vacuum_host, args.ssh_key)
            LOG.info("Played event %r", event.id)

    try:
        poll(args.events_url, args.interval, deliver)
    except KeyboardInterrupt:
        pass
