# OBus Voice Link test audit

Voice Link is a deliberately small LAN test relay, separate from OBus's local speech-to-text and task-routing features. It lets two browser clients relay short microphone chunks through one OBus host.

## Run the test

1. On the host PC, set a non-empty shared secret for the current shell: `$env:OBUS_VOICE_LINK_KEY = "choose-a-long-random-key"`.
2. Start OBus on a reachable interface, for example: `uvicorn backend.main:app --host 0.0.0.0 --port 8000`.
3. On both PCs, open `http://HOST-IP:8000/voice-link`, enter the same room name and key, and click **Start talking**. Use headphones to prevent feedback.

## What this validates

- Browser microphone permission and MediaRecorder capture on each PC.
- IP reachability to the OBus host and the WebSocket upgrade.
- Room isolation: audio chunks only go to other clients in the same room.
- No OBus recording, transcription, task creation, or disk persistence occurs in this feature.

## Boundaries and next improvements

This is suitable only for a trusted LAN or VPN: the relay uses plain WebSocket when served over HTTP, so it does not encrypt audio in transit. The shared key gates joining but is sent in the initial WebSocket message. Production use should add HTTPS/WSS, short-lived authenticated join tokens, a real-time codec such as WebRTC/Opus, rate limits, peer counts and reconnect metrics. The relay intentionally caps an incoming audio chunk at 1 MiB and drops it otherwise.
