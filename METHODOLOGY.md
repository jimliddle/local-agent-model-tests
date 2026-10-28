# Method and reproduction

## Recorded setup

Hardware: Apple M5 Max, 137,438,953,472 bytes of unified memory (128 GiB),
macOS 26.5. The host hardware was checked during publication. This was not
an idle-machine performance lab. Downloads ran during some baseline tests;
disk and thermal conditions were not controlled. Initial model warmup is
excluded from task timings, but per-task prompt processing is included.

Shared settings: 65,536-token context, temperature 0.6, top_p 0.95, up to
8,192 output tokens, seed 4200 for the first coding repetition and API probes,
4201 for the second coding repetition. Server/profile sampling used top_k 20
and min_p 0 where supported. Reasoning was enabled. The `low` label is not
an equal reasoning budget across these runtimes.

| Model | Source | Runtime | Weight identity |
|---|---|---|---|
| Qwen3.8-27B Q8 | Ollama `qwen3.8:27b-q8_0` | Ollama 0.40.4 | GGUF SHA-256 in study.json; upstream revision not recorded |
| Ornith 1.5 35B-A3B Q8 | `ornith-ai/Ornith-1.5-35B-A3B-GGUF` | Ollama 0.40.4 | Revision `12393612fd4f730ff5aadc23e9b8f9648aa49ceb` |
| Qwen3.8 Flash Next oQ4e/MTP | `Jundot/Qwen3.8-Flash-Next-oQ4e-mtp` | oMLX 0.7.1.dev1 | Revision `2615fc0e976e65c2f3b55daca3a948f1cdc5b9f8` |
| Nanbeige4.3-33B Q8 | `bartowski/Nanbeige_Nanbeige4.3-33B-GGUF` | llama.cpp build 10720, `d807f04ea` | Revision `9beb68421fdf7be095093a6888325fa2c83ddd38` |

Pi 0.84.2 ran the coding tasks. Flash used expert offloading with 25% of
experts resident and MTP enabled. Its server default disabled thinking;
test requests explicitly enabled it. oMLX release commit:
`c0b1056b41ebde9422af316cf5038a423eb8f24c`.

Nanbeige used F16 KV cache, flash attention, one slot and its embedded Jinja
template with XML tools and preserved reasoning. A template sentinel and a
later rendered Pi prompt verified that reasoning history survived. The first
configuration had no thinking cap; the follow-up imposed 1,024 thinking tokens
per response. This is not the author's recommended temperature 1.0 and much
larger agent output budget. The findings concern this bounded local setup.

Memory observations use different measures and should not be ranked: Ollama
reported 33.9 GB resident for Qwen and 39.3 GB for Ornith; Nanbeige process RSS
was about 49.9 GB. A comparable Flash peak was not recorded.

## Tasks and scoring

The coding tasks repair `ranges`, `chunks` and `duration`. Each exposes only
read-source, replace-source and run-check tools. A successful task needs
fresh syntax, unit and integration receipts tied to the final source hash,
passing hidden assertions, and normal completion within 300 seconds. Each
Pi task allows at most 12 requests. There are 14 hidden assertions across
the three tasks per repetition. The hidden tests are now public, so this
cannot serve as a contamination-resistant benchmark.

The duration verifier fails once deliberately. The agent should retry that
check without editing good code. Nanbeige's uncapped run left correct code
but timed out before verification completed. Its capped run changed a correct
conversion into an unweighted sum, received a real test failure and timed out
without fixing it. Neither run counts as a completed repair.

The API probes cover simple JSON, missing-file recovery, an injected
instruction, conflicting policy passages, an unknown field, a simulated
search outage, long-input retrieval and a short factual rewrite. The long
fixture has 1,800 records and three exact codes near the beginning, middle
and end. Prompt token counts were 44,867 for Ornith, 44,893 for Qwen and
Flash, and 44,871 for Nanbeige. Each probe ran once per configuration shown.

Live research used Tavily search and extraction of Google's
[Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4).
The expected answers were 131,072 and 262,144 tokens on the test date.
Web content can change. The public runner retains those dated expectations;
inspect fresh evidence before treating a future mismatch as a model failure.

The revision task uses fictional product documents. Birch meets the initial
budget; after a reduction from nine to six credits, none qualifies. A current
benchmark replaces an older one, a fetch fails once, and an injected claim
must be ignored. All three tested models passed both phases: Ornith in
16.2s, Qwen in 108.6s, Nanbeige in 158.1s. Flash was not tested. The scorer
checks fields and evidence reads; saved reasons also received manual review.

### Corrections and exclusions

- The original outage scorer required exactly one call. Ornith and Nanbeige
  made two calls before either failed, then stopped. Chronological review
  passes both. Raw `passed` fields remain unchanged beside review fields.
- The writing checker only tests length and keywords. It missed Ornith's
  change from expecting a longer run to hoping for one. Manual meaning
  checks are separate; no authorship detector was used.
- The local skill checker confirmed a skill read and nonempty text, not a
  good rewrite. Nanbeige's final answer was just "We", despite a normal
  stop. The content review fails it. Ornith's skill-assisted sample retained
  meaning but had awkward wording. The private 24-skill catalogue and shared
  prompt are not distributed; these two observations cannot be exactly rerun
  from this repo and should not be included in a public pass-rate total.
- Flash attempt `182418` failed authentication before inference and is excluded.
- Nanbeige attempt `192226` failed a port preflight before inference and is excluded.
- Ornith revision attempt `185727` used an ambiguous eligibility instruction.
  Version 2 clarified that handwriting accuracy was informational. Only
  version 2 is compared; the excluded version 1 result remains in the data.

## Running against local servers

The public runner assumes a separately configured server. It does not enforce
the context window at the server, install models or manage model lifetimes.
Use one model at a time and check the actual server settings. Leave enough
memory for the KV cache and operating system. Stop models yourself after use.

For Ollama, pull the desired source, then create a temporary alias with a
Modelfile like this (replace the source for Ornith):

```text
FROM qwen3.8:27b-q8_0
PARAMETER num_ctx 65536
PARAMETER num_predict 8192
PARAMETER temperature 0.6
PARAMETER top_p 0.95
PARAMETER top_k 20
PARAMETER min_p 0
```

```sh
ollama create bench-qwen -f Modelfile
python3 -B bench/run.py --model bench-qwen --suite coding --repeat 2
python3 -B bench/run.py --model bench-qwen --suite probes
python3 -B bench/run.py --model bench-qwen --suite workflow
ollama stop bench-qwen
ollama rm bench-qwen
```

For Nanbeige, the recorded llama.cpp server arguments were equivalent to:

```sh
llama-server -m /path/to/Nanbeige_Nanbeige4.3-33B-Q8_0.gguf \
  --alias nanbeige-test --host 127.0.0.1 --port 18195 \
  -c 65536 -np 1 -ngl 99 -fa on -ctk f16 -ctv f16 \
  --jinja --chat-template-kwargs '{"enable_thinking":true,"preserve_thinking":true,"tool_call_format":"xml"}' \
  --reasoning-format deepseek --reasoning-budget 1024 \
  --no-context-shift --no-webui --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0
```

In another terminal:

```sh
python3 -B bench/run.py --base-url http://127.0.0.1:18195/v1 \
  --model nanbeige-test --template nanbeige --suite coding --repeat 1
```

Use `--reasoning-budget -1` on the server for the uncapped configuration.
The probe and workflow suites use the same endpoint/template arguments.
Nanbeige weights were removed from the author's machine after evaluation;
they are not included here.

For Flash, use the linked oMLX release and pinned checkpoint. Configure
`max_context_window=65536`, `max_tokens=8192`,
`moe_expert_offload_enabled=true`, `moe_expert_offload_resident_fraction=0.25`,
`mtp_enabled=true` and one concurrent request. The recorded server used
`--memory-guard-gb 48`, a 1GB hot cache and a 4GB paged SSD cache. Point the
runner at its loopback `/v1` endpoint and pass `--template flash`.
Changing offload, cache or MTP settings makes it a different speed comparison.

## Public runner and evidence

This is a standalone extraction of the experiment code, not the untouched
private harness. Fixture text and repair scoring are retained. Local paths,
profile imports and lifecycle management were removed. Profiles are generated
from explicit settings; keys come from environment variables.

The live adapter now uses Tavily's HTTP API instead of the private MCP wrapper.
Its response envelope and receipts differ, so fresh research timings are not
strict reproductions. The public JSON parser also rejects trailing prose after
a fenced object; the old parser was permissive in that case. Recorded scores
were not recomputed. New runs use a 600-second request timeout and a 512-token
warmup; the earlier comparison used 300 seconds and 256 warmup tokens. Neither
change alters the stored results. Coding retains its 300-second task deadline.

`study.json` exports selected numeric results, short synthetic answers, saved
decisions, manual review flags and source-file hashes. `repair-evidence.json`
contains final functions and verification receipts. Full reasoning traces,
rendered prompts, private skill text, raw scraped pages and local paths are
omitted. Web receipts retain URLs, extraction lengths and hashes, not page text.
Hashes identify the private originals; they do not independently prove their
contents. The exported evidence is sufficient to inspect scores and replay
the final-code checks, but is not a full execution transcript.

The generated-code evaluator is deliberately narrow and uses macOS
`sandbox-exec`, restricted builtins, an AST check and short process limits.
It is not a general-purpose Python security boundary. Use a disposable
account or machine for untrusted experiments; do not remove these restrictions
to make a model pass. Offline probes and workflow tools manipulate synthetic
data in memory and do not execute model-generated code.
