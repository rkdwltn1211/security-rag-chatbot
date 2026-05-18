<div align="center">

# 🔐 기업 IT 보안 정책 AI 어시스턴트
### ISMS-P 문서 기반 Self-Correction RAG 시스템

**"단순히 RAG를 만든 것이 아니라, 답변의 환각(Hallucination)을 줄이기 위해 이중 검증 루프를 설계했습니다."**

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-4B8BBE?style=flat-square)](https://langchain-ai.github.io/langgraph/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6B35?style=flat-square)](https://www.trychroma.com)
[![React](https://img.shields.io/badge/React-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![AWS EC2](https://img.shields.io/badge/AWS_EC2-FF9900?style=flat-square&logo=amazonaws&logoColor=white)](https://aws.amazon.com)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com)

### 🌐 [라이브 데모 바로가기 →](http://3.26.94.252/)
`employee1 / test1234` · `security1 / test1234` · `admin1 / test1234`

</div>

---

## 📸 서비스 화면

<table>
  <tr>
    <td align="center" width="50%">
      <img src="docs/screenshots/login.png" alt="로그인" width="100%"/>
      <br/><sub><b>JWT 기반 로그인</b></sub>
    </td>
    <td align="center" width="50%">
      <img src="docs/screenshots/dashboard.png" alt="대시보드" width="100%"/>
      <br/><sub><b>ADMIN 전용 로그 분석 대시보드</b></sub>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%">
      <img src="docs/screenshots/chatbot_action.png" alt="ACTION 답변" width="100%"/>
      <br/><sub><b>ACTION 유형 — 단계별 절차 답변</b></sub>
    </td>
    <td align="center" width="50%">
      <img src="docs/screenshots/chatbot_security.png" alt="SECURITY 권한" width="100%"/>
      <br/><sub><b>SECURITY 권한 — 다중 문서 출처 표시</b></sub>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%">
      <img src="docs/screenshots/chatbot_blocked.png" alt="답변 차단" width="100%"/>
      <br/><sub><b>범위 외 질문 — 출처 없으면 답변 거부</b></sub>
    </td>
    <td align="center"></td>
  </tr>
</table>

> 📁 `docs/screenshots/` 폴더에 `login.png` · `dashboard.png` · `chatbot_action.png` · `chatbot_security.png` · `chatbot_blocked.png` 순서로 이미지를 추가하면 자동 표시됩니다.

---

## 🎯 핵심 차별화 포인트

| | 일반 RAG | **이 프로젝트** |
|---|---|---|
| **검색 방식** | 벡터 검색만 사용 | 벡터 + BM25 **Hybrid Search** |
| **검색 품질** | 결과 그대로 사용 | 문서 관련성 LLM 평가 후 **재검색** (최대 2회) |
| **답변 생성** | 1회 생성 후 반환 | 환각 검증(PASS/FAIL) 후 **자동 재생성** (최대 2회) |
| **출처 처리** | 출처 표시만 | 출처 없으면 **답변 자체 차단** |
| **접근 제어** | 없음 | **EMPLOYEE / SECURITY / ADMIN** 3단계 권한별 문서 분리 |
| **운영 관리** | 없음 | ADMIN 전용 **로그 분석 대시보드** |

---

## 🏗️ 시스템 아키텍처

```mermaid
graph TD
    A[사용자 React] -->|HTTP + JWT| B[FastAPI 백엔드]
    B --> C[LangGraph 워크플로우]
    B --> G[(PostgreSQL\n질문/답변 로그)]

    C --> D1[① categorize\n질문 유형 분류]
    D1 --> D2[② retrieve\nHybrid Search + 권한 필터]
    D2 --> D3[③ grade_docs\n문서 관련성 평가]
    D3 -->|IRRELEVANT 최대 2회| D2
    D3 -->|RELEVANT| D4[④ generate\n유형별 맞춤 답변 생성]
    D4 --> D5[⑤ check_hallucination\n환각 검증 PASS/FAIL]
    D5 -->|FAIL 최대 2회| D4
    D5 -->|PASS| E[최종 답변 반환]
    D2 <-->|권한 필터 검색| F[(ChromaDB\n벡터스토어)]
```

---

## ⚙️ 기술 스택

| 기술 | 선택 이유 |
|------|-----------|
| **LangGraph** | 검증 → 재시도 순환 루프를 그래프 구조로 명확하게 표현 |
| **ChromaDB + BM25** | 의미 검색(벡터) + 정확 검색(키워드) 병행으로 검색 누락 최소화 |
| **text-embedding-3-small** | 비용 효율적이면서 한국어 문서 처리 성능 검증 |
| **FastAPI** | 비동기 처리 + 자동 Swagger 문서 + Pydantic 타입 안전성 |
| **PostgreSQL** | 정형 로그 저장 및 대시보드 집계 쿼리 최적화 |
| **JWT (HS256)** | Stateless 토큰으로 권한(role) 정보 내장, 서버 세션 불필요 |
| **AWS EC2 + Docker** | 로컬-서버 환경 차이 제거(컨테이너화) + 클라우드 배포 일관성 |

---

## 🔑 핵심 구현 — Hybrid Search + Query Rewriting

일반 RAG와 가장 차별화되는 부분입니다. 벡터 검색과 BM25 키워드 검색을 병행하고, 권한 필터를 적용한 뒤 중복을 제거합니다. 재검색 시에는 LLM이 질문을 키워드 중심으로 자동 재작성(Query Rewriting)하여 검색 다양성을 확보합니다.

```python
# 권한 레벨에 따라 접근 가능한 문서 필터 동적 생성
accessible = [r for r, l in ROLE_LEVELS.items() if l <= user_level]
filter_dict = {"$or": [{"permission": p} for p in accessible]}

# 벡터 검색 + BM25 병행 후 중복 제거
vector_docs = vectorstore.similarity_search(question, k=k, filter=filter_dict)
bm25_docs   = bm25_retriever.invoke(question)

seen, combined = set(), []
for doc in vector_docs + bm25_docs:
    if doc.page_content not in seen:
        seen.add(doc.page_content)
        combined.append(doc)

# 재검색 시 질문 자동 재작성 + 검색 범위 확장 (k: 4 → 8 → 12)
if state["retrieve_count"] > 0:
    question = llm.invoke(rewrite_prompt).content.strip()
    k += 4
```

---

## 🔥 결과 및 Trouble Shooting

### TS #1 · AWS EC2 OOM — 메모리 부족으로 컨테이너 강제 종료

> **문제**: t2.micro(RAM 1GB) 배포 후 첫 질문 시 컨테이너가 `Killed`로 종료  
> **원인**: ChromaDB 로딩 + BM25 전체 문서 적재 + LangGraph 상태 객체가 동시에 메모리에 올라가며 1GB 초과  
> **해결**: t2.micro → **t2.large(RAM 8GB)** 업그레이드  
> **학습**: 로컬과 서버의 리소스 차이를 배포 전 반드시 고려해야 함. 근본 개선으로 BM25Retriever 싱글턴 패턴 적용 예정

---

### TS #2 · 대시보드 사용자 통계 미표시 — username NULL 저장

> **문제**: ADMIN 대시보드 "사용자별 질문 수"에 데이터 없음  
> **원인**: 로그인 기능 추가 후 `save_log()` 호출부에 `username` 인자 누락 → 전체 행 NULL 저장 → `GROUP BY username` 집계 불가

```python
# 수정 전 — username 누락
save_log(question, answer, sources, question_type, is_valid, ...)

# 수정 후 — username 추가
save_log(..., username=current_user["username"])
```

> **학습**: 기능을 순차적으로 추가할 때 기존 연동 지점(함수 호출부)을 함께 업데이트해야 함

---

## 📁 프로젝트 구조

```
security-rag/
├── backend/
│   ├── rag_chain.py   # LangGraph 핵심 — 분류→검색→생성→검증→재시도
│   ├── main.py        # FastAPI 서버 — 엔드포인트, CORS, 로그 저장
│   ├── ingest.py      # PDF 전처리 — 청킹(chunk 500/overlap 50), 임베딩
│   ├── auth.py        # JWT 생성·검증, bcrypt 해시
│   ├── database.py    # PostgreSQL 연결, 로그 저장, 대시보드 쿼리
│   ├── data/          # KISA 보안 문서 PDF 원본
│   └── vectorstore/   # ChromaDB 영구 저장
├── frontend/src/      # React — 챗봇 UI, 로그인, ADMIN 대시보드
├── docker-compose.yml
└── .env               # API 키, JWT 시크릿, DB 정보 (Git 제외)
```

---

## 🚀 실행 방법

**Docker (권장)**
```bash
docker compose up -d
# → http://localhost
```

**로컬 실행**
```bash
# 백엔드
cd backend && pip install -r requirements.txt
python ingest.py   # PDF 임베딩 (최초 1회)
python main.py     # → http://localhost:8001

# 프론트엔드
cd frontend && npm install && npm run dev
# → http://localhost:5173
```

---

<div align="center">

**📬 문의는 GitHub Issues로 남겨주세요**

</div>
