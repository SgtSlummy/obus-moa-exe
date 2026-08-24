# Warp AGPL companion boundary

OBus includes a sparse, pinned checkout of Warp under `third_party/warpdotdev-warp` for an optional local terminal companion. The upstream checkout is governed by its included `LICENSE-AGPL`; `crates/warpui` and `crates/warpui_core` retain their own MIT licensing.

## Boundary

- OBus's FastAPI/static UI remains an original implementation.
- The optional companion is the upstream `warp-tui-oss` executable built from the vendored Warp source. It runs in a separate terminal process only after the user explicitly invokes **Launch Warp TUI**.
- OBus communicates with the companion only through the existing local OBus MCP interface (`OBus.exe --mcp`) when the user configures Warp to use it. OBus does not copy credentials, agent session data, or terminal history into its state.
- The OBus executable does not bundle Warp's Rust source or TUI binary by default.

## License and distribution obligations

If a release distributes the Warp companion binary, a combined launcher, or a derivative of AGPL Warp code, distribute the corresponding source under AGPL-3.0-compatible terms and preserve upstream notices. Keep the pinned source checkout and `LICENSE-AGPL` available with that release.

Current upstream source: https://github.com/warpdotdev/warp

## Building the optional companion

The source requires a Rust toolchain and Warp's upstream platform prerequisites. From the vendored checkout:

```text
cargo run -p warp_tui --bin warp-tui-oss
```

After producing the release binary at `target/release/warp-tui-oss` (or `.exe` on Windows) inside that checkout, OBus will expose an enabled **Launch Warp TUI** control in Visual Studio. Use `OBUS_WARP_COMPANION_ROOT` only to select a different Warp source checkout; OBus deliberately refuses arbitrary executable-path overrides.

No credentials, API keys, or OAuth material belong in this setup.
