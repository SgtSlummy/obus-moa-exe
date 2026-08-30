---
name: gortex-16-dirs
description: "Work in the . +16 dirs area — 732 symbols across 40 files (88% cohesion)"
---

# . +16 dirs

732 symbols | 40 files | 88% cohesion

## When to Use

Use this skill when working on files in:
- ``
- `.venv-build\Lib\site-packages\anyio\_backends\_asyncio.py`
- `.venv-build\Lib\site-packages\anyio\_backends\_trio.py`
- `.venv-build\Lib\site-packages\anyio\_core\_exceptions.py`
- `.venv-build\Lib\site-packages\anyio\_core\_sockets.py`
- `.venv-build\Lib\site-packages\anyio\_core\_synchronization.py`
- `.venv-build\Lib\site-packages\anyio\_core\_tasks.py`
- `.venv-build\Lib\site-packages\anyio\_core\_tempfile.py`
- `.venv-build\Lib\site-packages\anyio\abc\_sockets.py`
- `.venv-build\Lib\site-packages\anyio\abc\_streams.py`
- `.venv-build\Lib\site-packages\anyio\functools.py`
- `.venv-build\Lib\site-packages\anyio\lowlevel.py`
- `.venv-build\Lib\site-packages\anyio\streams\buffered.py`
- `.venv-build\Lib\site-packages\anyio\streams\memory.py`
- `.venv-build\Lib\site-packages\anyio\to_interpreter.py`
- `.venv-build\Lib\site-packages\anyio\to_process.py`
- `.venv-build\Lib\site-packages\anyio\to_thread.py`
- `.venv-build\Lib\site-packages\ctranslate2\extensions.py`
- `.venv-build\Lib\site-packages\fastapi\routing.py`
- `.venv-build\Lib\site-packages\httpcore\_backends\trio.py`
- `.venv-build\Lib\site-packages\httpx\_transports\asgi.py`
- `.venv-build\Lib\site-packages\numpy\_core\tests\test_array_coercion.py`
- `.venv-build\Lib\site-packages\numpy\_core\tests\test_errstate.py`
- `.venv-build\Lib\site-packages\numpy\_core\tests\test_overrides.py`
- `.venv-build\Lib\site-packages\numpy\_globals.py`
- `.venv-build\Lib\site-packages\numpy\typing\tests\data\pass\scalars.py`
- `.venv-build\Lib\site-packages\starlette\_utils.py`
- `.venv-build\Lib\site-packages\uvicorn\_types.py`
- `.venv-build\Lib\site-packages\uvicorn\lifespan\on.py`
- `.venv-build\Lib\site-packages\uvicorn\protocols\websockets\websockets_sansio_impl.py`
- `external-call::dep:anyio._core._asyncio_selector_thread.get_selector`
- `external-call::dep:contextvars.copy_context`
- `external-call::dep:exceptiongroup.BaseExceptionGroup`
- `external-call::dep:numpy._core._internal._ufunc_inspect_signature_builder`
- `external-call::dep:trio.lowlevel`
- `external-call::dep:trio.lowlevel.notify_closing`
- `external-call::dep:trio.lowlevel.wait_readable`
- `external-call::dep:trio.lowlevel.wait_writable`
- `external-call::dep:trio.testing.wait_all_tasks_blocked`
- `external-call::dep:trio.to_thread.run_sync`

## Key Files

| File | Symbols |
|------|---------|
| `` | concurrent.futures, future_discard_from_awaited_by, asyncio.current_task, gather, asyncio.get_running_loop, ... |
| `.venv-build\Lib\site-packages\anyio\_backends\_asyncio.py` | current_effective_deadline, _deliver, _RawSocketMixin, acquire_on_behalf_of, coro, ... |
| `.venv-build\Lib\site-packages\anyio\_backends\_trio.py` | deadline, checkpoint_if_cancelled, sock, args, total_tokens, ... |
| `.venv-build\Lib\site-packages\anyio\_core\_exceptions.py` | exception, iterate_exceptions, ConnectionFailed, action, __init__, ... |
| `.venv-build\Lib\site-packages\anyio\_core\_sockets.py` | remote_port, local_port, local_host, tls_standard_compatible, happy_eyeballs_delay, ... |
| `.venv-build\Lib\site-packages\anyio\_core\_synchronization.py` | CapacityLimiterStatistics |
| `.venv-build\Lib\site-packages\anyio\_core\_tasks.py` | _run_coro |
| `.venv-build\Lib\site-packages\anyio\_core\_tempfile.py` | readlines, truncate, read1, size, size, ... |
| `.venv-build\Lib\site-packages\anyio\abc\_sockets.py` | SocketListener |
| `.venv-build\Lib\site-packages\anyio\abc\_streams.py` | ByteSendStream, send_eof, max_bytes, ByteStream, __aiter__, ... |
| `.venv-build\Lib\site-packages\anyio\functools.py` | cache_clear |
| `.venv-build\Lib\site-packages\anyio\lowlevel.py` | RunVar, value, _current_vars, default, get, ... |
| `.venv-build\Lib\site-packages\anyio\streams\buffered.py` | extra_attributes, max_bytes, receive_exactly, nbytes, delimiter, ... |
| `.venv-build\Lib\site-packages\anyio\streams\memory.py` | receive_nowait, send, receive, send_nowait, item, ... |
| `.venv-build\Lib\site-packages\anyio\to_interpreter.py` | current_default_interpreter_limiter, limiter, workers, run_sync, _stop_workers, ... |
| `.venv-build\Lib\site-packages\anyio\to_process.py` | cancellable, run_sync, func, send_raw_command, args, ... |
| `.venv-build\Lib\site-packages\anyio\to_thread.py` | limiter, args, current_default_thread_limiter, func, run_sync, ... |
| `.venv-build\Lib\site-packages\ctranslate2\extensions.py` | __anext__ |
| `.venv-build\Lib\site-packages\fastapi\routing.py` | _keepalive_inserter |
| `.venv-build\Lib\site-packages\httpcore\_backends\trio.py` | _get_socket_stream, info, get_extra_info |
| `.venv-build\Lib\site-packages\httpx\_transports\asgi.py` | receive |
| `.venv-build\Lib\site-packages\numpy\_core\tests\test_array_coercion.py` | MyClass |
| `.venv-build\Lib\site-packages\numpy\_core\tests\test_errstate.py` | func2, main, decorated, func1, func3 |
| `.venv-build\Lib\site-packages\numpy\_core\tests\test_overrides.py` | test_function_like |
| `.venv-build\Lib\site-packages\numpy\_globals.py` | __get__, _SignatureDescriptor, obj, objtype |
| `.venv-build\Lib\site-packages\numpy\typing\tests\data\pass\scalars.py` | __index__, D |
| `.venv-build\Lib\site-packages\starlette\_utils.py` | BaseExceptionGroup |
| `.venv-build\Lib\site-packages\uvicorn\_types.py` | LifespanShutdownEvent |
| `.venv-build\Lib\site-packages\uvicorn\lifespan\on.py` | shutdown |
| `.venv-build\Lib\site-packages\uvicorn\protocols\websockets\websockets_sansio_impl.py` | receive |
| `external-call::dep:anyio._core._asyncio_selector_thread.get_selector` | anyio._core._asyncio_selector_thread.get_selector |
| `external-call::dep:contextvars.copy_context` | contextvars.copy_context |
| `external-call::dep:exceptiongroup.BaseExceptionGroup` | exceptiongroup.BaseExceptionGroup |
| `external-call::dep:numpy._core._internal._ufunc_inspect_signature_builder` | numpy._core._internal._ufunc_inspect_signature_builder |
| `external-call::dep:trio.lowlevel` | trio.lowlevel |
| `external-call::dep:trio.lowlevel.notify_closing` | trio.lowlevel.notify_closing |
| `external-call::dep:trio.lowlevel.wait_readable` | trio.lowlevel.wait_readable |
| `external-call::dep:trio.lowlevel.wait_writable` | trio.lowlevel.wait_writable |
| `external-call::dep:trio.testing.wait_all_tasks_blocked` | trio.testing.wait_all_tasks_blocked |
| `external-call::dep:trio.to_thread.run_sync` | trio.to_thread.run_sync |

## Connected Communities

- **. +31 dirs** (22 cross-edges)
- **. +54 dirs** (12 cross-edges)
- **site-packages/fsspec +7 dirs** (4 cross-edges)
- **site-packages/anyio · _convert_socket_error** (4 cross-edges)
- **. +47 dirs** (3 cross-edges)
- **huggingface_hub/utils +11 dirs** (3 cross-edges)
- **numpy/lib +3 dirs** (3 cross-edges)
- **. +112 dirs** (2 cross-edges)
- **site-packages/pycparser +1 dirs** (2 cross-edges)
- **anyio/_core +4 dirs** (2 cross-edges)
- **. +3 dirs · TypeHelper** (1 cross-edges)
- **site-packages/pydantic +5 dirs** (1 cross-edges)
- **protocols/http +5 dirs** (1 cross-edges)
- **. +4 dirs · draw_figure** (1 cross-edges)
- **anyio/_core +1 dirs · getaddrinfo** (1 cross-edges)
- **site-packages/anyio · __new__** (1 cross-edges)
- **site-packages/filelock +11 dirs** (1 cross-edges)
- **. +1 dirs · _lazy_init** (1 cross-edges)
- **site-packages/anyio · cancel_shielded_checkpoint** (1 cross-edges)
- **. +1 dirs · __init__ · . · _trio** (1 cross-edges)
- **. +1 dirs · _task_started** (1 cross-edges)
- **anyio/_core · get_async_backend** (1 cross-edges)
- **starlette/middleware +5 dirs** (1 cross-edges)
- **. +1 dirs · start_task** (1 cross-edges)
- **. +4 dirs · shutdown** (1 cross-edges)
- **. +12 dirs · load** (1 cross-edges)
- **. +1 dirs · __init__ · . · _asyncio** (1 cross-edges)
- **anyio/_core · wait** (1 cross-edges)

## How to Explore

```
analyze(operation:"communities", id:"community-250")
explore(operation:"context", task:"understand . +16 dirs", format:"gcx")
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
