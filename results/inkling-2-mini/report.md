# Results — unsloth/Inkling-2-Mini-GGUF

- Run: 2026-11-24T06:05:10+00:00
- Machine: Apple M3 Max, 40-core GPU, 64 GB, macOS 26.6.2
- Quant: UD-Q4_K_M · context as loaded 40,448 (native 1,048,576)
- Server flags: `-m --port 53333 --parallel 4 --flash-attn on --no-context-shift -c 40448 --video-fps 1 --video-timestamp-interval 2000 --video-ffmpeg-dir --alias unsloth/Inkling-2-Mini-GGUF -ngl -1 --fit off --metrics --slot-save-path --kv-unified --fit-target 3946 --jinja --verbosity 4 --model-draft --spec-type draft-dspark --spec-draft-n-max 2 --chat-template-kwargs {"reasoning_effort": "high"} --mmproj --api-key-file --ctx-checkpoints 5`

## Accuracy

| Family | Passed | Rate |
|---|---|---|
| Tool calling | 24/24 | 100% |
| Vision | 9/9 | 100% |
| Long-context recall | 15/15 | 100% |
| Maths & reasoning | 48/48 | 100% |
| Instruction following | 29/30 | 97% |
| Python coding | 46/48 | 96% |
| Elixir coding | 20/21 | 95% |

- coding items not passing every sample: {'cron_matches': '1/3'}
- coding by difficulty: easy 21/21, medium 21/21, hard 4/6
- elixir items not passing every sample: {'flatten_keys_ex': '2/3'}
- elixir by difficulty: easy 12/12, medium 8/9
- maths misses (id, got, want): none

## Speed

| Output | Median tok/s | Range | Draft acceptance |
|---|---|---|---|
| structured | 31.9 | 30.6–32.9 | 61% |
| code | 32.3 | 32.0–34.4 | 63% |
| prose | 23.9 | 23.5–24.6 | 30% |

- decode runs that overlapped with another generation: 0

| Prompt tokens | TTFT | Server prefill tok/s |
|---|---|---|
| 532 | 1.46s | 364 |
| 1,942 | 5.04s | 385 |
| 7,695 | 24.84s | 310 |
| 15,256 | 52.86s | 289 |
| 30,469 | 129.30s | 236 |

| Concurrent | Total tok/s | Per request tok/s | Median TTFT | Max TTFT |
|---|---|---|---|---|
| 1 | 23.1 | 23.9 | 0.88s | 0.88s |
| 2 | 31.9 | 16.7 | 0.72s | 0.84s |
| 4 | 34.2 | 8.7 | 1.39s | 1.39s |
| 6 | 33.9 | 9.4 | 1.37s | 66.42s |

## Thinking share

- Maths: 82% of text is reasoning, median 304 tokens/reply
- Python coding: 86% of text is reasoning, median 969 tokens/reply
- Elixir coding: 88% of text is reasoning, median 1,054 tokens/reply

## Wall-clock per suite

- speed: 19.1 min
- needle: 18.8 min
- coding: 29.0 min
- elixir: 10.9 min
- math: 6.9 min
- instruct: 6.6 min
- tools: 1.8 min
- vision: 0.9 min
- personality: 2.4 min
