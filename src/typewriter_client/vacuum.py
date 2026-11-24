import json
import logging
import subprocess
import time
from http.client import HTTPException
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


LOG = logging.getLogger(__name__)
REMOTE_PLAY = "/mnt/data/aplay -q -D plughw:0,0 -t raw -f S16_LE -r 16000 -c 1"
MANUAL_CONTROL_PATH = "/api/v2/robot/capabilities/HighResolutionManualControlCapability"
# Valetudo uses positive angles for clockwise rotation.
MOVEMENT_VECTORS = {
    "w": {"velocity": 0.5, "angle": 0},
    "a": {"velocity": 0, "angle": -60},
    "s": {"velocity": -0.5, "angle": 0},
    "d": {"velocity": 0, "angle": 60},
}


def _manual_control(url: str, payload: dict[str, object]) -> None:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urlopen(request, timeout=3):
        pass


def move(sequence: str, valetudo_url: str) -> None:
    if not sequence or any(key not in MOVEMENT_VECTORS for key in sequence):
        raise ValueError("use a non-empty sequence of w, a, s, and d")
    base = urlsplit(valetudo_url)
    if base.scheme not in {"http", "https"} or not base.hostname or base.query or base.fragment:
        raise ValueError("use an HTTP or HTTPS Valetudo base URL")

    url = valetudo_url.rstrip("/") + MANUAL_CONTROL_PATH
    disable = {"action": "disable"}
    try:
        _manual_control(url, {"action": "enable"})
        for key in sequence:
            command = {"action": "move", "vector": MOVEMENT_VECTORS[key]}
            # Refresh the vector during the burst, as the Valetudo joystick does.
            for _ in range(3):
                _manual_control(url, command)
                time.sleep(0.15)
    except (OSError, HTTPException, ValueError, KeyboardInterrupt):
        try:
            _manual_control(url, disable)
        except (OSError, HTTPException, ValueError) as exc:
            LOG.warning("Could not disable Valetudo manual control: %s", exc)
        raise
    else:
        _manual_control(url, disable)


def speak(text: str, host: str, ssh_key: Path | None) -> None:
    wav = subprocess.run(
        ["espeak-ng", "-b", "1", "--stdout", "--stdin"],
        input=text.encode("utf-8"),
        stdout=subprocess.PIPE,
        check=True,
        timeout=30,
    ).stdout
    pcm = subprocess.run(
        [
            "ffmpeg", "-loglevel", "error", "-i", "pipe:0",
            "-ac", "1", "-ar", "16000", "-f", "s16le", "pipe:1",
        ],
        input=wav,
        stdout=subprocess.PIPE,
        check=True,
        timeout=30,
    ).stdout
    if not pcm:
        raise OSError("speech synthesis produced no audio")

    ssh = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5"]
    if ssh_key is not None:
        ssh.extend(["-i", str(ssh_key.expanduser())])
    duration = len(pcm) / (16_000 * 2)
    subprocess.run(
        [*ssh, "--", host, REMOTE_PLAY],
        input=pcm,
        check=True,
        timeout=15 + duration,
    )
