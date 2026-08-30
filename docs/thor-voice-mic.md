# Thor Voice Mic

`OBus Relay Pad.cmd` is the dedicated coded microphone client. It serves its UI from local `127.0.0.1`, where browser microphone permission works, and relays to the paired OBus host at `http://100.73.36.108:8000`.

On Thor, enter the same room name and `OBUS_VOICE_LINK_KEY` value configured on the OBus host, then click **Connect** and allow microphone access. Audio is sent only while **Hold to talk** is pressed. On release, OBus transcribes the complete recording locally and creates a guarded `codex` harness task. Relay Pad speaks the transcript and task acknowledgement back; it never claims that a task has already completed. The client does not retain the key or record audio.

Install the Relay Pad with `tools/voice_link/install_relay_pad.ps1`. It needs only Python and a normal browser; enter a different host in the app if needed.
