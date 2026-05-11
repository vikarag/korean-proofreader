# Korean Proofreading Proxy

A local FastAPI service that fixes the predictable Korean-language failure modes of Chinese LLMs (DeepSeek, Qwen, Yi, etc.) — particle misuse, SVO bleed-through, spacing errors, calque expressions, inconsistent politeness, stiff endings, and Sino-Korean overuse. Pipe a raw LLM response through it and get back the same response with only the unnatural Korean surfaces rewritten. Code blocks, URLs, markdown structure, and non-Korean text pass through untouched.

## Why

Chinese LLMs often produce technically-correct-but-unnatural Korean. Examples:

- 조사 오류 — 은/는, 이/가, 을/를 misuse (Chinese has no particles)
- 어순 간섭 — Chinese SVO leaking into Korean SOV
- 띄어쓰기 — spacing errors, especially with compound nouns
- 존댓말 혼용 — inconsistent politeness levels within a single response
- 직역체 — calque expressions (`进行` → 진행하다 overuse)
- 어미 부자연스러움 — stiff, textbook-like sentence endings
- 한자어 과다 — Sino-Korean overuse where native Korean is more natural

This service is a thin proxy you call after generation. It is *not* a Korean grammar checker for human writing; it is targeted at machine output from non-Korean-native LLMs.

## Architecture

```
raw LLM output ──▶  /proofread  ──▶  language gate (Korean? skip if not)
                                       │
                                       ▼
                                     segmenter ── splits into Korean prose, code,
                                       │           URLs, markdown structure, etc.
                                       ▼
                                     cache (SHA-256 of text+tone+provider)
                                       │
                                       ▼
                                     proofreading LLM (Gemini / OpenAI / OpenRouter)
                                       │
                                       ▼
                                     reassembler (stitches segments back in order)
                                       │
                                       ▼
                                     corrected output (+ optional diff)
```

Only Korean prose segments are sent to the proofreading LLM. Everything else round-trips byte-identical.

## Quick start

```bash
git clone https://github.com/<you>/korean-proofreader.git
cd korean-proofreader

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp config.example.yaml config.yaml
# edit config.yaml and paste your API key(s)

python3 main.py
```

The server listens on `0.0.0.0:8787` by default.

Smoke test:

```bash
curl -s -X POST http://localhost:8787/proofread \
  -H 'Content-Type: application/json' \
  -d '{"text":"이 함수를 진행합니다.","return_diff":true}'
```

You should see `진행합니다` → something like `실행합니다` in the response.

## Configuration

Copy `config.example.yaml` to `config.yaml` and fill in at least one provider's `api_key`. `config.yaml` is gitignored.

### Using Google Gemini directly

```yaml
providers:
  gemini:
    api_key: "..."
    model: "gemini-2.5-flash"
    base_url: "https://generativelanguage.googleapis.com/v1beta"
defaults:
  provider: "gemini"
```

### Using OpenAI directly

```yaml
providers:
  openai:
    api_key: "sk-..."
    model: "gpt-4o-mini"
    base_url: "https://api.openai.com/v1"
defaults:
  provider: "openai"
```

### Using OpenRouter

OpenRouter is OpenAI-API-compatible. Just retarget the `openai` slot:

```yaml
providers:
  openai:
    api_key: "sk-or-v1-..."
    model: "openai/gpt-5.4-nano"   # or anthropic/claude-haiku-4.5, google/gemini-2.5-flash, etc.
    base_url: "https://openrouter.ai/api/v1"
defaults:
  provider: "openai"
```

Model slugs come from <https://openrouter.ai/models>.

## API

### `POST /proofread`

| Field         | Type    | Default    | Description |
|---------------|---------|------------|-------------|
| `text`        | string  | *required* | Raw LLM output to proofread |
| `mode`        | string  | `"auto"`   | `auto` skips when Korean ratio is below threshold; `force` always proofreads |
| `tone`        | string  | `"casual"` | `casual` (해요체) or `formal` (격식체) |
| `provider`    | string  | `"gemini"` | `gemini` or `openai` |
| `return_diff` | boolean | `false`    | If true, include per-segment changes in the response |
| `context`     | string  | `""`       | Optional original user prompt for tone matching |

Response:

```json
{
  "corrected": "이 함수를 실행합니다.",
  "was_modified": true,
  "korean_ratio": 0.78,
  "segments_proofread": 1,
  "segments_skipped": 0,
  "provider_used": "openai",
  "latency_ms": 412,
  "diff": [
    {
      "original": "이 함수를 진행합니다.",
      "corrected": "이 함수를 실행합니다.",
      "error_type": "직역체",
      "segment_index": 0
    }
  ]
}
```

### `GET /health`

Returns `{"status": "ok"}`.

### `GET /stats`

Returns correction counts by error type, computed from the JSONL correction log:

```json
{
  "error_counts": { "직역체": 12, "조사 오류": 3 },
  "total_corrections": 15
}
```

## How it works (slightly more detail)

1. **Language gate** (`core/detector.py`) — counts Korean characters (including jamo). If the ratio is below `detector.korean_ratio_threshold` and `mode="auto"`, the request short-circuits and returns the input untouched. No API spend.
2. **Segmenter** (`core/segmenter.py`) — a state machine that splits the input into typed segments: fenced code blocks, inline code, URLs, markdown headings, list items, Korean prose, English prose, whitespace. Each segment carries an index for reassembly.
3. **Cache** (`core/cache.py`) — SQLite. Key is `SHA-256(text|tone|provider)`. TTL configurable (default 24h). Tone- and provider-aware so a casual correction is never served to a formal request.
4. **Proofreader** (`core/proofreader.py`) — assembles a system prompt (`prompts/system_{tone}.txt` + `prompts/error_examples.txt`) and a per-segment user prompt with `[SEGMENT N]` markers. Calls Gemini or OpenAI/OpenRouter via `httpx.AsyncClient`. Parses the markers back to a `{segment_index: corrected_text}` dict.
5. **Reassembler** (`core/reassembler.py`) — walks the original segment list and writes `corrected[i]` where present, falling back to the original text otherwise. Markdown heading/list prefixes (`# `, `- `, `1. `) are preserved by stripping them from the original segment and prepending them back to the corrected text.
6. **Correction log** (`utils/logging.py`) — every correction is appended to `logs/corrections.jsonl` with its heuristic error type (조사, 직역체, 띄어쓰기, ...). This data feeds `/stats`.

## Development

```bash
pip install -r requirements.txt pytest pytest-asyncio
python3 -m pytest tests/ -v
```

Tests are pure-Python and offline. They cover the detector, segmenter, reassembler, and cache; they do not exercise the LLM call path.

## Project layout

```
korean-proofreader/
├── main.py                      # FastAPI app
├── config.example.yaml          # template — copy to config.yaml and fill in keys
├── requirements.txt
├── core/
│   ├── detector.py              # Korean-character ratio + min-char gate
│   ├── segmenter.py             # state-machine content splitter
│   ├── proofreader.py           # Gemini / OpenAI / OpenRouter calls
│   ├── reassembler.py           # stitch corrected segments back
│   └── cache.py                 # SQLite cache (tone+provider aware)
├── prompts/
│   ├── system_casual.txt        # 해요체 system prompt
│   ├── system_formal.txt        # 격식체 system prompt
│   └── error_examples.txt       # few-shot error/correction pairs
├── models/
│   ├── request.py               # Pydantic request schema
│   └── response.py              # Pydantic response schema
├── utils/
│   ├── diff.py                  # diff + heuristic error classifier
│   └── logging.py               # JSONL correction log + /stats source
└── tests/
    ├── test_detector.py
    ├── test_segmenter.py
    ├── test_reassembler.py
    ├── test_cache.py
    └── fixtures/                # sample LLM outputs for manual testing
```

## License

MIT (see `LICENSE` if present).
