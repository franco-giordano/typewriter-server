# Typewriter Client

Poll an HTTP event feed for typed text and use the latest message to speak or drive a Valetudo vacuum.

## Try it locally

Run the toy server in one terminal and the client in another.

```sh
uv run typewriter-event-server
```

```sh
uv run typewriter-client --dry-run
```

Publish text from a third terminal.

```sh
curl -fsS http://127.0.0.1:8000/events \
  -H 'Content-Type: application/json' \
  --data '{"text":"hello world"}'
```

The client logs the text on the next poll. Publishing the same text again creates a new event. The toy server keeps the latest event in memory and starts empty after a restart.

## Play through the vacuum

Install `espeak-ng`, `ffmpeg`, and the OpenSSH client on the machine running the poller. The vacuum needs the SSH access and `/mnt/data/aplay` setup used by the sibling project's [vacuum script](../digitized-typewriter/speak.sh). Use an SSH identity that works without an interactive prompt.

```sh
uv run typewriter-client \
  --vacuum-host root@192.168.1.67 \
  --ssh-key ~/.ssh/vacuum_key
```

Use your vacuum's SSH destination and identity path. You can also pass an SSH host alias with the identity configured in OpenSSH.

The client turns each new event into 16 kHz, mono, signed 16-bit PCM and sends it over SSH to the vacuum's speaker. To poll a remote feed, add `--events-url https://your-server.example/events`. Use `--interval` to change the two-second wait between polls.

## Drive the vacuum

With the client running in vacuum mode, post text starting with `m ` followed by a sequence of movement keys.

```sh
curl -fsS http://127.0.0.1:8000/events \
  -H 'Content-Type: application/json' \
  --data '{"text":"m wwasd"}'
```

Each `w` moves forward, `s` moves backward, `a` turns left, and `d` turns right. The example drives forward twice, turns left, reverses, and turns right. The client validates the full sequence before driving, sends each key as a short burst, and ends manual control when the sequence finishes.

Movement uses Valetudo's high-resolution manual-control API over HTTP. The client uses the SSH hostname by default. Set `--valetudo-url http://192.168.1.67` if the Web UI is at a different address or the SSH destination is an alias. [Valetudo manual-control API](https://github.com/Hypfer/Valetudo/blob/master/backend/lib/webserver/capabilityRouters/HighResolutionManualControlCapabilityRouter.js)

See the [Events API](EVENTS_API.md) for the response format and delivery behavior.
