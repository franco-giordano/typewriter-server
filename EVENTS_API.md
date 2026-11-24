# Typed Text Events API

## `GET /events`

Expose this endpoint on the server that receives typed text. The client polls it without query parameters or a request body and sends `Accept: application/json`.

```http
GET /events HTTP/1.1
Host: your-server.example
Accept: application/json
```

Return `200 OK` with a UTF-8 JSON body. Set `Content-Type: application/json` and `Cache-Control: no-store` so each poll can see fresh events.

```json
{
  "events": [
    {"id": "6d081913-347d-48a6-9fd3-bf1f53a7e988", "text": "hello"},
    {"id": "4be2d135-823d-4b92-ade7-adcc12d55a5a", "text": "hello world"}
  ]
}
```

| Field | Type | Meaning |
| --- | --- | --- |
| `events` | Array | Events in publication order, with the newest last. Returning only the newest event is sufficient. |
| `id` | String | A stable, non-empty ID unique to this publication. Generate a new ID for each submission, even if its text matches an earlier event. |
| `text` | String | The original non-blank Unicode text, without NUL characters. |

Before any events have been published, return `{"events":[]}` with `200 OK`. Once events exist, keep the current newest event available until a newer one is published. Keep its ID and text stable across polls.

## Delivery behavior

The first successful poll can act on the event already on the server. Each poll considers the last event in the array. If several events arrive between polls, the client acts on the newest one and skips the intermediate events.

The client remembers the last handled ID for the lifetime of the process. If speech playback fails, it retries that event on a later poll while the event is still the latest. Errors reading the event feed leave the last handled ID in place. Restarting the client makes the current newest event eligible again.

Text beginning with `m ` is a movement command for the vacuum. Use lowercase `w` for forward, `a` for a left turn, `s` for backward, and `d` for a right turn. For example, publish `{"text":"m wwasd"}` through the same event feed. The client logs malformed commands and treats each movement event as handled after one attempt, since a failed request may already have moved the robot.

## Toy server publishing endpoint

The local simulator also accepts `POST /events` with `Content-Type: application/json` and a body such as `{"text":"hello world"}`. It returns `201 Created` with the new event object and makes that event available to the next `GET /events`. The simulator accepts request bodies up to 64 KiB.
