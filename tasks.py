"""Task definitions. Every problem here was written for this benchmark, so none
of it can be in a training set verbatim. Every coding task carries a reference
solution; `python bench.py selftest` runs the tests against the references
before any model is scored, so a failing test is never the test's fault.
"""
import json
import re

CODE_SUFFIX_PY = (
    "\n\nReturn exactly one ```python code block with the complete implementation. "
    "No tests, no example usage, nothing that runs at import time."
)
CODE_SUFFIX_EX = (
    "\n\nReturn exactly one ```elixir code block with the complete module(s). "
    "No tests, no example usage, nothing that runs at load time."
)

# --------------------------------------------------------------------------
# Python coding: (id, difficulty, prompt, reference, tests)
# --------------------------------------------------------------------------
PYTHON = [
    ("parse_duration", "easy",
     "Write `parse_duration(s: str) -> int` that converts strings like '1h30m15s', '45s', '2h', "
     "'10m5s' into total seconds. Units h, m, s appear at most once each, in that order. "
     "Raise ValueError for empty strings or anything else malformed (e.g. '5x', 'h', '1s1h').",
     '''
import re
def parse_duration(s):
    m = re.fullmatch(r"(?:(\\d+)h)?(?:(\\d+)m)?(?:(\\d+)s)?", s or "")
    if not s or not m or not any(m.groups()):
        raise ValueError(s)
    h, mi, se = (int(g) if g else 0 for g in m.groups())
    return h * 3600 + mi * 60 + se
''',
     '''
assert parse_duration("1h30m15s") == 5415
assert parse_duration("45s") == 45
assert parse_duration("2h") == 7200
assert parse_duration("10m5s") == 605
for bad in ["", "5x", "h", "1s1h"]:
    try:
        parse_duration(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(f"no ValueError for {bad!r}")
'''),

    ("merge_intervals", "easy",
     "Write `merge_intervals(intervals: list[list[int]]) -> list[list[int]]` that merges overlapping "
     "intervals and returns them sorted by start. Intervals that touch (e.g. [1,2] and [2,3]) merge. "
     "Input may be unsorted.",
     '''
def merge_intervals(intervals):
    out = []
    for s, e in sorted(intervals):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out
''',
     '''
assert merge_intervals([[1,3],[2,6],[8,10],[15,18]]) == [[1,6],[8,10],[15,18]]
assert merge_intervals([[1,4],[4,5]]) == [[1,5]]
assert merge_intervals([]) == []
assert merge_intervals([[5,7],[1,2]]) == [[1,2],[5,7]]
assert merge_intervals([[1,10],[2,3]]) == [[1,10]]
'''),

    ("lru_cache", "medium",
     "Implement a class `LRUCache` with `__init__(self, capacity: int)`, `get(self, key) -> value` "
     "(return -1 if absent) and `put(self, key, value)`. Both operations O(1). When over capacity, "
     "evict the least recently used key. `get` and `put` both count as a use.",
     '''
from collections import OrderedDict
class LRUCache:
    def __init__(self, capacity):
        self.c, self.d = capacity, OrderedDict()
    def get(self, k):
        if k not in self.d: return -1
        self.d.move_to_end(k); return self.d[k]
    def put(self, k, v):
        self.d[k] = v; self.d.move_to_end(k)
        if len(self.d) > self.c: self.d.popitem(last=False)
''',
     '''
c = LRUCache(2)
c.put(1, 1); c.put(2, 2)
assert c.get(1) == 1
c.put(3, 3)
assert c.get(2) == -1
c.put(4, 4)
assert c.get(1) == -1
assert c.get(3) == 3 and c.get(4) == 4
c = LRUCache(1); c.put(1, 1); c.put(1, 2)
assert c.get(1) == 2
'''),

    ("int_to_roman", "easy",
     "Write `int_to_roman(n: int) -> str` for 1 <= n <= 3999 using standard subtractive notation.",
     '''
def int_to_roman(n):
    out = ""
    for v, s in [(1000,"M"),(900,"CM"),(500,"D"),(400,"CD"),(100,"C"),(90,"XC"),
                 (50,"L"),(40,"XL"),(10,"X"),(9,"IX"),(5,"V"),(4,"IV"),(1,"I")]:
        while n >= v: out += s; n -= v
    return out
''',
     '''
assert int_to_roman(1994) == "MCMXCIV"
assert int_to_roman(3999) == "MMMCMXCIX"
assert int_to_roman(4) == "IV"
assert int_to_roman(58) == "LVIII"
assert int_to_roman(1) == "I"
'''),

    ("top_k_frequent", "medium",
     "Write `top_k_frequent(words: list[str], k: int) -> list[str]` returning the k most frequent "
     "words, ordered by frequency descending, ties broken alphabetically ascending.",
     '''
from collections import Counter
def top_k_frequent(words, k):
    return [w for w, _ in sorted(Counter(words).items(), key=lambda x: (-x[1], x[0]))[:k]]
''',
     '''
assert top_k_frequent(["i","love","leetcode","i","love","coding"], 2) == ["i","love"]
assert top_k_frequent(["the","day","is","sunny","the","the","the","sunny","is","is"], 4) == ["the","is","sunny","day"]
assert top_k_frequent(["b","a","c"], 2) == ["a","b"]
'''),

    ("is_balanced", "easy",
     "Write `is_balanced(s: str) -> bool` that checks whether the brackets (), [] and {} in s are "
     "balanced and properly nested. Ignore every other character.",
     '''
def is_balanced(s):
    st, pairs = [], {")":"(", "]":"[", "}":"{"}
    for ch in s:
        if ch in "([{": st.append(ch)
        elif ch in pairs:
            if not st or st.pop() != pairs[ch]: return False
    return not st
''',
     '''
assert is_balanced("([]{})") is True
assert is_balanced("([)]") is False
assert is_balanced("((") is False
assert is_balanced("a(b)c") is True
assert is_balanced("") is True
assert is_balanced("}") is False
'''),

    ("flatten_dict", "easy",
     "Write `flatten_dict(d: dict, sep: str = '.') -> dict` that flattens nested dicts into a single "
     "level, joining keys with sep. Non-dict values are leaves. Empty nested dicts disappear.",
     '''
def flatten_dict(d, sep=".", _p=""):
    out = {}
    for k, v in d.items():
        key = f"{_p}{sep}{k}" if _p else str(k)
        if isinstance(v, dict): out.update(flatten_dict(v, sep, key))
        else: out[key] = v
    return out
''',
     '''
assert flatten_dict({"a":{"b":1,"c":{"d":2}},"e":3}) == {"a.b":1,"a.c.d":2,"e":3}
assert flatten_dict({"a":{}}) == {}
assert flatten_dict({"x":{"y":[1,2]}}, sep="/") == {"x/y":[1,2]}
'''),

    ("sliding_window_limiter", "hard",
     "Implement `SlidingWindowLimiter(limit: int, window: float)` with a method `allow(t: float) -> bool`. "
     "Calls arrive with non-decreasing t. A call at time t is allowed if strictly fewer than `limit` "
     "previously ALLOWED calls have timestamps in the half-open interval (t - window, t]. Rejected "
     "calls are not recorded.",
     '''
from collections import deque
class SlidingWindowLimiter:
    def __init__(self, limit, window):
        self.l, self.w, self.q = limit, window, deque()
    def allow(self, t):
        while self.q and self.q[0] <= t - self.w: self.q.popleft()
        if len(self.q) < self.l:
            self.q.append(t); return True
        return False
''',
     '''
l = SlidingWindowLimiter(2, 10)
assert [l.allow(t) for t in [0, 1, 2, 10, 10.5, 11]] == [True, True, False, True, False, True]
l = SlidingWindowLimiter(1, 5)
assert [l.allow(t) for t in [0, 4.9, 5, 5]] == [True, False, True, False]
'''),

    ("compare_versions", "easy",
     "Write `compare_versions(a: str, b: str) -> int` comparing dotted version strings numerically "
     "part by part ('1.2.10' > '1.2.9'). Missing parts count as 0 and leading zeros are ignored. "
     "Return -1, 0 or 1.",
     '''
def compare_versions(a, b):
    x, y = [int(p) for p in a.split(".")], [int(p) for p in b.split(".")]
    n = max(len(x), len(y)); x += [0]*(n-len(x)); y += [0]*(n-len(y))
    return (x > y) - (x < y)
''',
     '''
assert compare_versions("1.2.10", "1.10") == -1
assert compare_versions("1.0", "1.0.0") == 0
assert compare_versions("2.1", "2.0.9") == 1
assert compare_versions("1.01", "1.1") == 0
assert compare_versions("1.2.10", "1.2.9") == 1
'''),

    ("group_runs", "medium",
     "Write `group_runs(timestamps: list[int], gap: int) -> list[tuple[int, int]]`. Sort the input, "
     "then group values into runs where each consecutive difference is <= gap. Return (start, end) "
     "tuples per run, in order.",
     '''
def group_runs(ts, gap):
    out = []
    for t in sorted(ts):
        if out and t - out[-1][1] <= gap: out[-1] = (out[-1][0], t)
        else: out.append((t, t))
    return out
''',
     '''
assert group_runs([1,2,3,10,11,20], 2) == [(1,3),(10,11),(20,20)]
assert group_runs([], 2) == []
assert group_runs([5,1,3], 2) == [(1,5)]
assert group_runs([0,3], 2) == [(0,0),(3,3)]
'''),

    ("topo_sort", "medium",
     "Write `topo_sort(deps: dict[str, list[str]]) -> list[str]`. deps maps each node to the nodes it "
     "depends on. Return all nodes (including ones that only appear as dependencies) ordered so every "
     "dependency comes before the node that needs it. Raise ValueError if there is a cycle.",
     '''
def topo_sort(deps):
    nodes = set(deps) | {d for v in deps.values() for d in v}
    out, state = [], {}
    def visit(n):
        if state.get(n) == 1: raise ValueError("cycle")
        if state.get(n) == 2: return
        state[n] = 1
        for d in deps.get(n, []): visit(d)
        state[n] = 2; out.append(n)
    for n in sorted(nodes): visit(n)
    return out
''',
     '''
def _valid(deps, order):
    pos = {n: i for i, n in enumerate(order)}
    nodes = set(deps) | {d for v in deps.values() for d in v}
    assert set(order) == nodes and len(order) == len(nodes)
    for n, ds in deps.items():
        for d in ds: assert pos[d] < pos[n], (d, n)
g = {"app": ["db", "cache"], "db": ["net"], "cache": ["net"], "net": []}
_valid(g, topo_sort(g))
g2 = {"a": ["b"], "c": ["d"]}
_valid(g2, topo_sort(g2))
try:
    topo_sort({"a": ["b"], "b": ["c"], "c": ["a"]})
except ValueError:
    pass
else:
    raise AssertionError("cycle not detected")
'''),

    ("rle", "easy",
     "Write `rle_encode(s: str) -> str` and `rle_decode(s: str) -> str` for run-length encoding where "
     "each run is written as count followed by the character, e.g. 'aaabccdddd' <-> '3a1b2c4d'. "
     "Counts may exceed 9. Input characters are never digits.",
     '''
import re
from itertools import groupby
def rle_encode(s):
    return "".join(f"{len(list(g))}{c}" for c, g in groupby(s))
def rle_decode(s):
    return "".join(c * int(n) for n, c in re.findall(r"(\\d+)(\\D)", s))
''',
     '''
assert rle_encode("aaabccdddd") == "3a1b2c4d"
assert rle_decode("3a1b2c4d") == "aaabccdddd"
assert rle_encode("") == "" and rle_decode("") == ""
assert rle_decode("12a1b") == "a" * 12 + "b"
assert rle_encode("x" * 15) == "15x"
'''),

    ("fix_binary_search", "medium",
     "This function has bugs. Fix it, keeping the same name and signature:\n\n"
     "```python\n"
     "def find_first(nums, target):\n"
     "    \"\"\"Return the index of the first occurrence of target in sorted nums, or -1.\"\"\"\n"
     "    lo, hi = 0, len(nums)\n"
     "    while lo < hi:\n"
     "        mid = (lo + hi) // 2\n"
     "        if nums[mid] < target:\n"
     "            lo = mid\n"
     "        else:\n"
     "            hi = mid\n"
     "    return lo if nums[lo] == target else -1\n"
     "```",
     '''
def find_first(nums, target):
    lo, hi = 0, len(nums)
    while lo < hi:
        mid = (lo + hi) // 2
        if nums[mid] < target: lo = mid + 1
        else: hi = mid
    return lo if lo < len(nums) and nums[lo] == target else -1
''',
     '''
assert find_first([1,2,2,2,3], 2) == 1
assert find_first([], 1) == -1
assert find_first([1,3], 2) == -1
assert find_first([1,1,1], 1) == 0
assert find_first([1,2,3], 4) == -1
assert find_first([1,2,3], 3) == 2
'''),

    ("spiral_order", "medium",
     "Write `spiral_order(matrix: list[list[int]]) -> list[int]` returning elements in clockwise "
     "spiral order starting top-left. The matrix may be empty or non-square.",
     '''
def spiral_order(m):
    out = []
    while m:
        out += m.pop(0)
        m = [list(r) for r in zip(*m)][::-1]
    return out
''',
     '''
assert spiral_order([[1,2,3],[4,5,6],[7,8,9]]) == [1,2,3,6,9,8,7,4,5]
assert spiral_order([[1,2,3,4],[5,6,7,8],[9,10,11,12]]) == [1,2,3,4,8,12,11,10,9,5,6,7]
assert spiral_order([]) == []
assert spiral_order([[1],[2],[3]]) == [1,2,3]
'''),

    ("cron_matches", "hard",
     "Write `cron_matches(expr: str, dt: datetime.datetime) -> bool` for 5-field cron expressions "
     "(minute hour day-of-month month day-of-week). Each field supports `*`, a number, ranges `a-b`, "
     "comma lists, and steps `*/n` and `a-b/n`. Day-of-week is 0-6 with 0 = Sunday. All five fields "
     "must match (plain AND; ignore the classic day-of-month/day-of-week OR rule).",
     '''
import datetime
def _field(spec, value, lo, hi):
    for part in spec.split(","):
        rng, _, step = part.partition("/")
        step = int(step) if step else 1
        if rng == "*": a, b = lo, hi
        elif "-" in rng: a, b = map(int, rng.split("-"))
        else: a = b = int(rng)
        if a <= value <= b and (value - a) % step == 0: return True
    return False
def cron_matches(expr, dt):
    mi, h, dom, mon, dow = expr.split()
    return (_field(mi, dt.minute, 0, 59) and _field(h, dt.hour, 0, 23)
            and _field(dom, dt.day, 1, 31) and _field(mon, dt.month, 1, 12)
            and _field(dow, (dt.weekday() + 1) % 7, 0, 6))
''',
     '''
from datetime import datetime as D
assert cron_matches("*/15 * * * *", D(2026,11,24,10,30)) is True
assert cron_matches("*/15 * * * *", D(2026,11,24,10,31)) is False
assert cron_matches("0 9-17 * * 1-5", D(2026,11,24,9,0)) is True    # Tuesday
assert cron_matches("0 9-17 * * 1-5", D(2026,11,29,9,0)) is False   # Sunday
assert cron_matches("0 9-17 * * 1-5", D(2026,11,24,18,0)) is False
assert cron_matches("30 8 1,15 * *", D(2026,12,15,8,30)) is True
assert cron_matches("0 0 * * 0", D(2026,11,29,0,0)) is True         # Sunday = 0
assert cron_matches("0 10-20/5 * * *", D(2026,1,1,15,0)) is True
assert cron_matches("0 10-20/5 * * *", D(2026,1,1,16,0)) is False
assert cron_matches("* * * 2 *", D(2026,3,1,0,0)) is False
'''),

    ("json_path_get", "medium",
     "Write `json_path_get(obj, path: str, default=None)` that walks nested dicts/lists using paths "
     "like 'a.b[2].c' or 'items[0]' or 'a[1][0]'. Return default if any step is missing or an index "
     "is out of range. An empty path returns obj itself.",
     '''
import re
def json_path_get(obj, path, default=None):
    if path == "": return obj
    cur = obj
    for name, idx in re.findall(r"([^.\\[\\]]+)|\\[(\\d+)\\]", path):
        try:
            cur = cur[int(idx)] if idx else cur[name]
        except (KeyError, IndexError, TypeError):
            return default
    return cur
''',
     '''
doc = {"a": {"b": [0, 1, {"c": "hit"}]}, "items": ["x"], "m": [[1, 2], [3]]}
assert json_path_get(doc, "a.b[2].c") == "hit"
assert json_path_get(doc, "items[0]") == "x"
assert json_path_get(doc, "m[1][0]") == 3
assert json_path_get(doc, "a.b[10]", "dflt") == "dflt"
assert json_path_get(doc, "nope.x") is None
assert json_path_get(doc, "") is doc
'''),
]

# --------------------------------------------------------------------------
# Elixir coding: (id, difficulty, prompt, reference, tests). Tests are ExUnit
# bodies; the runner wraps them.
# --------------------------------------------------------------------------
ELIXIR = [
    ("word_freq", "easy",
     "Write an Elixir module `Bench` with `word_freq(text)` returning a map of lowercase word => count. "
     "Words are maximal runs of ASCII letters; everything else separates words.",
     '''
defmodule Bench do
  def word_freq(text) do
    ~r/[a-z]+/ |> Regex.scan(String.downcase(text)) |> List.flatten() |> Enum.frequencies()
  end
end
''',
     '''
assert Bench.word_freq("The cat and the hat.") == %{"the" => 2, "cat" => 1, "and" => 1, "hat" => 1}
assert Bench.word_freq("") == %{}
assert Bench.word_freq("It's 2 o'clock!") == %{"it" => 1, "s" => 1, "o" => 1, "clock" => 1}
'''),

    ("rle_encode_ex", "easy",
     "Write an Elixir module `Bench` with `rle_encode(string)` producing run-length encoding as "
     "count followed by character, e.g. \"aaabccdddd\" -> \"3a1b2c4d\". Counts may exceed 9.",
     '''
defmodule Bench do
  def rle_encode(s) do
    s |> String.graphemes() |> Enum.chunk_by(& &1)
    |> Enum.map_join(fn [c | _] = g -> "#{length(g)}#{c}" end)
  end
end
''',
     '''
assert Bench.rle_encode("aaabccdddd") == "3a1b2c4d"
assert Bench.rle_encode("") == ""
assert Bench.rle_encode(String.duplicate("z", 12)) == "12z"
'''),

    ("group_runs_ex", "medium",
     "Write an Elixir module `Bench` with `group_runs(list, gap)`: sort the integers, group them into "
     "runs where each consecutive difference is <= gap, and return a list of `{start, end}` tuples.",
     '''
defmodule Bench do
  def group_runs(list, gap) do
    list |> Enum.sort() |> Enum.reduce([], fn
      x, [{s, e} | rest] when x - e <= gap -> [{s, x} | rest]
      x, acc -> [{x, x} | acc]
    end) |> Enum.reverse()
  end
end
''',
     '''
assert Bench.group_runs([1, 2, 3, 10, 11, 20], 2) == [{1, 3}, {10, 11}, {20, 20}]
assert Bench.group_runs([], 2) == []
assert Bench.group_runs([5, 1, 3], 2) == [{1, 5}]
'''),

    ("balanced_ex", "easy",
     "Write an Elixir module `Bench` with `balanced?(string)` returning true if (), [] and {} are "
     "balanced and properly nested. Ignore other characters.",
     '''
defmodule Bench do
  @pairs %{")" => "(", "]" => "[", "}" => "{"}
  def balanced?(s), do: walk(String.graphemes(s), [])
  defp walk([], st), do: st == []
  defp walk([c | t], st) when c in ["(", "[", "{"], do: walk(t, [c | st])
  defp walk([c | t], st) when c in [")", "]", "}"] do
    case st do
      [top | rest] -> if top == @pairs[c], do: walk(t, rest), else: false
      [] -> false
    end
  end
  defp walk([_ | t], st), do: walk(t, st)
end
''',
     '''
assert Bench.balanced?("([]{})")
refute Bench.balanced?("([)]")
refute Bench.balanced?("((")
assert Bench.balanced?("a(b)c")
assert Bench.balanced?("")
'''),

    ("flatten_keys_ex", "medium",
     "Write an Elixir module `Bench` with `flatten_keys(map)` that flattens nested maps with string "
     "keys into one level, joining keys with \".\". Empty nested maps disappear.",
     '''
defmodule Bench do
  def flatten_keys(map, prefix \\\\ nil) do
    Enum.reduce(map, %{}, fn {k, v}, acc ->
      key = if prefix, do: "#{prefix}.#{k}", else: k
      if is_map(v), do: Map.merge(acc, flatten_keys(v, key)), else: Map.put(acc, key, v)
    end)
  end
end
''',
     '''
assert Bench.flatten_keys(%{"a" => %{"b" => 1, "c" => %{"d" => 2}}, "e" => 3}) ==
         %{"a.b" => 1, "a.c.d" => 2, "e" => 3}
assert Bench.flatten_keys(%{"a" => %{}}) == %{}
'''),

    ("counter_genserver", "medium",
     "Write an Elixir GenServer module `Bench.Counter` with: `start_link(initial)` returning "
     "`{:ok, pid}` (do not register a global name), `increment(pid)` and `increment(pid, n)` returning "
     "`:ok`, `value(pid)` returning the current integer, and `reset(pid)` setting it back to the "
     "initial value and returning `:ok`.",
     '''
defmodule Bench.Counter do
  use GenServer
  def start_link(initial), do: GenServer.start_link(__MODULE__, initial)
  def increment(pid, n \\\\ 1), do: GenServer.call(pid, {:inc, n})
  def value(pid), do: GenServer.call(pid, :value)
  def reset(pid), do: GenServer.call(pid, :reset)
  @impl true
  def init(i), do: {:ok, {i, i}}
  @impl true
  def handle_call({:inc, n}, _f, {i, v}), do: {:reply, :ok, {i, v + n}}
  def handle_call(:value, _f, {_, v} = s), do: {:reply, v, s}
  def handle_call(:reset, _f, {i, _}), do: {:reply, :ok, {i, i}}
end
''',
     '''
{:ok, a} = Bench.Counter.start_link(10)
{:ok, b} = Bench.Counter.start_link(0)
assert :ok = Bench.Counter.increment(a)
assert :ok = Bench.Counter.increment(a, 5)
assert Bench.Counter.value(a) == 16
assert Bench.Counter.value(b) == 0
assert :ok = Bench.Counter.reset(a)
assert Bench.Counter.value(a) == 10
'''),

    ("parse_kv_ex", "easy",
     "Write an Elixir module `Bench` with `parse_kv(string)` that parses \"a=1;b=2;;c=3\" into "
     "%{\"a\" => \"1\", \"b\" => \"2\", \"c\" => \"3\"}. Skip empty segments and segments with no '='. "
     "Split each segment on the first '=' only. Trim whitespace around keys and values.",
     '''
defmodule Bench do
  def parse_kv(s) do
    s |> String.split(";") |> Enum.flat_map(fn seg ->
      case String.split(seg, "=", parts: 2) do
        [k, v] -> [{String.trim(k), String.trim(v)}]
        _ -> []
      end
    end) |> Map.new()
  end
end
''',
     '''
assert Bench.parse_kv("a=1;b=2;;c=3") == %{"a" => "1", "b" => "2", "c" => "3"}
assert Bench.parse_kv("") == %{}
assert Bench.parse_kv(" x = y=z ; junk") == %{"x" => "y=z"}
'''),
]

# --------------------------------------------------------------------------
# Maths / reasoning: (id, question, integer answer). Answers worked by hand and
# double-checked in the selftest where computable.
# --------------------------------------------------------------------------
MATH = [
    ("timelapse", "A construction timelapse camera takes one photo every 10 minutes from 07:00 to 18:00 inclusive. How many photos does it take per day?", 67),
    ("train", "A train leaves at 14:35 and arrives at 17:10 the same day. How many minutes is the trip?", 155),
    ("multiples", "What is the sum of all positive integers below 100 that are multiples of 3 or 5?", 2318),
    ("markup", "A shop buys an item for 200 euros, marks the price up by 40%, then sells it at a 25% discount off the marked price. What is the selling price in euros?", 210),
    ("pen", "A notebook and a pen cost 11.00 dollars in total. The notebook costs 10.00 dollars more than the pen. How many cents does the pen cost?", 50),
    ("days", "How many days are there from 1 January 2026 to 1 March 2026, counting the end date but not the start date?", 59),
    ("snail", "A snail is at the bottom of a 20 metre well. Each day it climbs 3 metres; each night it slides back 2 metres. On which day does it first reach the top?", 18),
    ("widgets", "If 5 machines make 5 widgets in 5 minutes, how many minutes do 100 machines take to make 100 widgets?", 5),
    ("choose", "How many different 3-person committees can be chosen from 10 people?", 120),
    ("raid", "A storage server has 12 drives of 8 TB each in RAID 6. How many TB of usable capacity does it have?", 80),
    ("bitrate", "A camera streams video at a constant 5 megabits per second for 24 hours. How many gigabytes is that, using 1 GB = 10^9 bytes?", 54),
    ("modpow", "What is the remainder when 2^100 is divided by 7?", 2),
    ("lcm", "What is the least common multiple of 12, 18 and 30?", 180),
    ("ages", "Alice is twice as old as Bob was when Alice was as old as Bob is now. Alice is 24. How old is Bob?", 18),
    ("sevens", "How many integers from 1 to 1000 inclusive contain at least one digit 7?", 271),
    ("servers", "Three servers each finish one request every 4 seconds. How many requests do they finish together in one minute?", 45),
]
MATH_SUFFIX = "\n\nWork it out, then finish with a final line of the form `ANSWER: <integer>`."


def extract_int_answer(text: str):
    m = re.findall(r"ANSWER:\s*\**\s*(-?[\d,]+)", text)
    if m:
        return int(m[-1].replace(",", ""))
    nums = re.findall(r"-?\d[\d,]*", text)
    return int(nums[-1].replace(",", "")) if nums else None


# --------------------------------------------------------------------------
# Instruction following: (id, prompt, checker(text) -> bool)
# --------------------------------------------------------------------------
def _lines(t):
    return [l for l in t.strip().splitlines() if l.strip()]


def _json_ok(t):
    t = t.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        d = json.loads(t)
    except Exception:
        return False
    return (isinstance(d, dict) and set(d) == {"name", "year", "tags"}
            and isinstance(d["name"], str) and isinstance(d["year"], int)
            and isinstance(d["tags"], list) and len(d["tags"]) == 3
            and all(isinstance(x, str) for x in d["tags"]))


INSTRUCT = [
    ("five_lines", "List exactly 5 Elixir/OTP behaviours, one per line. No numbering, no bullets, no other text.",
     lambda t: len(_lines(t)) == 5 and not any(re.match(r"\s*([-*•]|\d+[.)])", l) for l in _lines(t))),
    ("json_only", "Reply with valid JSON only (no code fence, no commentary): an object with exactly the keys "
     "name (string), year (integer) and tags (array of exactly 3 strings), describing the Erlang language.",
     lambda t: _json_ok(t) and not t.strip().startswith("```")),
    ("no_letter_e", "Write one sentence of at least 8 words about databases without using the letter 'e' anywhere.",
     lambda t: "e" not in t.lower() and len(t.split()) >= 8),
    ("lowercase", "Answer entirely in lowercase letters: what is a mutex?",
     lambda t: t == t.lower() and len(t) > 20),
    ("three_bullets", "Give exactly 3 bullet points about caching. Each line must start with '- '. No other lines.",
     lambda t: len(_lines(t)) == 3 and all(l.startswith("- ") for l in _lines(t))),
    ("twelve_words", "Respond with exactly 12 words about the sea. Nothing else.",
     lambda t: len(t.split()) == 12),
    ("end_phrase", "Explain what DNS does in two sentences, and end your reply with the exact phrase 'Over and out.'",
     lambda t: t.strip().endswith("Over and out.")),
    ("answer_tags", "Wrap your entire reply in <answer></answer> tags, with nothing outside them. Inside, name the capital of Australia.",
     lambda t: re.fullmatch(r"\s*<answer>.*</answer>\s*", t, re.S) is not None and "canberra" in t.lower()),
    ("no_commas", "Explain what a load balancer does in at least 3 sentences without using a single comma.",
     lambda t: "," not in t and len(re.findall(r"[.!?](\s|$)", t)) >= 3),
    ("md_table", "Return a markdown table with columns Language and Paradigm and exactly 3 data rows. Only the table.",
     lambda t: len([l for l in _lines(t) if l.strip().startswith("|")]) == 5
     and len(_lines(t)) == 5 and "language" in _lines(t)[0].lower()),
]

# --------------------------------------------------------------------------
# Tool calling
# --------------------------------------------------------------------------
TOOLS = [
    {"type": "function", "function": {
        "name": "get_weather", "description": "Current weather for a city.",
        "parameters": {"type": "object", "properties": {
            "city": {"type": "string"},
            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}},
            "required": ["city"]}}},
    {"type": "function", "function": {
        "name": "search_flights", "description": "Search one-way flights.",
        "parameters": {"type": "object", "properties": {
            "origin": {"type": "string"}, "destination": {"type": "string"},
            "date": {"type": "string", "description": "YYYY-MM-DD"}},
            "required": ["origin", "destination", "date"]}}},
    {"type": "function", "function": {
        "name": "create_calendar_event", "description": "Create a calendar event.",
        "parameters": {"type": "object", "properties": {
            "title": {"type": "string"},
            "start": {"type": "string", "description": "ISO 8601 local datetime"},
            "duration_minutes": {"type": "integer"}},
            "required": ["title", "start", "duration_minutes"]}}},
    {"type": "function", "function": {
        "name": "calculator", "description": "Evaluate an arithmetic expression.",
        "parameters": {"type": "object", "properties": {"expression": {"type": "string"}},
                       "required": ["expression"]}}},
]


def _safe_eval(expr):
    if not re.fullmatch(r"[\d\s+\-*/().%]+", expr or ""):
        return None
    try:
        return eval(expr.replace("%", "/100"), {"__builtins__": {}})  # noqa: S307 - charset-restricted above
    except Exception:
        return None


def _args(call):
    try:
        return json.loads(call["arguments"] or "{}")
    except Exception:
        return None


def _one(calls, name):
    return len(calls) == 1 and calls[0]["name"] == name and _args(calls[0]) is not None


TOOL_CASES = [
    ("weather_unit", "What's the weather in Dublin right now? Use celsius.",
     lambda c: _one(c, "get_weather") and "dublin" in _args(c[0]).get("city", "").lower()
     and _args(c[0]).get("unit") == "celsius"),
    ("flights", "Find me flights from Paris to Algiers on 2026-12-20.",
     lambda c: _one(c, "search_flights")
     and any(x in _args(c[0]).get("origin", "").lower() for x in ["paris", "cdg", "ory"])
     and any(x in _args(c[0]).get("destination", "").lower() for x in ["algiers", "alg"])
     and _args(c[0]).get("date") == "2026-12-20"),
    ("calendar", "Put a 45 minute 'Design review' in my calendar on 2026-12-01 at 15:00.",
     lambda c: _one(c, "create_calendar_event")
     and "design review" in _args(c[0]).get("title", "").lower()
     and _args(c[0]).get("start", "").startswith("2026-12-01T15:00")
     and _args(c[0]).get("duration_minutes") == 45),
    ("calc_mul", "What is 1234 * 5678? Use the calculator.",
     lambda c: _one(c, "calculator") and _safe_eval(_args(c[0]).get("expression")) == 7006652),
    ("calc_pct", "What's 15% of 240?",
     lambda c: _one(c, "calculator") and abs((_safe_eval(_args(c[0]).get("expression")) or 0) - 36) < 1e-9),
    ("parallel_weather", "Compare the current weather in Tokyo and Oran.",
     lambda c: len(c) == 2 and all(x["name"] == "get_weather" for x in c)
     and {("tokyo" in (_args(x) or {}).get("city", "").lower(), "oran" in (_args(x) or {}).get("city", "").lower()) for x in c}
     == {(True, False), (False, True)}),
    ("no_tool_joke", "Tell me a short joke about compilers.", lambda c: len(c) == 0),
    ("no_tool_greeting", "Hi! What kinds of things can you help me with?", lambda c: len(c) == 0),
]

# --------------------------------------------------------------------------
# Personality - not scored. Collected verbatim for the article.
# --------------------------------------------------------------------------
PERSONALITY = [
    ("let_it_crash", "Explain Elixir's 'let it crash' philosophy as a 60-second stand-up comedy bit."),
    ("one_char_commit", "Write the git commit message for a bug fix that took six hours and changed one character."),
    ("small_fix_pr", "You're reviewing a pull request that adds 3,000 lines. Its description says 'small fix'. Write your review comment."),
    ("crane_giraffe", "A construction site manager asks why the timelapse camera's AI keeps labelling the tower crane as a giraffe. Explain, kindly but honestly."),
    ("segfault_haiku", "Write a haiku about a segfault."),
    ("roast_code", "Roast this code in at most four lines:\n\ndef is_even(n):\n    if n == 0: return True\n    if n == 1: return False\n    return is_even(n - 2)"),
]

# --------------------------------------------------------------------------
# Speed prompts - three genres, because speculative decoding's acceptance rate
# depends heavily on how predictable the output is.
# --------------------------------------------------------------------------
SPEED_GENRES = {
    "prose": "Write a detailed, roughly 600-word essay on the history of the printing press. Plain prose, no headings.",
    "code": "Write a complete Python module implementing a thread-safe LRU cache with TTL expiry, type hints, docstrings, and a small CLI demo. Only code.",
    "structured": "Output a JSON array of 40 objects, each with keys id (1..40), name, email, country, and active (boolean). Fictional data. Only the JSON.",
}
