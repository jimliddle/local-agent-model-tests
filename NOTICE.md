# Sources and attribution

The test controller, synthetic fixtures, Pi extension, runner and documentation
were written for these local experiments. They are released under the MIT
licence in this repository. Model-generated fixture answers and repaired
functions are identified by model and run in the result files. Those records
are evaluation evidence, not a redistribution of model weights or templates.

## Models

| Model | Authors or distributor | Source and licence |
|---|---|---|
| Qwen3.8-27B | Qwen Team | [Model card, Apache 2.0](https://huggingface.co/Qwen/Qwen3.8-27B) |
| Ornith 1.5 35B-A3B | Ornith | [Model card, MIT](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B), [official GGUF](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF) |
| Qwen3.8 Flash Next | Qwen Team; oQ4e/MTP distribution by Jundot | [Checkpoint](https://huggingface.co/Jundot/Qwen3.8-Flash-Next-oQ4e-mtp), [Qwen Community License 1.0](https://huggingface.co/Jundot/Qwen3.8-Flash-Next-oQ4e-mtp/blob/main/LICENSE) |
| Nanbeige4.3-33B | Nanbeige LLM Lab; Q8 GGUF by Bartowski | [Model card, Apache 2.0](https://huggingface.co/Nanbeige/Nanbeige4.3-33B), [GGUF distribution](https://huggingface.co/bartowski/Nanbeige_Nanbeige4.3-33B-GGUF) |

Licences were checked on 28 October 2026. In particular, Flash Next's Qwen
Community License is not Apache 2.0. Read the model's terms before downloading
or deploying it. This repo's MIT licence does not replace those terms or grant
rights to model weights.

## Tools and services

- [Pi](https://github.com/earendil-works/pi): coding agent used for the repair
  sessions. [MIT licence](https://github.com/earendil-works/pi/blob/main/LICENSE).
- [Ollama](https://github.com/ollama/ollama): Qwen and Ornith serving.
  [MIT licence](https://github.com/ollama/ollama/blob/main/LICENSE).
- [llama.cpp](https://github.com/ggml-org/llama.cpp): Nanbeige serving.
  [MIT licence](https://github.com/ggml-org/llama.cpp/blob/master/LICENSE).
- [oMLX](https://github.com/jundot/omlx): Flash Next serving.
  [Project licence](https://github.com/jundot/omlx/blob/main/LICENSE).
- [Tavily](https://www.tavily.com/): optional search and extraction service.
  Requires a separate account and API key; requests may incur charges.
- [Google Gemma model card](https://ai.google.dev/gemma/docs/core/model_card_4):
  primary source used in the dated live-research task. Page text is not bundled.

These dependencies are installed separately. No upstream runtime code,
weights, tokenizer files, chat templates or writing skills are vendored here.
The authors and distributors have not endorsed this comparison.
