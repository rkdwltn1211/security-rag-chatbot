<div align="center">

# 🔐 기업 IT 보안 정책 AI 어시스턴트
### ISMS-P 문서 기반 Self-Correction RAG 시스템

**"단순히 RAG를 만든 것이 아니라, 답변의 환각(Hallucination)을 줄이기 위해 이중 검증 루프를 설계했습니다."**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.1-4B8BBE?style=flat-square)](https://langchain-ai.github.io/langgraph/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-0.4-FF6B35?style=flat-square)](https://www.trychroma.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?style=flat-square&logo=postgresql)](https://www.postgresql.org)
[![AWS EC2](https://img.shields.io/badge/AWS-EC2-FF9900?style=flat-square&logo=amazonaws)](https://aws.amazon.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker)](https://www.docker.com)

🌐 **[라이브 데모 바로가기 →](http://3.26.94.252/)**

</div>

---

## 📸 서비스 화면

<table>
  <tr>
    <td align="center" width="50%">
      <img src="docs/screenshots/login.png" alt="로그인 화면" width="100%"/>
      <br/><sub><b>로그인 — JWT 기반 권한 인증</b></sub>
    </td>
    <td align="center" width="50%">
      <img src="docs/screenshots/dashboard.png" alt="관리자 대시보드" width="100%"/>
      <br/><sub><b>ADMIN 전용 로그 분석 대시보드</b></sub>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%">
      <img src="docs/screenshots/chatbot_action.png" alt="ACTION 유형 답변" width="100%"/>
      <br/><sub><b>ACTION 유형 — 단계별 절차 답변</b></sub>
    </td>
    <td align="center" width="50%">
      <img src="docs/screenshots/chatbot_security.png" alt="SECURITY 권한 다중 출처" width="100%"/>
      <br/><sub><b>SECURITY 권한 — 다중 문서 출처 표시</b></sub>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%">
      <img src="docs/screenshots/chatbot_blocked.png" alt="범위 외 질문 차단" width="100%"/>
      <br/><sub><b>범위 외 질문 차단 — 출처 없으면 답변 거부</b></sub>
    </td>
    <td align="center"></td>
  </tr>
</table>

> 📌 **이미지 업로드 방법**: `docs/screenshots/` 폴더에 위 파일명으로 이미지를 추가하면 자동 표시됩니다.
> - `login.png` → 로그인 화면
> - `dashboard.png` → 대시보드 화면
> - `chatbot_action.png` → 단계별 답변 화면
> - `chatbot_security.png` → SECURITY 권한 화면
> - `chatbot_blocked.png` → 범위 외 질문 차단 화면

---

## 🎯 핵심 차별화 포인트

> 일반 RAG는 **"검색 → 생성"** 으로 끝납니다.  
> 이 프로젝트는 **"검색 → 관련성 평가 → 생성 → 환각 검증 → 재시도"** 이중 루프로 신뢰성을 높였습니다.

| 포인트 | 설명 |
|--------|------|
| 🔄 **Self-Correction** | 생성된 답변을 LLM이 다시 검증 (PASS/FAIL). FAIL 시 자동 재생성 (최대 2회) |
| 🔍 **Hybrid Search** | 벡터 유사도 검색(ChromaDB) + 키워드 검색(BM25)을 병행하여 검색 누락 최소화 |
| ✏️ **Query Rewriting** | 재검색 시 LLM이 질문을 키워드 중심으로 자동 재작성하여 검색 다양성 확보 |
| 🔐 **권한별 문서 접근** | EMPLOYEE / SECURITY / ADMIN 3단계 권한에 따라 접근 가능한 문서가 다름 |
| 📊 **운영 대시보드** | ADMIN 전용 로그 분석 화면 — PASS/FAIL 비율, 질문 유형 통계, 사용자별 집계 |
| 🚫 **출처 없으면 차단** | 검색 결과가 없으면 답변 자체를 거부 — 근거 없는 답변 원천 차단 |

---

## 🏗️ 시스템 아키텍처

```
사용자 (React)
    │
    │  HTTP (JWT 토큰)
    ▼
FastAPI 백엔드 ──────────────── PostgreSQL
    │                           (질문/답변/로그)
    │
    ▼
LangGraph 워크플로우
    │
    ├── ① categorize      질문 유형 분류 (ACTION / DEFINITION / POLICY)
    │
    ├── ② retrieve        Hybrid Search (벡터 + BM25) + 권한 필터
    │       │
    │       └── [재검색 시] Query Rewriting → k값 증가 (4→8→12)
    │
    ├── ③ grade_docs      문서 관련성 평가 (RELEVANT / IRRELEVANT)
    │       │
    │       └── IRRELEVANT → 재검색 (최대 2회)
    │
    ├── ④ generate        유형별 맞춤 프롬프트로 답변 생성
    │
    └── ⑤ check_hallucination   환각 검증 (PASS / FAIL)
            │
            └── FAIL → 재생성 (최대 2회)
                        │
                        └── 출처 없음 → 답변 차단
    │
    ▼
ChromaDB (벡터스토어)
문서별 permission 메타데이터로 권한 필터링
```

---

## ⚙️ 기술 스택 및 선택 이유

| 분류 | 기술 | 선택 이유 |
|------|------|-----------|
| **AI 워크플로우** | LangGraph | 순환형 그래프 구조로 검증 → 재시도 루프를 명확하게 표현 |
| **벡터 검색** | ChromaDB | 의미 기반 유사도 검색; 자연어 질문에 키워드 DB보다 유연 |
| **키워드 검색** | BM25Retriever | 고유명사(ISMS-P 등) 정확 검색; 벡터 검색의 약점 보완 |
| **임베딩** | text-embedding-3-small | 비용 효율적이면서 한국어 문서 처리 성능 검증 |
| **백엔드** | FastAPI | 비동기 처리, 자동 Swagger 문서, Pydantic 타입 안전성 |
| **로그 DB** | PostgreSQL | 정형 로그 저장 및 대시보드 집계 쿼리 최적화 |
| **인증** | JWT (HS256) | Stateless 토큰으로 권한(role) 정보 내장, 서버 세션 불필요 |
| **프론트엔드** | React (Vite) | 상태 기반 실시간 챗봇 UI; FastAPI JSON 응답과 자연스러운 연동 |
| **배포** | AWS EC2 + Docker | 환경 차이 제거(컨테이너화) + 클라우드 배포 일관성 확보 |

---

## 🔑 주요 기능

### 1. Self-Correction RAG 파이프라인

```python
# LangGraph 이중 루프 구조
graph.add_conditional_edges(
    "grade_docs",
    check_relevance,          # 문서 관련성 평가
    {"relevant": "generate", "irrelevant": "increment_retrieve"}
)
graph.add_conditional_edges(
    "check_hallucination",
    should_retry,             # 환각 검증
    {"end": END, "retry": "increment_retry"}
)
```

### 2. Hybrid Search + Query Rewriting

```python
# 벡터 검색 + BM25 병행 후 중복 제거
vector_docs = vectorstore.similarity_search(question, k=k, filter=filter_dict)
bm25_docs   = bm25_retriever.invoke(question)

seen, combined = set(), []
for doc in vector_docs + bm25_docs:
    if doc.page_content not in seen:
        seen.add(doc.page_content)
        combined.append(doc)

# 재검색 시 질문 자동 재작성
if state["retrieve_count"] > 0:
    question = llm.invoke(rewrite_prompt)  # 키워드 중심으로 재작성
    k += 4                                  # 검색 범위 확장
```

### 3. 권한별 문서 접근 제어

```python
# 권한 레벨에 따라 ChromaDB 필터 동적 생성
ROLE_LEVELS = {"EMPLOYEE": 1, "SECURITY": 2, "ADMIN": 3}
accessible = [r for r, l in ROLE_LEVELS.items() if l <= user_level]

# SECURITY → ["EMPLOYEE", "SECURITY"] 문서만 검색
filter_dict = {"$or": [{"permission": p} for p in accessible]}
vector_docs = vectorstore.similarity_search(question, k=k, filter=filter_dict)
```

### 4. 질문 유형별 맞춤 프롬프트

| 유형 | 예시 질문 | 답변 형식 |
|------|----------|-----------|
| `ACTION` | "랜섬웨어 감염 시 어떻게 해?" | 단계별 절차 (1, 2, 3...) |
| `DEFINITION` | "ISMS-P가 뭐야?" | 용어 정의 + 개념 설명 |
| `POLICY` | "비밀번호 규정이 뭐야?" | 관련 정책 및 기준 설명 |

---

## 🔥 Trouble Shooting

### 1. AWS EC2 OOM — 메모리 부족으로 컨테이너 강제 종료

**문제**: t2.micro(RAM 1GB) 배포 후 첫 질문 시 컨테이너가 `Killed` 메시지와 함께 종료

**원인**: ChromaDB 로딩 + BM25Retriever 전체 문서 메모리 적재 + LangGraph 상태 객체가 동시에 올라가며 1GB 한계 초과

**해결**: EC2 인스턴스를 t2.micro → t2.large(RAM 8GB)로 업그레이드  
**교훈**: 로컬(16GB)과 서버(1GB)의 메모리 차이를 배포 전에 반드시 고려해야 함

---

### 2. 대시보드 사용자별 통계 미표시 — username NULL 저장

**문제**: ADMIN 대시보드의 "사용자별 질문 수"에 데이터가 표시되지 않음

**원인**: 로그인 기능 추가 후 `save_log()` 호출부에 `username` 인자를 전달하지 않아 전체 행이 NULL로 저장

```python
# 수정 전
save_log(question, answer, sources, question_type, is_valid, ...)

# 수정 후
save_log(..., username=current_user["username"])  # username 추가
```

**교훈**: 기능을 순차적으로 추가할 때 기존 연동 지점(함수 호출부)을 함께 업데이트해야 함

---

### 3. /ask 엔드포인트 ValueError — 검색 결과 0건 언패킹 오류

**문제**: 배포 환경에서 `/ask` 호출 시 `ValueError: not enough values to unpack (expected 3, got 0)` 발생

**원인**: EC2 환경에서 vectorstore 경로 불일치로 검색 결과 0건 반환 → 빈 튜플 언패킹 시도

**해결**:
```python
# 출처 없으면 답변 차단 (안전한 early return)
if not sources_text:
    return {
        "answer": "⚠️ 접근 가능한 문서에서 관련 내용을 찾을 수 없습니다.",
        "sources": "",
        ...
    }
```

---

## 📁 프로젝트 구조

```
security-rag/
├── backend/
│   ├── rag_chain.py      # LangGraph 핵심 — 분류→검색→생성→검증→재시도
│   ├── main.py           # FastAPI 서버 — API 엔드포인트, CORS, 로그 저장
│   ├── ingest.py         # PDF 전처리 — 청킹(500/50), 임베딩, ChromaDB 저장
│   ├── auth.py           # JWT 생성·검증, bcrypt 해시
│   ├── database.py       # PostgreSQL 연결, 로그 저장, 대시보드 쿼리
│   ├── data/             # KISA 보안 문서 PDF 원본
│   └── vectorstore/      # ChromaDB 영구 저장 (재시작 시 재임베딩 불필요)
├── frontend/
│   └── src/              # React — 챗봇 UI, 로그인, ADMIN 대시보드
├── docker-compose.yml    # 멀티 컨테이너 오케스트레이션
└── .env                  # API 키, JWT 시크릿, DB 정보 (Git 제외)
```

---

## 🚀 로컬 실행 방법

### 사전 준비
- Python 3.11+
- Node.js 18+
- PostgreSQL
- OpenAI API Key

### 백엔드 실행

```bash
# 가상환경 생성 및 활성화
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# 패키지 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일에 OPENAI_API_KEY, DB 정보 입력

# PDF 임베딩 (최초 1회)
python ingest.py

# 서버 실행
python main.py
# → http://localhost:8001
```

### 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### Docker로 실행 (권장)

```bash
docker compose up -d
# → http://localhost
```

---

## 🌐 배포 환경

| 항목 | 내용 |
|------|------|
| 서버 | AWS EC2 (t2.large, RAM 8GB) |
| OS | Ubuntu 22.04 |
| 컨테이너 | Docker Compose (백엔드 + 프론트엔드 + PostgreSQL) |
| 라이브 URL | http://3.26.94.252/ |

**테스트 계정**

| 권한 | 아이디 | 비밀번호 |
|------|--------|----------|
| 일반 직원 | employee1 | test1234 |
| 보안팀 | security1 | test1234 |
| 관리자 | admin1 | test1234 |

---

## 📚 사용 문서 (KISA 공식 자료)

| 문서명 | 권한 | 출처 |
|--------|------|------|
| 2019 패스워드 선택 및 이용 안내서 | EMPLOYEE | KISA |
| 개인정보 처리방침 작성지침(2025.4.) | EMPLOYEE | KISA |
| ISMS-P 인증제도 안내서(2024.07) | SECURITY | KISA |
| KISA 랜섬웨어 대응 가이드라인 | SECURITY | KISA |
| 클라우드서비스 보안인증제 안내서 | SECURITY | KISA |
| 주요정보통신기반시설 기술적 취약점 분석 평가 방법 | ADMIN | KISA |

---

## 💭 회고

**잘한 점**
- Self-Correction, 권한 관리, 대시보드까지 "운영 가능한 시스템" 수준으로 완성
- ChromaDB vs PostgreSQL 역할 분리, Hybrid Search 도입 등 기술 선택에 근거를 가짐
- 발생한 오류를 회피하지 않고 원인을 추적하여 해결

**아쉬운 점 / 개선 계획**
- BM25Retriever를 요청마다 초기화 → 서버 시작 시 1회 로딩으로 개선 예정 (메모리 효율화)
- Self-Correction PASS/FAIL 기준이 LLM 주관적 판단에 의존 → 객관적 평가 테스트셋 구축 계획
- 문서 업로드 자동화 미구현 → 관리자 UI에서 PDF 업로드 시 자동 재임베딩 기능 추가 예정

---

<div align="center">

**📬 문의**: GitHub Issues 또는 이메일로 연락 주세요

</div>
