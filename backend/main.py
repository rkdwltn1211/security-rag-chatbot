from fastapi import FastAPI, HTTPException, Depends
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from rag_chain import ask
from database import get_db_connection, create_users_table, create_user, save_log, get_user
from auth import hash_password, verify_password, create_access_token, get_current_user
import uvicorn

# 서버 시작 시 테이블 생성
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_users_table()
    print("✅ 서버 시작 완료")
    yield


app = FastAPI(
    title="IT 보안 정책 RAG API",
    description="Self-Correction RAG 기반 IT 보안 정책 QA 시스템",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173",
                   "http://localhost",  # Docker 컨테이너에서 접근할 
                   "http://localhost:80"], # Docker 컨테이너에서 접근할 때
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 요청/응답 모델
class QuestionRequest(BaseModel):
    question: str

class AnswerResponse(BaseModel):
    question: str
    answer: str
    sources: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "EMPLOYEE"

# 헬스체크
@app.get("/")
def health_check():
    return {"status": "ok", "message": "IT 보안 정책 RAG API 작동 중"}

# 회원가입
@app.post("/register")
def register(request: RegisterRequest):
    existing = get_user(request.username)
    if existing:
        raise HTTPException(status_code=400, detail="이미 존재하는 아이디입니다.")
    hashed = hash_password(request.password)
    create_user(request.username, hashed, request.role)
    return {"message": f"{request.username} 회원가입 완료!"}

# 로그인
@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 틀렸습니다.")
    token = create_access_token({"sub": user["username"], "role": user["role"]})
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}

# 내 정보 조회
@app.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {"username": current_user["username"], "role": current_user["role"]}

# 질문 API (로그인 필요)
@app.post("/ask", response_model=AnswerResponse)
def ask_question(request: QuestionRequest, current_user: dict = Depends(get_current_user)):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="질문을 입력해주세요")

    try:
        result = ask(request.question, user_role=current_user["role"])
        answer = result["answer"]
        sources = result["sources"]
        question_type = result["question_type"]
        is_valid = result["is_valid"]
        retry_count = result["retry_count"]
        retrieve_count = result["retrieve_count"]

        save_log(
            question=request.question,
            answer=answer,
            sources=sources,
            question_type=question_type,
            is_valid=is_valid,
            retry_count=retry_count,
            retrieve_count=retrieve_count,
            username=current_user["username"]
        )

        return AnswerResponse(
            question=request.question,
            answer=answer,
            sources=sources
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 로그 조회 (로그인 필요)
@app.get("/logs")
def get_logs(current_user: dict = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, question, answer, sources, created_at
            FROM chat_logs
            ORDER BY created_at DESC
            LIMIT 20
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [
            {
                "id": row[0],
                "question": row[1],
                "answer": row[2],
                "sources": row[3],
                "created_at": str(row[4])
            }
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 대시보드 API (ADMIN만 접근 가능)
@app.get("/dashboard")
def get_dashboard(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="ADMIN 권한이 필요합니다.")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 총 질문 수
        cur.execute("SELECT COUNT(*) FROM chat_logs")
        total = cur.fetchone()[0]

        # PASS/FAIL 비율
        cur.execute("SELECT is_valid, COUNT(*) FROM chat_logs GROUP BY is_valid")
        valid_rows = cur.fetchall()
        pass_count = sum(r[1] for r in valid_rows if r[0] == True)
        fail_count = sum(r[1] for r in valid_rows if r[0] == False)

        # 질문 유형별 통계
        cur.execute("SELECT question_type, COUNT(*) FROM chat_logs GROUP BY question_type")
        type_rows = cur.fetchall()
        type_stats = {r[0]: r[1] for r in type_rows if r[0]}

        # 사용자별 질문 수 (상위 5명)
        cur.execute("""
            SELECT username, COUNT(*) as cnt 
            FROM chat_logs 
            WHERE username IS NOT NULL
            GROUP BY username 
            ORDER BY cnt DESC 
            LIMIT 5
        """)
        user_rows = cur.fetchall()
        user_stats = [{"username": r[0], "count": r[1]} for r in user_rows]

        # 최근 질문 10개
        cur.execute("""
            SELECT question, is_valid, question_type, created_at 
            FROM chat_logs 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        recent_rows = cur.fetchall()
        recent_logs = [
            {
                "question": r[0],
                "is_valid": r[1],
                "question_type": r[2],
                "created_at": str(r[3])
            }
            for r in recent_rows
        ]

        cur.close()
        conn.close()

        return {
            "total": total,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "type_stats": type_stats,
            "user_stats": user_stats,
            "recent_logs": recent_logs
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))





if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)