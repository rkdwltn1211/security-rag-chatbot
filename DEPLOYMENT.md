# 로컬 개발과 운영 배포

## 설정 분리

- `.env.example`: 로컬 개발용. 기존 루트 `.env`를 계속 사용하며 실제 파일은 변경하지 않았습니다.
- `.env.production.example`: 운영 서버 환경변수 참고용. 실제 값은 호스팅 서비스의 비밀 환경변수 설정에 입력합니다. 예제 파일을 그대로 배포하지 않습니다.
- 서버 프로세스에 `APP_ENV=production`을 먼저 설정하면 루트 `.env`를 자동 로드하지 않습니다. 환경변수가 로컬 파일 값보다 우선합니다.
- `SECRET_KEY`는 코드 기본값이 없으며 누락/공백이면 시작되지 않습니다. 배포 전에 새 암호학적 난수로 발급하고 비밀 설정에 입력합니다. 이전 공개 기본값을 재사용하지 않습니다. `python -c "import secrets; print(secrets.token_urlsafe(48))"`를 개인 터미널에서 실행할 수 있습니다. 결과는 Git/로그/프론트에 넣지 않습니다.
- 운영 DB에는 새 강한 비밀번호와 제공자의 TLS 연결 설정을 사용합니다. `DB_SSLMODE` 기본값은 운영 `require`, 로컬 `prefer`입니다. 공급자가 인증서 검증 구성을 제공하면 `verify-full`을 사용하세요.
- `docker-compose.yml`은 로컬 전용입니다. DB_HOST=db, 포트 8001, 프론트 개발 모드 빌드를 사용합니다. 이 파일을 그대로 공개 운영용으로 사용하지 않습니다.

| 변수 | 로컬 | 운영 |
|---|---|---|
| APP_ENV | development | production |
| SECRET_KEY / OPENAI_API_KEY / DB_PASSWORD | 개인 .env | 백엔드 호스트 비밀 변수 |
| DB_HOST | localhost (Compose: db) | 제공자가 발급한 PostgreSQL 호스트 |
| DB_SSLMODE | prefer | require 또는 제공자의 verify-full 설정 |
| CORS_ORIGINS | http://localhost:5173 등 | https://실제-프론트-도메인 (쉼표로 추가) |
| CHROMA_DIR | backend 기준 vectorstore | /tmp/security-rag-chroma |
| CHROMA_RESTORE_FROM_DB | false | true |
| VITE_API_URL | http://localhost:8001 | https://실제-백엔드-도메인 |

CORS는 경로나 `*`를 받지 않습니다. 운영은 HTTPS origin만 허용합니다. 미리보기 도메인도 필요할 때 정확한 도메인을 추가합니다. CORS는 인증을 대체하지 않습니다.

## 프론트 빌드

호스팅 root directory는 `frontend`, build command는 `npm ci && npm run build`, output은 `dist`입니다. Node 24를 사용합니다. `VITE_API_URL`은 빌드 시점에 주입되는 공개 값이며 변경 후 재빌드해야 합니다. 모든 비밀은 백엔드에만 둡니다.

운영 빌드는 API 주소 누락 및 HTTP 주소(localhost 포함)를 거부합니다. 로컬 정적 빌드가 필요하면 `npm run build -- --mode development`를 사용합니다. Docker도 기본 빌드는 production이고, 로컬 Compose만 BUILD_MODE=development를 전달합니다. 운영에서는 `npm run dev`나 `vite preview`를 공개하지 않고 dist 정적 파일만 제공합니다.

## Chroma 재시작 복구

현재처럼 운영 중 문서를 업로드하지 않는 고정 문서 모음은 PostgreSQL에 압축 스냅샷 한 개를 보관하는 방식으로 충분합니다. 별도 Chroma 서버나 객체 저장소가 필요하지 않습니다.

1. 로컬에서 OCR/ingest가 완료된 후 `backend`에서 `python chroma_snapshot.py export corpus.snapshot.json.gz` 실행.
2. 배포를 승인한 뒤, 운영 PostgreSQL 접속 환경변수가 설정된 운영자 터미널에서 `python chroma_snapshot.py publish corpus.snapshot.json.gz` 실행. 이 명령은 해당 DB의 `rag_snapshot` 한 행만 생성/교체합니다. 이번 작업에서는 외부 DB에 실행하지 않았습니다.
3. 백엔드에 CHROMA_RESTORE_FROM_DB=true 및 CHROMA_DIR를 설정하고 시작합니다. 스냅샷이 없거나 손상되면 시작을 실패시킵니다.
4. 서버가 빈 디스크로 재시작하면 ID·텍스트·출처·페이지·권한·기존 1536차원 임베딩을 Chroma에 복원합니다. OCR/임베딩 API를 재호출하지 않습니다. 중단된 복원도 같은 ID로 재시도합니다.
5. 문서 변경 시 로컬 ingest → 새 스냅샷 export/publish → 새 빈 CHROMA_DIR로 서버 재시작 순서로 갱신합니다. 기존 검색 데이터를 조용히 덮어쓰지 않습니다. 운영 인스턴스는 단일 worker로 실행합니다.

스냅샷은 문서 원문을 포함하므로 비공개로 보관합니다. `.gitignore`와 `.dockerignore`에서 제외했습니다. 이것은 PostgreSQL 자체 백업을 대체하지 않습니다. 운영 중 새로 만든 Chroma 데이터는 자동 역동기화하지 않으며 publish하지 않은 변경은 재시작 후 유지되지 않습니다.

실제 2,225개 청크(패스워드 PDF 10개) 스냅샷은 15,552,618 bytes, 약 14.83 MiB였습니다. 빈 Chroma 복원·중복 없는 재복원 및 OCR 벡터 검색 결과/출처 일치를 확인했습니다. 매 부팅 시 약 15.6 MB 다운로드가 발생하므로 DB 전송량 한도에 포함됩니다.

## 무료 후보와 권장 조합 (2026-09-12 확인)

| 구성 | 추천 | 제한/대안 |
|---|---|---|
| 프론트 | Cloudflare Pages Free | dist 정적 배포. Render Static Site도 대안 |
| 백엔드 | Render Free Web Service, 공개 데모에 한정 | Python 3.12, 단일 worker. 512 MB 메모리에서 실제 복원/RAG 부하 검증 필요. 15분 유휴 후 중지·콜드스타트·월 사용량 제한 |
| PostgreSQL | Neon Free | 사용자/로그 및 rag_snapshot. 프로젝트당 0.5 GB, 100 CU-hours, 월 공개 전송량 5 GB 한도 확인 필요 |
| Chroma | Render 백엔드 내부 임시 디스크 | 원본 스냅샷은 Neon에 저장하고 매 시작 복원. 별도 무료 영구 디스크라고 간주하지 않음 |

Render는 무료 인스턴스를 운영 서비스용으로 권장하지 않습니다. 상시 운영이나 메모리 부족 시 백엔드는 유료 인스턴스로 전환해야 합니다. Render 무료 PostgreSQL은 30일 만료이므로 장기 보관용으로 추천하지 않습니다. Hugging Face Spaces는 현재 문서상 Docker/Gradio Space 생성에 유료 플랜이 필요하므로 완전 무료 백엔드 추천에서 제외했습니다.

Render native 배포: root `backend`, build `pip install -r requirements.txt`, start `uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1`. 호스팅 Python 버전은 로컬과 같은 3.12로 지정합니다. 운영은 복원된 임베딩으로 검색하므로 ingest/setup_ocr를 시작 명령에 넣지 않습니다. 실제 Docker/Linux 빌드는 아직 검증하지 않았습니다.

호스팅 무료 한도와 별개로 현재 OpenAI 질문 API 사용료는 발생합니다. API 비용 제한과 공개 요청 제한은 별도로 준비해야 합니다.

공식 근거: [Cloudflare Pages 제한](https://developers.cloudflare.com/pages/platform/limits/), [Vite 배포](https://developers.cloudflare.com/pages/framework-guides/deploy-a-vite3-project/), [Render 무료 제한](https://render.com/docs/free), [Render 메모리](https://render.com/docs/compute-plans), [Neon 무료 플랜](https://neon.com/faqs/postgres-services-free-to-production), [Spaces 조건](https://huggingface.co/docs/hub/spaces-overview).

## npm 취약점 구분

이번 audit은 총 7개 패키지: high 5, moderate 1, low 1. `npm audit --omit=dev`는 0건입니다. 업데이트 또는 audit fix/--force는 실행하지 않았습니다.

| 패키지 | 심각도 | 현재 정적 배포에서의 판단 |
|---|---|---|
| vite | high | 개발 서버의 파일 노출. 외부 공개 전에 패치 또는 개발 서버 외부 노출 제거 필수. dist만 배포하면 런타임 공격 경로 없음 |
| postcss | high | 공격자 CSS/source map을 빌드하면 파일 노출. 신뢰할 수 없는 입력을 받는 빌드 전에 수정 필수 |
| @babel/core | low | 공격자 sourceMappingURL을 처리하는 빌드 전 수정 필요 |
| brace-expansion | high | 공격자 패턴을 처리할 때 DoS. 현재 고정 소스의 빌드/검사 도구 경로에서는 조건부 보류 |
| browserslist | high | 공격자 쿼리/stats 입력에서 메모리 고갈·오류. 현재 고정 빌드 설정에서는 조건부 보류 |
| nanoid | high | 비정상 크기 입력 관련 문제. 현재 앱이 직접 호출하지 않는 빌드 의존성이므로 조건부 보류 |
| baseline-browser-mapping | moderate | 비정상 입력의 프로세스 종료. 현재 빌드 도구 사용 범위에서는 조건부 보류 |

현재 추천 구성(신뢰된 소스로 빌드한 dist만 공개)에서 이번 npm 결과만으로 확인된 운영 런타임 차단 취약점은 없습니다. devDependency라는 이유만으로 안전하다는 뜻은 아닙니다. 외부 PR을 비밀이 있는 빌드 환경에서 실행하거나 개발 서버를 공개하면 위 조건부 보류 판단을 적용할 수 없습니다. 정상 범위 업데이트는 별도 검증 후 진행하세요. Vite Windows 파일 노출 문제는 [공식 권고](https://github.com/vitejs/vite/security/advisories/GHSA-fx2h-pf6j-xcff)를 참고하세요.
