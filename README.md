# arxiv-graph

arXiv 논문을 매일 자동으로 수집하고, 시맨틱 유사도·공저자 관계를 기반으로 지식 그래프를 구축하는 도구입니다.

## 개요

`arxiv-graph`는 cs.CL(자연어처리), cs.LG(머신러닝), cs.AI(인공지능) 카테고리의 최신 논문을 arXiv API로 수집하고,
문장 임베딩 모델을 활용해 논문 간 관계를 자동으로 탐지합니다.
PageRank와 최신성·인용수를 결합한 복합 중요도 점수로 논문의 영향력을 정량화합니다.

## 주요 기능

- **자동 논문 수집** — arXiv API로 지정 카테고리의 최신 논문을 주기적으로 가져옵니다
- **시맨틱 그래프 구성** — `all-MiniLM-L6-v2` 임베딩 + 코사인 유사도(임계값 0.75)로 관련 논문 간 엣지를 생성합니다
- **공저자 관계 추적** — 동일 저자가 작성한 논문들을 자동으로 연결합니다
- **복합 중요도 점수** — 최신성(30%) + 인용수(40%) + PageRank(30%) 가중 합산
- **일별 스케줄링** — APScheduler로 매일 06:00 UTC 자동 실행
- **SQLite 영구 저장** — 논문·저자·관계 데이터를 로컬 DB에 누적 관리

## 기술 스택

| 분야 | 라이브러리 |
| --- | --- |
| CLI | typer |
| 논문 수집 | arxiv |
| 임베딩 | sentence-transformers |
| 그래프 연산 | networkx |
| 유사도 계산 | scikit-learn |
| DB ORM | sqlalchemy (SQLite) |
| 스케줄링 | apscheduler |
| 로깅 | loguru |
| 패키지 관리 | uv |

## 설치

Python 3.12 및 [uv](https://docs.astral.sh/uv/)가 필요합니다.

```bash
git clone <repo-url>
cd arxiv-graph
uv sync
```

> 첫 실행 시 HuggingFace에서 `all-MiniLM-L6-v2` 모델(~90MB)이 자동 다운로드됩니다.

## 사용법

### 단발 수집

```bash
# 기본값: 최근 1일, 최대 200편
uv run arxiv-graph crawl

# 옵션 지정
uv run arxiv-graph crawl --days 3 --max 500
```

### 일별 자동 스케줄링

```bash
# 매일 06:00 UTC 실행 (프로세스 종료 시까지 블로킹)
uv run arxiv-graph schedule
```

### 통계 확인

```bash
# 수집된 논문 수, 관계 수, 상위 10개 논문 출력
uv run arxiv-graph stats
```

## 프로젝트 구조

```text
arxiv-graph/
├── src/arxiv_graph/
│   ├── cli.py               # Typer CLI 진입점 (crawl / schedule / stats)
│   ├── crawler/
│   │   ├── arxiv_client.py  # arXiv API 클라이언트
│   │   └── ingester.py      # DB upsert 로직
│   ├── graph/
│   │   ├── builder.py       # 시맨틱·공저자 엣지 생성 + PageRank
│   │   └── scorer.py        # 복합 중요도 점수 계산
│   ├── storage/
│   │   ├── db.py            # SQLAlchemy 세션·엔진 관리
│   │   └── models.py        # Paper / Author / PaperRelation ORM 모델
│   └── scheduler/
│       ├── runner.py        # APScheduler 설정
│       └── job.py           # 일별 작업 오케스트레이션
├── data/                    # SQLite DB 저장 위치 (gitignore)
├── logs/                    # 로그 파일 (gitignore)
└── pyproject.toml
```

## 데이터 모델

```text
Paper ──< paper_author >── Author
  │
  └── PaperRelation (source ↔ target)
        relation_type : "semantic" | "author"
        weight        : cosine similarity 또는 공저 횟수
```

**Paper**: `arxiv_id`, `title`, `abstract`, `pdf_url`, `published_at`, `importance_score`, `citation_count`, `categories`

**PaperRelation**: 시맨틱 유사도 엣지(임계값 0.75 초과) 또는 공저자 엣지

## 중요도 점수 계산

```text
score = 0.3 × recency + 0.4 × citations + 0.3 × pagerank
```

| 항목 | 계산 방식 |
| --- | --- |
| recency | 30일 반감기 지수 감쇠 |
| citations | `min(citation_count / 100, 1.0)` 정규화 |
| pagerank | 그래프 내 PageRank를 [0, 1]로 정규화 |

## 설정값

| 항목 | 기본값 |
| --- | --- |
| 수집 카테고리 | cs.CL, cs.LG, cs.AI |
| 시맨틱 유사도 임계값 | 0.75 |
| 임베딩 모델 | all-MiniLM-L6-v2 |
| 임베딩 배치 크기 | 64 |
| 최신성 반감기 | 30일 |
| 스케줄 실행 시각 | 매일 06:00 UTC |
| DB 경로 | `data/arxiv_graph.db` |

## 확장 포인트

- **인용수 연동**: `scorer.py`의 stub에 Semantic Scholar / OpenAlex API 연결
- **카테고리 추가**: `arxiv_client.py`의 `DEFAULT_CATEGORIES` 수정
- **유사도 모델 교체**: `builder.py`의 `_MODEL_NAME` 변경
- **DB 교체**: 각 함수의 `db_url` 파라미터로 PostgreSQL 등 지정 가능
