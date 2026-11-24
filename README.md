# local-llm-bench

A small, machine-checked benchmark for LLMs you run yourself: coding (Python and
Elixir), maths, instruction following, tool calling, long-context recall,
vision, and speed. It works with anything that speaks the OpenAI chat API, such
as Unsloth Studio, llama.cpp, LM Studio, Ollama or vLLM.

**It's not a leaderboard.** 60 questions won't rank frontier models to the
decimal point. It's a filter: in about an hour and a half, it tells you whether
a new local model is genuinely capable on your hardware, or just average
dressed up by a model card. It also measures the costs a model card never
mentions: how long it takes to read a long prompt, how much of its output is
hidden reasoning, and what happens when several requests arrive at once.

![Pass rate by task family for Inkling-2-Mini](results/inkling-2-mini/charts/accuracy.svg)

## Quick start

Requirements: Python 3.10+ (standard library only), Docker (sandbox for
generated code), and optionally Google Chrome (PNG/JPG chart export).

```bash
python bench.py selftest                         # proves the suite is sound; no model needed

export BENCH_API_KEY=...                         # if your server needs one (or --key-file PATH)
python bench.py run \
  --base-url http://127.0.0.1:8080/v1 \
  --model qwen \
  --out results/my-model                         # all suites, ~1.5–2 h

python bench.py run --suites speed,tools --out results/my-model    # or a subset
python charts.py --results results/my-model      # charts + report.md
```

`--model` is a substring of the model ID the server lists. Other useful flags:
`--samples` (default 3 per question), `--workers` (parallel accuracy requests,
default 4), `--temperature` (omit to use the server's default),
`--max-tokens`, `--prefill-sizes`, `--needle-sizes`, `--concurrency`. Size the
long-context lists to fit the context your server actually loaded.

## What it measures

| Suite | Items | Scoring |
| --- | --- | --- |
| `speed` | 3 output types × 3 runs; 5 prompt lengths × 2; 1/2/4/6 concurrent requests | Server-reported timings (llama.cpp `timings`), client-side cross-check |
| `coding` | 16 Python functions, from easy to a cron parser | Unit tests in a sandbox |
| `elixir` | 7 Elixir modules, including a GenServer | ExUnit in a sandbox |
| `math` | 16 word problems, including classic traps | Exact integer match |
| `instruct` | 10 format constraints: word counts, JSON only, no commas… | Programmatic checkers |
| `tools` | 8 cases, including parallel calls and two where no tool should be called | Function name and argument validation |
| `needle` | 5 context sizes × 3 depths | Exact recall of a hidden code |
| `vision` | Receipt OCR, counting shapes, reading a bar chart | Exact answer match |
| `personality` | 6 open prompts | Not scored; written to `personality.md` |

## Design rules

- **Every problem is new**, written for this benchmark, so none can be
  memorised from a training set word for word.
- **The tests are tested.** `selftest` runs every coding test against a
  reference solution, checks that a deliberately wrong solution fails in both
  languages, brute-forces the maths answer key, and probes every
  instruction-following and tool-calling checker with known-good and known-bad
  answers. A failing score is never the test's fault.
- **Model-written code never runs on your machine.** Each test runs in a fresh
  container with `--network none`, 512 MB of memory, 1 CPU, a read-only root
  filesystem, a process limit, and a hard timeout (`sandbox.py`).
- **Speed is measured on an idle server.** On Unsloth Studio, the harness
  polls for active generations and waits until nothing else is running before
  each timed request. Any measurement that overlapped another generation is
  flagged with `contended: true`.
- **No cache hits.** Every long prompt starts with a random string, so the
  server can't reuse earlier work and flatter the numbers.
- **Accuracy uses default sampling and 3 samples per question**, running 4 at
  a time. Running in parallel changes how fast answers arrive, not what they
  say.

## Results so far

| Model | Machine | Python | Elixir | Maths | Instructions | Tools | Vision | Needle | Prose tok/s | 30K prompt read |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [Inkling-2-Mini](results/inkling-2-mini/report.md) `UD-Q4_K_M` | M3 Max, 64 GB | 46/48 | 20/21 | 48/48 | 29/30 | 24/24 | 9/9 | 15/15 | 23.9 | 129 s |

Each results folder has `summary.json` (every row, plus the environment and
server flags), `raw/*.jsonl` (full transcripts, including reasoning, code and
test output), `report.md` and `charts/`.

The full write-up of the Inkling-2-Mini run is on
[abdelhakbahri.com](https://abdelhakbahri.com/blog/benchmarking-inkling-2-mini-locally).

<p>
  <img src="results/inkling-2-mini/charts/decode.svg" alt="Generation speed by output type" width="49%">
  <img src="results/inkling-2-mini/charts/thinking.svg" alt="Share of output spent thinking" width="49%">
</p>

## Notes on Unsloth Studio

These came up while building the harness against Studio's API, and they apply
to any always-reasoning model served there:

- Studio launches models with `--chat-template-kwargs {"reasoning_effort": "high"}`.
  `enable_thinking: false`, `chat_template_kwargs` and
  `thinking: {type: disabled}` all still produce reasoning, and
  `reasoning_effort: "none"` makes the reasoning leak into `content`.
- Speculative decoding can't be turned off per request; `speculative.n_max: 0`
  is ignored. The harness reports the draft acceptance rate
  (`draft_n_accepted / draft_n`) instead.
- Studio may load far less context than the model supports (40,448 of
  1,048,576 tokens on 64 GB). `/v1/models` reports `context_length`.

## Limitations

60 questions is a probe. Inkling-2-Mini already scores 95–100% on most
families, so the next version needs harder problems to tell strong models
apart. Function-level coding isn't agentic coding. And every number comes from
one machine, one quantisation and one runtime.

## How this was made

The benchmark was designed, written and run by Claude (Anthropic), working as
Claude Code at Abdelhak Bahri's request, with the results reviewed by him. The
article linked above describes how that went, including the mistakes Claude
caught in its own harness.

## License

MIT
