# ABC Camp RAG - YES24 IT/모바일 베스트셀러 대시보드

YES24 IT/모바일 종합 베스트셀러 도서 데이터를 수집하고, RAG(Retrieval-Augmented Generation) 검색과 대화형 대시보드를 제공하는 프로젝트입니다.

## 프로젝트 개요

- **데이터 수집**: YES24 IT/모바일 베스트셀러 페이지 크롤링
- **검색/RAG**: ChromaDB 벡터 스토어 기반 도서 의미 검색
- **대시보드**: Streamlit + Plotly 기반 EDA(탐색적 데이터 분석) 및 Groq LLM 대화형 질의
- **리포트**: OpenPyXL 기반 엑셀 대시보드 자동 생성

## 디렉터리 구조

```
ABC-RAG/
├── data/
│   └── yes24_it_mobile_bestseller.csv   # 수집된 베스트셀러 데이터 (커밋 대상)
├── src/
│   ├── scraper.py            # YES24 크롤러 (도서 목록 + 상세 소개 크롤)
│   ├── migrate_description.py# 기존 CSV에 도서 상세 소개 보완 마이그레이션
│   ├── embedding_store.py    # ChromaDB 임베딩/검색 저장소
│   ├── create_dashboard.py   # OpenPyXL 엑셀 대시보드 생성
│   └── app.py                # Streamlit 대시보드 애플리케이션
├── requirements.txt
└── .gitignore
```

> 참고: `data/*.xlsx`, `output/*.pptx`, `.venv/`, `.vscode/`, ChromaDB 데이터(`data/chroma_*`) 등은 `.gitignore`로 제외됩니다.

## 주요 모듈 설명

| 파일 | 역할 |
|------|------|
| `src/scraper.py` | YES24 베스트셀러 목록을 크롤링하고 병렬로 도서 상세 소개(Description)를 수집해 `data/yes24_it_mobile_bestsellers.csv`로 저장 |
| `src/migrate_description.py` | 기존 CSV에 도서 상세 소개 글을 병렬 크롤링하여 보완 마이그레이션 |
| `src/embedding_store.py` | ChromaDB `PersistentClient` 기반 임베딩 인덱스 구축 및 배치 검색 (컬렉션: `yes24_books`) |
| `src/create_dashboard.py` | Pandas + OpenPyXL로 KPI/차트(막대, 파이, 산점, 라인)가 포함된 엑셀 대시보드(`data/yes24_dashboard.xlsx`) 생성 |
| `src/app.py` | Streamlit 웹 대시보드. CSV 로드 후 Plotly 차트로 EDA 제공, Groq LLM을 활용한 도서 추천/질의 대화 기능 |

## 실행 방법

### 1. 환경 준비

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. 데이터 수집

```bash
python src/scraper.py
# 또는 상세 소개 보완 시
python src/migrate_description.py
```

### 3. 벡터 검색 인덱스 구축

```bash
python src/embedding_store.py
```

### 4. 엑셀 대시보드 생성

```bash
python src/create_dashboard.py
```

### 5. Streamlit 대시보드 실행

```bash
streamlit run src/app.py
```

## 환경 변수

- `GROQ_API_KEY`: `src/app.py`의 Groq LLM 대화 기능 사용 시 필요

## 커밋 정책

- **커밋 대상**: 수집된 CSV(`data/yes24_it_mobile_bestseller.csv`), 소스 코드(`src/*.py`), 설정(`requirements.txt`, `.gitignore`, `opencode.json`)
- **제외 대상**: 엑셀/파워포인트 문서(`data/*.xlsx`, `output/*.pptx`), 가상환경(`.venv/`), 에디터 설정(`.vscode/`), ChromaDB 데이터(`data/chroma_*`)

## 작업 내역

1. YES24 IT/모바일 베스트셀러 크롤러 및 상세 소개 수집 스크립트 구현 (`scraper.py`, `migrate_description.py`)
2. ChromaDB 기반 도서 검색 임베딩 스토어 구축 (`embedding_store.py`)
3. OpenPyXL 엑셀 대시보드 자동 생성 (`create_dashboard.py`)
4. Streamlit + Plotly + Groq LLM 대화형 대시보드 구현 (`app.py`)
5. `.gitignore` 정비 (문서/가상환경/DB 제외) 및 README 작성