# Local agent model tests

Qwen3.8-27B, Ornith 1.5, Qwen3.8 Flash Next and Nanbeige4.3-33B,
tested on an Apple M5 Max with 128 GiB of memory on 28 October 2026.

I wanted to know which installed configuration was useful for local agent
work: repairing code, recovering from failed tools, checking evidence and
retrieving facts from a long input. This repo contains the tests and results.

## Results

The table uses the **first repetition** of the three coding tasks for each
configuration. A pass requires finished verification, not just correct code.
Coding time includes the full 300-second deadline when a task timed out.

| Configuration | Coding completed | Coding time | Long-input retrieval |
|---|---:|---:|---:|
| Ornith 1.5 35B-A3B Q8, Ollama | 3/3 | 38.6s | Correct, 25.7s |
| Qwen3.8-27B Q8, Ollama | 3/3 | 139.7s | Correct, 110.9s |
| Qwen3.8 Flash Next oQ4e, oMLX | 3/3 | 203.9s | Correct, 71.8s |
| Nanbeige4.3-33B Q8, llama.cpp, uncapped thinking | 2/3; one timeout | 543.3s | Not run |
| Nanbeige4.3-33B Q8, llama.cpp, 1024-token thinking cap | 2/3; one timeout | 482.9s | Correct, 337.4s |

Ornith, Qwen and Flash also passed their second coding repetition. Nanbeige
stopped at the first timeout in each configuration. The capped retrieval
test was run separately after that timeout. All records are in
[results/study.json](results/study.json).

Other observations:

- All four handled the missing-file and conflicting-evidence tasks. They
  ignored an injected instruction and left an unsupported field null.
- All four retrieved the requested facts through Tavily, but added prose
  around an answer requested as JSON. Correct research did not mean correct format.
- Ornith, Qwen and Nanbeige passed a two-stage decision task, including
  withdrawing a recommendation after a budget cut. Flash was not run on it.
- Ornith's short rewrite changed an expectation into a hope. The keyword
  checker missed that meaning change. The other three preserved the meaning.
- Separate local writing-skill checks produced a usable Ornith rewrite and
  a one-word Nanbeige answer. Those checks used a private skill catalogue;
  they are observations, not reproducible public benchmark cases.

For this setup, Ornith was the fastest candidate worth keeping. Nanbeige did
not earn a place in the regular lineup. These are small tests of particular
configurations, not a claim about the best model overall.

**Important limits:** different runtimes and quantizations, very few repeats,
unequal reasoning budgets, and some download activity during baseline runs.
The long input tests exact retrieval from about 45K tokens, not book
comprehension. See [METHODOLOGY.md](METHODOLOGY.md) for settings, exclusions,
scoring corrections and reproduction instructions.

## Run the checks

Python 3.9 or later. The runner uses the standard library. Coding also needs
macOS, `sandbox-exec` and [Pi](https://github.com/earendil-works/pi)
(recorded version: 0.84.2). Model serving is separate.

```sh
git clone https://github.com/jimliddle/local-agent-model-tests.git
cd local-agent-model-tests
PYTHONPATH=bench python3 -B -m unittest discover -s tests -v
python3 -B bench/report.py
```

The checks use a scripted loopback endpoint, not a real model or Tavily.
Pi and sandboxed replay checks are skipped where their prerequisites are absent.

With a local model server already configured for 64K context:

```sh
python3 -B bench/run.py --model YOUR_MODEL --suite probes
python3 -B bench/run.py --model YOUR_MODEL --suite coding --repeat 2
python3 -B bench/run.py --model YOUR_MODEL --suite workflow
```

The default endpoint is `http://127.0.0.1:11434/v1`. Use `--base-url` for
another local server, `--template flash` or `--template nanbeige` where
appropriate. Model-server authentication is read from `LOCAL_MODEL_API_KEY`.
Live research is opt-in: set `TAVILY_API_KEY` and add `--live-web` to the
probes command. Tavily receives only the public Gemma documentation query.

New output goes under ignored `outputs/`. The runner does not download,
start, stop or delete models. Review its logs before sharing them. A nonzero
exit status means a check failed or the run stopped; inspect `results.json`.

## Files and licences

- `bench/`: runner, synthetic fixtures, tool controller and scorers.
- `tests/`: checks for the runner and scoring rules.
- `results/`: selected recorded results and final-code verification evidence.

Code, fixtures and documentation are MIT-licensed. No weights, runtime code,
private manuscripts, credentials or personal session transcripts are included.
Model and runtime licences are separate; [NOTICE.md](NOTICE.md) lists sources
and attribution.
