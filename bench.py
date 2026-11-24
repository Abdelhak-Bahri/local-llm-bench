#!/usr/bin/env python3
"""Benchmark a local model behind any OpenAI-compatible endpoint.

    python bench.py selftest                      # validate the suite itself (no model)
    python bench.py run --suites all              # everything
    python bench.py run --suites speed,coding     # a subset

Auth: BENCH_API_KEY env var, or --key-file PATH. Results go to --out
(default results/latest): one JSONL of full transcripts per suite, plus
summary.json. Re-running a subset of suites updates summary.json in place.

Speed suites run one request at a time and wait for the server to be idle
first. Accuracy suites run --workers requests in parallel: concurrency changes
how fast answers arrive, not what they say.
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import json
import os
import platform
import random
import statistics as st
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import tasks as T  # noqa: E402
from client import Client, load_key, strip_thinking, studio_busy, wait_idle  # noqa: E402
from sandbox import extract_block, run_elixir, run_python  # noqa: E402

OUT = os.path.join(HERE, "results", "latest")  # set from --out in main()
_print_lock = threading.Lock()


def log(*a):
    with _print_lock:
        print(time.strftime("%H:%M:%S"), *a, flush=True)


class Recorder:
    def __init__(self, suite):
        os.makedirs(os.path.join(OUT, "raw"), exist_ok=True)
        self.f = open(os.path.join(OUT, "raw", f"{suite}.jsonl"), "w")
        self.lock = threading.Lock()

    def __call__(self, **row):
        with self.lock:
            self.f.write(json.dumps(row, default=str) + "\n")
            self.f.flush()


def ask(cli, prompt, **kw):
    return cli.chat([{"role": "user", "content": prompt}], **kw)


def sampling(args):
    return {} if args.temperature is None else {"temperature": args.temperature}


def pmap(fn, items, workers):
    with cf.ThreadPoolExecutor(workers) as ex:
        return list(ex.map(fn, items))


def jobs(items, samples):
    return [(it, k) for it in items for k in range(samples)]


def spec_stats(s):
    t = s.get("server_timings") or {}
    n, acc = t.get("draft_n"), t.get("draft_n_accepted")
    return {"server_decode_tps": t.get("predicted_per_second"),
            "server_prefill_tps": t.get("prompt_per_second"),
            "server_prompt_n": t.get("prompt_n"), "cache_n": t.get("cache_n"),
            "draft_n": n, "draft_accepted": acc,
            "acceptance": (acc / n) if n else None}


# ---------------------------------------------------------------- speed ----
FILLER_WORDS = ("the camera uploads frames to storage while a worker resizes them and the "
                "scheduler retries failed jobs after a short backoff so the queue stays healthy "
                "even when the network drops packets during heavy rain on site").split()


def filler(n_words, seed):
    rnd = random.Random(seed)
    return " ".join(rnd.choice(FILLER_WORDS) for _ in range(n_words))


def timed(cli, prompt, **kw):
    """One measured request: wait for an idle server, run, note whether
    anything else started generating while we were measuring."""
    waited = wait_idle(cli, log=log)
    r = ask(cli, prompt, **kw)
    s = r.summary()
    s.update(spec_stats(s), waited_s=round(waited, 1))
    busy_after = studio_busy(cli)
    s["contended"] = bool(busy_after)  # someone else was generating as we finished
    return r, s


def suite_speed(cli, args):
    rec, out = Recorder("speed"), {"decode": [], "prefill": [], "concurrency": []}
    log("speed: warmup")
    ask(cli, "Say hi.", max_tokens=64)

    # 1. Decode throughput by output genre. The drafter (speculative decoding)
    #    is fixed on in this server; its acceptance rate is what varies.
    for genre, prompt in T.SPEED_GENRES.items():
        for i in range(args.repeats):
            r, s = timed(cli, prompt, max_tokens=1536, **sampling(args))
            row = {"genre": genre, "run": i, **s, "reasoning_chars": len(r.reasoning),
                   "content_chars": len(r.content)}
            out["decode"].append(row)
            rec(test="decode", **row, content=r.content[:3000])
            log(f"decode {genre:<10} run{i}: {(s['server_decode_tps'] or 0):5.1f} tok/s "
                f"(client {(s['decode_tps'] or 0):5.1f}), accept {(s['acceptance'] or 0):.0%}, "
                f"{s['completion_tokens']} tok{'  CONTENDED' if s['contended'] else ''}")

    # 2. Prefill vs prompt length. A random nonce up front defeats the prompt cache.
    for target in args.prefill_sizes:
        for i in range(2):
            prompt = (f"[nonce {uuid.uuid4()}]\n" + filler(int(target / 1.25), seed=target * 10 + i)
                      + "\n\nIn one word: what is this text about?")
            r, s = timed(cli, prompt, max_tokens=1, **sampling(args))
            row = {"target": target, "run": i, **s}
            out["prefill"].append(row)
            rec(test="prefill", **row)
            log(f"prefill ~{target:>6}: {s['prompt_tokens']} tok, ttft {(s['ttft_s'] or 0):6.2f}s, "
                f"server {(s['server_prefill_tps'] or 0):6.0f} tok/s, cache {s['cache_n']} {s['error'] or ''}")

    # 3. Concurrency. The server has 4 slots (--parallel 4); past that, requests queue.
    for n in args.concurrency:
        wait_idle(cli, log=log)
        prompts = [T.SPEED_GENRES["prose"] + f" (Variant {k}.)" for k in range(n)]
        t0 = time.perf_counter()
        rs = pmap(lambda p: ask(cli, p, max_tokens=600, **sampling(args)), prompts, n)
        wall = time.perf_counter() - t0
        toks = sum(r.out_tokens for r in rs)
        row = {"n": n, "wall_s": wall, "total_tokens": toks, "aggregate_tps": toks / wall,
               "per_request_tps": st.median([r.decode_tps or 0 for r in rs]),
               "median_ttft_s": st.median([r.ttft or 0 for r in rs]),
               "max_ttft_s": max(r.ttft or 0 for r in rs),
               "errors": sum(not r.ok for r in rs)}
        out["concurrency"].append(row)
        rec(test="concurrency", **row)
        log(f"concurrency {n}: aggregate {row['aggregate_tps']:.1f} tok/s, per-request "
            f"{row['per_request_tps']:.1f}, ttft med {row['median_ttft_s']:.2f}s max {row['max_ttft_s']:.2f}s")
    return out


# --------------------------------------------------------------- coding ----
def _code_suite(cli, args, name, items, lang, suffix, runner):
    rec = Recorder(name)

    def one(job):
        (tid, diff, prompt, _ref, tests), k = job
        r = ask(cli, prompt + suffix, max_tokens=args.max_tokens, **sampling(args))
        code = extract_block(strip_thinking(r.content), lang)
        passed, tail = runner(code, tests) if code else (False, "NO CODE BLOCK")
        row = {"id": tid, "difficulty": diff, "sample": k, "passed": passed,
               "reasoning_chars": len(r.reasoning), **r.summary()}
        rec(**row, prompt=prompt, content=r.content, reasoning=r.reasoning, test_log=tail)
        log(f"{name} {tid:<24} s{k} {'PASS' if passed else 'FAIL'}  {r.out_tokens} tok "
            f"{r.total:5.1f}s {r.finish_reason} {r.error or ''}")
        return row
    return pmap(one, jobs(items, args.samples), args.workers)


def suite_coding(cli, args):
    return _code_suite(cli, args, "coding_python", T.PYTHON, "python", T.CODE_SUFFIX_PY, run_python)


def suite_elixir(cli, args):
    return _code_suite(cli, args, "coding_elixir", T.ELIXIR, "elixir", T.CODE_SUFFIX_EX, run_elixir)


# ------------------------------------------------------------ reasoning ----
def suite_math(cli, args):
    rec = Recorder("math")

    def one(job):
        (tid, q, ans), k = job
        r = ask(cli, q + T.MATH_SUFFIX, max_tokens=args.max_tokens, **sampling(args))
        got = T.extract_int_answer(strip_thinking(r.content))
        row = {"id": tid, "sample": k, "expected": ans, "got": got, "passed": got == ans,
               "reasoning_chars": len(r.reasoning), **r.summary()}
        rec(**row, content=r.content, reasoning=r.reasoning)
        log(f"math {tid:<12} s{k} {'PASS' if got == ans else 'FAIL'} got={got} want={ans}")
        return row
    return pmap(one, jobs(T.MATH, args.samples), args.workers)


def suite_instruct(cli, args):
    rec = Recorder("instruct")

    def one(job):
        (tid, prompt, check), k = job
        r = ask(cli, prompt, max_tokens=args.max_tokens, **sampling(args))
        text = strip_thinking(r.content)
        try:
            ok = bool(r.ok and check(text))
        except Exception:
            ok = False
        row = {"id": tid, "sample": k, "passed": ok, **r.summary()}
        rec(**row, prompt=prompt, content=r.content)
        log(f"instruct {tid:<14} s{k} {'PASS' if ok else 'FAIL'}")
        return row
    return pmap(one, jobs(T.INSTRUCT, args.samples), args.workers)


def suite_tools(cli, args):
    rec = Recorder("tools")

    def one(job):
        (tid, prompt, check), k = job
        r = cli.chat([{"role": "user", "content": prompt}], tools=T.TOOLS, tool_choice="auto",
                     max_tokens=args.max_tokens, **sampling(args))
        try:
            ok = bool(r.ok and check(r.tool_calls))
        except Exception:
            ok = False
        row = {"id": tid, "sample": k, "passed": ok, "tool_calls": r.tool_calls, **r.summary()}
        rec(**row, content=r.content)
        log(f"tools {tid:<18} s{k} {'PASS' if ok else 'FAIL'} {r.tool_calls}")
        return row
    return pmap(one, jobs(T.TOOL_CASES, args.samples), args.workers)


# ---------------------------------------------------------- long context ---
NEEDLE = "The secret deploy code for project Falcon is QUARTZ-7-ORCHID."


def suite_needle(cli, args):
    rec, rows = Recorder("needle"), []
    for target in args.needle_sizes:
        for depth in (0.1, 0.5, 0.9):
            words = filler(int(target / 1.25), seed=target).split()
            cut = int(len(words) * depth)
            hay = " ".join(words[:cut]) + "\n" + NEEDLE + "\n" + " ".join(words[cut:])
            prompt = (f"[nonce {uuid.uuid4()}]\n{hay}\n\nWhat is the secret deploy code for "
                      "project Falcon? Reply with the code only.")
            r, s = timed(cli, prompt, max_tokens=2048, **sampling(args))
            ok = "QUARTZ-7-ORCHID" in strip_thinking(r.content).upper()
            row = {"target": target, "depth": depth, "passed": ok, **s}
            rows.append(row)
            rec(**row, answer=r.content[:300])
            log(f"needle ~{target:>6} @{depth:.0%}: {'PASS' if ok else 'FAIL'} "
                f"({r.prompt_tokens} tok, ttft {(r.ttft or 0):.1f}s) {r.error or ''}")
    return rows


# --------------------------------------------------------------- vision ----
VISION = [
    ("read_text", "receipt.png", "What is the TOTAL amount on this receipt? Reply with the number only.", "47.80"),
    ("count_shapes", "shapes.png", "How many red circles are in this image? Reply with a single integer.", "7"),
    ("read_chart", "bars.png", "Which bar is the tallest, and what is its value? Reply as 'LABEL VALUE'.", "THU 92"),
]


def suite_vision(cli, args):
    rec = Recorder("vision")
    items = []
    for tid, fname, q, want in VISION:
        path = os.path.join(HERE, "vision", fname)
        if not os.path.exists(path):
            raise SystemExit(f"missing {path}; run `python vision.py` first")
        items.append((tid, base64.b64encode(open(path, "rb").read()).decode(), q, want))

    def one(job):
        (tid, b64, q, want), k = job
        msgs = [{"role": "user", "content": [
            {"type": "text", "text": q},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}]
        r = cli.chat(msgs, max_tokens=args.max_tokens, **sampling(args))
        text = strip_thinking(r.content).upper().replace(",", ".")
        ok = all(tok in text for tok in want.upper().split())
        row = {"id": tid, "sample": k, "passed": ok, **r.summary()}
        rec(**row, answer=r.content[:500])
        log(f"vision {tid:<14} s{k} {'PASS' if ok else 'FAIL'}  {r.content[:60]!r} {r.error or ''}")
        return row
    return pmap(one, jobs(items, args.samples), args.workers)


# ---------------------------------------------------------- personality ----
def suite_personality(cli, args):
    rec = Recorder("personality")

    def one(item):
        tid, prompt = item
        r = ask(cli, prompt, max_tokens=args.max_tokens)  # Studio's default sampling, always
        rec(id=tid, prompt=prompt, content=r.content, reasoning=r.reasoning, **r.summary())
        log(f"personality {tid}: {len(r.content)} chars")
        return tid, prompt, strip_thinking(r.content), r.summary()

    res = pmap(one, T.PERSONALITY, args.workers)
    md = ["# Personality samples\n", "Unscored. Verbatim, Studio's default sampling, first take.\n"]
    for tid, prompt, text, _ in res:
        md += [f"\n## {tid}\n", "> " + prompt.replace("\n", "\n> ") + "\n", text, ""]
    with open(os.path.join(OUT, "personality.md"), "w") as f:
        f.write("\n".join(md))
    return [{"id": tid, **s} for tid, _, _, s in res]


SUITES = {"speed": suite_speed, "coding": suite_coding, "elixir": suite_elixir,
          "math": suite_math, "instruct": suite_instruct, "tools": suite_tools,
          "needle": suite_needle, "vision": suite_vision, "personality": suite_personality}


# -------------------------------------------------------------- selftest ---
def selftest():
    bad = 0
    for tid, _, _, ref, tests in T.PYTHON:
        ok, out = run_python(ref, tests)
        print(f"python {tid:<24} {'ok' if ok else 'BROKEN'}")
        if not ok:
            bad += 1; print(out)
    for tid, _, _, ref, tests in T.ELIXIR:
        ok, out = run_elixir(ref, tests)
        print(f"elixir {tid:<24} {'ok' if ok else 'BROKEN'}")
        if not ok:
            bad += 1; print(out)
    # A known-wrong solution must fail, or the runner is rubber-stamping.
    assert not run_python("def int_to_roman(n): return 'X'", T.PYTHON[3][4])[0], "python runner passes wrong code"
    assert not run_elixir("defmodule Bench do\n def rle_encode(_), do: \"\"\nend", T.ELIXIR[1][4])[0], "elixir runner passes wrong code"
    # Brute-force the computable maths answers.
    checks = {
        "multiples": sum(i for i in range(100) if i % 3 == 0 or i % 5 == 0),
        "modpow": pow(2, 100, 7),
        "sevens": sum("7" in str(i) for i in range(1, 1001)),
        "timelapse": len(range(7 * 60, 18 * 60 + 1, 10)),
        "lcm": next(i for i in range(1, 1000) if all(i % d == 0 for d in (12, 18, 30))),
        "choose": 10 * 9 * 8 // 6,
        "bitrate": int(5e6 * 86400 / 8 / 1e9),
    }
    for tid, _, ans in T.MATH:
        if tid in checks and checks[tid] != ans:
            bad += 1; print(f"math {tid}: key says {ans}, brute force says {checks[tid]}")
    # Instruction checkers against hand-made good/bad answers.
    ins = {i: c for i, _, c in T.INSTRUCT}
    probes = [("twelve_words", "one two three four five six seven eight nine ten eleven twelve", True),
              ("twelve_words", "one two three", False),
              ("json_only", '{"name":"Erlang","year":1986,"tags":["a","b","c"]}', True),
              ("json_only", '```json\n{"name":"Erlang","year":1986,"tags":["a","b","c"]}\n```', False),
              ("three_bullets", "- a\n- b\n- c", True), ("three_bullets", "- a\n- b", False),
              ("answer_tags", "<answer>Canberra</answer>", True), ("answer_tags", "Sure! <answer>Canberra</answer>", False),
              ("md_table", "| Language | Paradigm |\n|---|---|\n| A | x |\n| B | y |\n| C | z |", True),
              ("no_commas", "It spreads load. It checks health. It removes dead nodes.", True)]
    for tid, text, want in probes:
        if bool(ins[tid](text)) != want:
            bad += 1; print(f"instruct checker {tid} wrong on {text!r}")
    # Tool checkers against hand-made calls.
    tc = {i: c for i, _, c in T.TOOL_CASES}
    call = lambda n, a: {"name": n, "arguments": json.dumps(a)}  # noqa: E731
    tprobes = [("calc_pct", [call("calculator", {"expression": "0.15*240"})], True),
               ("calc_pct", [call("calculator", {"expression": "15% * 240"})], True),
               ("parallel_weather", [call("get_weather", {"city": "Tokyo"}), call("get_weather", {"city": "Oran"})], True),
               ("parallel_weather", [call("get_weather", {"city": "Tokyo"})], False),
               ("calendar", [call("create_calendar_event", {"title": "Design review", "start": "2026-12-01T15:00:00", "duration_minutes": 45})], True),
               ("no_tool_joke", [], True)]
    for tid, calls, want in tprobes:
        if bool(tc[tid](calls)) != want:
            bad += 1; print(f"tool checker {tid} wrong on {calls}")
    print("SELFTEST", "PASSED" if not bad else f"FAILED ({bad})")
    return bad == 0


# ------------------------------------------------------------------ main ---
def environment(cli):
    def sh(c):
        try:
            return subprocess.run(c, shell=True, capture_output=True, text=True).stdout.strip()
        except Exception:
            return None
    try:
        meta = next((m for m in json.load(__import__("urllib.request").request.urlopen(
            cli._req("/models"), timeout=10))["data"] if m["id"] == cli.model), {})
    except Exception:
        meta = {}
    return {
        "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": cli.model, "base_url": cli.base,
        "quant": meta.get("quant"), "context_length": meta.get("context_length"),
        "native_context_length": meta.get("native_context_length"),
        "chip": sh("sysctl -n machdep.cpu.brand_string"),
        "ram_gb": round(int(sh("sysctl -n hw.memsize") or 0) / 2**30),
        "gpu_cores": sh("system_profiler SPDisplaysDataType | awk -F': ' '/Total Number of Cores/{print $2; exit}'"),
        "os": f"macOS {platform.mac_ver()[0]}",
        # Flags only; paths and the key file are dropped so nothing local leaks into the repo.
        "server_flags": sh("ps -o command= -ax | grep '[l]lama-server' | grep -v embedding | head -1 "
                           "| tr ' ' '\\n' | grep -vE '^/|\\.gguf$|api_key' | paste -sd' ' -"),
    }


def main():
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "selftest"])
    ap.add_argument("--base-url", default="http://127.0.0.1:8888/v1")
    ap.add_argument("--key-file")
    ap.add_argument("--out", default=OUT, help="results directory")
    ap.add_argument("--model", default="unsloth/inkling")
    ap.add_argument("--suites", default="all")
    ap.add_argument("--samples", type=int, default=3, help="samples per accuracy item")
    ap.add_argument("--repeats", type=int, default=3, help="runs per speed measurement")
    ap.add_argument("--workers", type=int, default=4, help="parallel requests for accuracy suites")
    ap.add_argument("--temperature", type=float, default=None,
                    help="omit to use the server's recommended default")
    ap.add_argument("--max-tokens", type=int, default=12000)
    ints = lambda s: [int(x) for x in s.split(",")]  # noqa: E731
    ap.add_argument("--prefill-sizes", type=ints, default=[512, 2048, 8192, 16384, 32768])
    ap.add_argument("--needle-sizes", type=ints, default=[2000, 8000, 16000, 24000, 34000])
    ap.add_argument("--concurrency", type=ints, default=[1, 2, 4, 6])
    args = ap.parse_args()

    if args.cmd == "selftest":
        sys.exit(0 if selftest() else 1)

    OUT = os.path.abspath(args.out)
    cli = Client(args.base_url, load_key(args.key_file))
    log("model:", cli.pick_model(args.model))
    names = list(SUITES) if args.suites == "all" else args.suites.split(",")

    summary_path = os.path.join(OUT, "summary.json")
    os.makedirs(OUT, exist_ok=True)
    summary = json.load(open(summary_path)) if os.path.exists(summary_path) else {}
    summary["environment"] = environment(cli)
    summary.setdefault("settings", {})
    for n in names:
        log(f"=== {n} ===")
        t0 = time.perf_counter()
        summary[n] = SUITES[n](cli, args)
        summary.setdefault("suite_seconds", {})[n] = round(time.perf_counter() - t0, 1)
        summary["settings"][n] = {k: v for k, v in vars(args).items() if k not in ("key_file", "cmd", "out")}
        json.dump(summary, open(summary_path, "w"), indent=2, default=str)
    log("done →", summary_path)


if __name__ == "__main__":
    main()
