# Korean Proofreading Proxy (한국어 교정 프록시)

중국어권 LLM(DeepSeek, Qwen, Yi 등)이 만들어내는 한국어 출력의 전형적인 결함 — 조사 오류, 어순 간섭, 띄어쓰기 오류, 직역체, 존댓말 혼용, 어색한 어미, 한자어 과다 사용 — 을 자동으로 교정하는 로컬 FastAPI 서비스입니다. 원본 응답을 그대로 흘려보내면, 어색한 한국어 부분만 다듬은 동일한 응답이 돌아옵니다. 코드 블록, URL, 마크다운 구조, 비한국어 텍스트는 손대지 않고 그대로 통과시킵니다.

## 왜 만들었나

중국어 LLM이 만들어내는 한국어는 의미는 맞지만 어색한 경우가 잦습니다. 대표적인 패턴은 다음과 같습니다.

- **조사 오류** — 은/는, 이/가, 을/를 등 (중국어에는 조사가 없어서 자주 틀립니다)
- **어순 간섭** — 중국어 SVO 어순이 한국어 SOV에 스며드는 현상
- **띄어쓰기 오류** — 특히 복합 명사에서 자주 발생
- **존댓말 혼용** — 한 응답 안에서 격식체와 비격식체가 뒤섞임
- **직역체** — 중국어 표현을 그대로 직역한 어색한 한국어 (예: `进行` → 진행하다 남용)
- **어미 부자연스러움** — 교과서 같은 딱딱한 문장 끝맺음
- **한자어 과다 사용** — 고유어가 자연스러운 자리에 한자어를 남발

이 서비스는 LLM 생성 후 한 번 거쳐가는 얇은 프록시입니다. 사람이 쓴 한국어를 검토하는 일반 문법 검사기가 **아니라**, 한국어 비원어민 모델이 만든 기계 출력에 특화되어 있습니다.

## 아키텍처

```
원본 LLM 출력 ──▶  /proofread  ──▶  언어 감지 게이트 (한국어 아니면 통과)
                                       │
                                       ▼
                                     세그멘터 ── 한국어 산문, 코드, URL,
                                       │         마크다운 구조 등으로 분할
                                       ▼
                                     캐시 (SHA-256: 텍스트+tone+provider)
                                       │
                                       ▼
                                     교정 LLM (Gemini / OpenAI / OpenRouter)
                                       │
                                       ▼
                                     재조립기 (원래 순서대로 다시 합치기)
                                       │
                                       ▼
                                     교정된 출력 (+ 선택적 diff)
```

한국어 산문 세그먼트만 교정 LLM으로 보냅니다. 그 외 모든 부분은 바이트 단위로 그대로 왕복합니다.

## 빠른 시작

```bash
git clone https://github.com/<your-username>/korean-proofreader.git
cd korean-proofreader

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp config.example.yaml config.yaml
# config.yaml을 열어 API 키를 채워 넣으세요

python3 main.py
```

서버는 기본으로 `0.0.0.0:8788`에서 실행됩니다.

테스트 호출:

```bash
curl -s -X POST http://localhost:8788/proofread \
  -H 'Content-Type: application/json' \
  -d '{"text":"이 함수를 진행합니다.","return_diff":true}'
```

응답에서 `진행합니다` → `실행합니다`(또는 비슷한 자연스러운 표현)로 바뀐 것을 확인할 수 있습니다.

## 설정

`config.example.yaml`을 `config.yaml`로 복사한 뒤, 사용할 제공자 중 최소 하나의 `api_key`를 채워 넣으세요. `config.yaml`은 `.gitignore`에 포함되어 있어 커밋되지 않습니다.

### Google Gemini를 직접 사용하는 경우

```yaml
providers:
  gemini:
    api_key: "..."
    model: "gemini-2.5-flash"
    base_url: "https://generativelanguage.googleapis.com/v1beta"
defaults:
  provider: "gemini"
```

### OpenAI를 직접 사용하는 경우

```yaml
providers:
  openai:
    api_key: "sk-..."
    model: "gpt-4o-mini"
    base_url: "https://api.openai.com/v1"
defaults:
  provider: "openai"
```

### OpenRouter를 사용하는 경우

OpenRouter는 OpenAI API와 호환되므로 `openai` 슬롯을 그대로 활용하면 됩니다.

```yaml
providers:
  openai:
    api_key: "sk-or-v1-..."
    model: "openai/gpt-5.4-nano"   # 또는 anthropic/claude-haiku-4.5, google/gemini-2.5-flash 등
    base_url: "https://openrouter.ai/api/v1"
defaults:
  provider: "openai"
```

사용 가능한 모델 슬러그는 <https://openrouter.ai/models>에서 확인할 수 있습니다.

## API

### `POST /proofread`

| 필드          | 타입    | 기본값     | 설명 |
|---------------|---------|------------|------|
| `text`        | string  | *필수*     | 교정할 원본 LLM 출력 |
| `mode`        | string  | `"auto"`   | `auto`는 한국어 비율이 임계값 미만이면 건너뜀, `force`는 항상 교정 |
| `tone`        | string  | `"casual"` | `casual`(해요체) 또는 `formal`(격식체) |
| `provider`    | string  | `"gemini"` | `gemini` 또는 `openai` |
| `return_diff` | boolean | `false`    | `true`이면 세그먼트별 변경 사항을 응답에 포함 |
| `context`     | string  | `""`       | 원래 사용자 프롬프트 (어조 일치에 도움이 됨, 선택) |

응답 예시:

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

`{"status": "ok"}`를 반환합니다.

### `GET /stats`

JSONL 교정 로그를 집계해 오류 유형별 카운트를 반환합니다.

```json
{
  "error_counts": { "직역체": 12, "조사 오류": 3 },
  "total_corrections": 15
}
```

## 동작 원리

1. **언어 게이트** (`core/detector.py`) — 한글 자모를 포함한 한국어 문자 수를 셉니다. `mode="auto"`이고 비율이 `detector.korean_ratio_threshold` 미만이면 즉시 원문을 그대로 반환합니다. API 비용을 아끼는 장치입니다.
2. **세그멘터** (`core/segmenter.py`) — 상태 기계 방식으로 입력을 타입별로 쪼갭니다. 펜스 코드 블록, 인라인 코드, URL, 마크다운 헤딩/리스트, 한국어 산문, 영어 산문, 공백 등으로 분류하고, 재조립을 위해 각 세그먼트에 인덱스를 부여합니다.
3. **캐시** (`core/cache.py`) — SQLite. 키는 `SHA-256(텍스트|tone|provider)`. TTL은 설정 가능(기본 24시간). tone과 provider를 키에 포함하므로 캐주얼한 교정 결과가 격식체 요청에 잘못 반환되는 일이 없습니다.
4. **교정기** (`core/proofreader.py`) — 시스템 프롬프트(`prompts/system_{tone}.txt` + `prompts/error_examples.txt`)와 `[SEGMENT N]` 마커가 붙은 사용자 프롬프트를 조립합니다. `httpx.AsyncClient`로 Gemini 또는 OpenAI/OpenRouter를 호출하고, 응답에서 마커를 파싱해 `{세그먼트_인덱스: 교정된_텍스트}` 형태로 되돌립니다.
5. **재조립기** (`core/reassembler.py`) — 원래 세그먼트 목록을 순서대로 순회하며 교정된 텍스트가 있는 자리에는 교정본을, 없는 자리에는 원본을 채워 넣습니다. 마크다운 헤딩/리스트의 접두사(`# `, `- `, `1. `)는 원본에서 분리해두었다가 교정본 앞에 다시 붙입니다.
6. **교정 로그** (`utils/logging.py`) — 모든 교정 사례는 휴리스틱으로 분류한 오류 유형(조사, 직역체, 띄어쓰기 등)과 함께 `logs/corrections.jsonl`에 추가됩니다. `/stats` 엔드포인트가 이 로그를 집계합니다.

## 개발

```bash
pip install -r requirements.txt pytest pytest-asyncio
python3 -m pytest tests/ -v
```

테스트는 순수 파이썬으로 오프라인에서 실행됩니다. 디텍터, 세그멘터, 재조립기, 캐시를 다루며, LLM 호출 경로는 검사하지 않습니다.

## 프로젝트 구조

```
korean-proofreader/
├── main.py                      # FastAPI 앱
├── config.example.yaml          # 템플릿 — config.yaml로 복사 후 키를 채워 사용
├── requirements.txt
├── core/
│   ├── detector.py              # 한국어 문자 비율 + 최소 글자 수 게이트
│   ├── segmenter.py             # 상태 기계 기반 콘텐츠 분할기
│   ├── proofreader.py           # Gemini / OpenAI / OpenRouter 호출
│   ├── reassembler.py           # 교정된 세그먼트 재조립
│   └── cache.py                 # SQLite 캐시 (tone+provider 인식)
├── prompts/
│   ├── system_casual.txt        # 해요체 시스템 프롬프트
│   ├── system_formal.txt        # 격식체 시스템 프롬프트
│   └── error_examples.txt       # 오류/교정 few-shot 예시
├── models/
│   ├── request.py               # Pydantic 요청 스키마
│   └── response.py              # Pydantic 응답 스키마
├── utils/
│   ├── diff.py                  # diff + 휴리스틱 오류 분류기
│   └── logging.py               # JSONL 교정 로그 + /stats 데이터 소스
└── tests/
    ├── test_detector.py
    ├── test_segmenter.py
    ├── test_reassembler.py
    ├── test_cache.py
    └── fixtures/                # 수동 테스트용 LLM 출력 샘플
```

## 라이선스

MIT (`LICENSE` 파일이 있는 경우 참조).
