# OBus benchmark plan

This plan measures four separate concerns without conflating them:

1. OBus deliberation latency.
2. Room and forum concurrency behavior.
3. Ollama residency, VRAM, and GPU utilization.
4. NVIDIA Warp preprocessing cost.

The default implementation is read-only. It probes existing local services and emits a
benchmark matrix; it does not create rooms, run deliberations, warm models, launch Warp,
pull models, call remote providers, or modify OBus state.

## Important boundary

NVIDIA Warp is **not** treated as a transformer-inference accelerator. In this repository,
`backend/warp_companion.py` discovers and optionally launches a separate `warp-tui-oss`
terminal companion. There is no OBus transformer preprocessing path wired to Warp. A Warp
number is therefore valid only for the explicitly measured preprocessing fixture. It must
not be reported as an inference speedup, model throughput improvement, or end-to-end OBus
latency improvement unless a real, measured integration is later added.

## Safe entry point

From the repository root:

```text
python scripts/obus_benchmark_plan.py
```

This prints the plan only. To perform local, read-only discovery:

```text
python scripts/obus_benchmark_plan.py --probe
```

Optional output capture is explicit and writes only the requested report file:

```text
python scripts/obus_benchmark_plan.py --probe --output benchmark-probe.json
```

The probe performs only:

- `GET http://127.0.0.1:38173/health`
- `GET /api/dashboard`
- `GET /api/warmup`
- `GET /api/integrations/warp`
- Ollama `GET /api/tags` and `GET /api/ps`
- a read-only `nvidia-smi --query-gpu=...` call when available

It never calls `POST /api/warmup`, `POST /api/deliberate`, `POST /api/rooms`,
`POST /api/rooms/{id}/run`, `POST /api/forum/threads/{id}/round`, or the Warp launch
endpoint.

## Phase 0: environment record

Record this once per run:

- OBus commit, Python version, OS, CPU, RAM, and NVIDIA driver/GPU name.
- OBus base URL and Ollama URL, both loopback-only by default.
- OBus performance profile: `fast`, `balanced`, `deep`, or `throughput`.
- Ollama model name, quantization, context window, `keep_alive` policy, and whether the
  model was already resident.
- Warp version/commit, device (`cpu` or `cuda:0`), and whether the first kernel compile
  is included.
- Power/performance mode and whether other GPU workloads are active.

Do not record environment variables, credentials, authorization references, prompt
transcripts, or full response bodies.

## Phase 1: deliberation latency

### Workloads

Use fixed prompts stored in the benchmark report, not user data:

| Case | Purpose |
|---|---|
| `short-circuit` | A trivial one-step prompt; validates the direct path. |
| `council-short` | Council-worthy prompt with roughly 32-128 input words. |
| `council-medium` | Same task shape with roughly 256-512 input words. |
| `council-long` | Same task shape with roughly 1,000-2,000 input words. |

Run each against:

- collaborative mode: `draft -> improve -> synthesize`;
- adversarial mode: `draft -> triage -> attack -> verdict`;
- 2, 4, and 8 cards where the room hand permits it;
- `fast`, `balanced`, `deep`, and `throughput` local profiles when the route path is
  being measured rather than the room path.

Use at least 3 unmeasured warm-ups and 20 measured repetitions per cell for a stable
initial baseline. If the local model is expensive, begin with 5 measured repetitions
and label the result exploratory rather than production-grade.

### Timing boundaries

Capture monotonic timestamps at the client and, where possible, server event timestamps:

- request start;
- response receipt;
- `route.started`, `route.plan_ready`, `route.deliberation_started`,
  `route.deliberation_complete`, `route.local_started`, and `route.complete` events;
- room phase message timestamps (`draft`, `improve`, `triage`, `attack`, `synthesize`,
  `verdict`);
- Ollama `total_duration`, `load_duration`, `prompt_eval_duration`, and
  `eval_duration` from provider responses when available.

Report:

- end-to-end latency: p50, p90, p95, p99, min, max;
- planning, deliberation, local generation, aggregation, and persistence components;
- tokens/sec for prompt evaluation and generation when Ollama supplies counts/durations;
- response status, timeout count, and failure reason class;
- cold versus warm model residency as an explicit dimension.

Do not infer phase latency by subtracting unrelated wall-clock measurements. Parallel
seat work should be reported as wall-clock phase duration plus total provider work.

## Phase 2: room and forum concurrency

Run separate experiments because they answer different questions:

| Experiment | Expected behavior to verify |
|---|---|
| Different rooms, concurrency 1/2/4/8 | Independent room locks permit overlap; latency and errors reveal shared state or GPU contention. |
| Same room, two simultaneous runs | One request succeeds and the other returns HTTP 409 due to the room execution lock. |
| Same forum thread, two simultaneous rounds | One request succeeds and the other returns HTTP 409 due to the forum execution lock. |
| One forum with 2/4/8 rooms | Room councils are dispatched with `asyncio.gather`; measure fan-out, join, persistence, and total wall time. |
| Auto deliberation | Two generated rooms plus one forum round; compare against the sum of isolated room runs. |

For every concurrency level record offered load, completed, 409, 4xx, 5xx, timeout,
and cancelled requests. Report throughput, queue/wait time if instrumented, p50/p95
latency, and the ratio of total provider calls to completed logical tasks.

A same-room 409 is a correctness result, not a performance failure. A successful
same-room overlap would be a safety/regression failure because it would violate the
current single-flight contract.

Because state is persisted to JSON, inspect the report for persistence contention and
state corruption symptoms. Do not run this phase against a user's primary state
without an isolated `OCCULTBUS_HOME` copy and a disposable test model.

## Phase 3: Ollama GPU usage

Use read-only Ollama status before and after every latency/concurrency cell:

- `/api/tags`: installed model names and declared context length;
- `/api/ps`: running model names, runtime context length, and `size_vram`;
- `nvidia-smi`: timestamped utilization, memory used/free, power, temperature, and
  process list if permitted.

Sample `nvidia-smi` at 1 Hz or faster for short requests and align samples to request
start/end using a monotonic clock. `/api/ps` is a residency/VRAM signal; it is not a
GPU-utilization signal. `nvidia-smi` is the utilization source.

Separate these conditions:

1. cold request: model not resident at the start, with `load_duration` captured;
2. warm request: model resident before the start, with `keep_alive` recorded;
3. concurrent requests: one model and multiple OBus room/route requests;
4. context-size sweep: fixed output budget with increasing input size.

Report peak and average GPU utilization, peak VRAM, model residency, load duration,
provider duration, prompt/eval token rates, and OBus wall time. Do not use `size_vram`
as a proxy for utilization, and do not call warmup automatically from the benchmark.

## Phase 4: NVIDIA Warp preprocessing microbenchmark

This is an independent fixture, not a transformer benchmark.

The fixture should use deterministic synthetic input and compare:

- a CPU reference preprocessing implementation;
- Warp CPU preprocessing, if available;
- Warp CUDA preprocessing, if CUDA and a compatible Warp install are available.

Measure separately:

- input creation and host-to-device transfer;
- first-call/kernel compilation time;
- synchronized steady-state kernel time;
- device-to-host transfer, only if the consumer requires it;
- output checksum/equivalence.

Use at least 3 warm-ups and 50 measured iterations per size/device cell. Synchronize
CUDA before stopping the timer. Test small, medium, and large fixed batches. Report
preprocessing milliseconds and throughput for that fixture only. Never label the result
"transformer acceleration" and never compare it directly with Ollama `eval_duration`.

If a future OBus change adds a real Warp preprocessing boundary, add an explicit trace
stage and benchmark the full pipeline as:

`input -> Warp preprocessing -> serialized prompt/tensor boundary -> Ollama inference`.

Until then, keep the Warp result in a separate section and do not fold it into OBus
route latency.

## Result schema and analysis

Each measured row should contain:

```json
{
  "run_id": "...",
  "case": "council-medium",
  "mode": "collaborative",
  "cards": 4,
  "profile": "balanced",
  "concurrency": 2,
  "status": "complete",
  "http_status": 200,
  "wall_seconds": 0.0,
  "phase_seconds": {},
  "provider": {},
  "gpu_samples": {},
  "warp_preprocessing": null,
  "errors": []
}
```

Calculate distributions in code, not by visual inspection. At minimum, compare:

- warm p95 versus cold p95;
- collaborative versus adversarial phase cost;
- independent-room scaling versus same-room 409 behavior;
- model load duration versus steady-state generation duration;
- GPU peak/average versus request concurrency;
- Warp preprocessing cost versus the same fixture's CPU reference, without assigning
  any inference claim.

Do not set a universal pass/fail latency target before the first baseline. After a
baseline exists, use a versioned regression budget, for example a pre-agreed p95 delta
and error-rate budget per workload cell. Preserve raw timestamped samples and the
configuration manifest alongside the summarized report.

## Safe execution gates

A future write-capable runner should require all of the following explicit flags:

- isolated `OCCULTBUS_HOME`;
- `--allow-write-test`;
- `--no-remote-aggregate`;
- a fixed local model already installed;
- a bounded repetition/concurrency limit;
- a cleanup/archive step and a report path outside the OBus state directory.

Without those gates, run only the plan and read-only probe implemented in
`scripts/obus_benchmark_plan.py`.
