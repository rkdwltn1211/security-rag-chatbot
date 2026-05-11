import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END
from typing import TypedDict
from langchain_core.documents import Document

load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

os.chdir(os.path.dirname(os.path.abspath(__file__)))


# 상태 정의
class GraphState(TypedDict):
    question: str
    question_type: str
    context: str
    answer: str
    is_valid: bool
    is_relevant: bool
    retry_count: int
    retrieve_count: int
    sources: list        # 출처 페이지 번호 저장
    user_role: str      # 사용자 권한 레벨 (예: EMPLOYEE, SECURITY, ADMIN)

# 벡터스토어 + 전체 문서 불러오기
def load_vectorstore():
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = Chroma(
        persist_directory="vectorstore",
        embedding_function=embeddings
    )
    return vectorstore

def load_all_docs():
    vectorstore = load_vectorstore()
    result = vectorstore.get()
    texts = result["documents"]
    metadatas = result["metadatas"]
    ids = result["ids"]
    return texts, metadatas, ids

# 노드 1. 질문 유형 분류 (Categorize)
def categorize(state: GraphState) -> GraphState:
    print("🏷️ 질문 유형 분류 중...")
    prompt = PromptTemplate.from_template("""
아래 질문이 어떤 유형인지 분류하세요.
반드시 아래 셋 중 하나만 정확히 답하세요.

POLICY: 규정, 기준, 정책을 묻는 질문
예) "비밀번호 규정이 뭐야?", "개인정보 보관 기간은?", "전화번호 뭐야?"

ACTION: 문제 해결, 조치 방법, 대응 절차를 묻는 질문
예) "해킹 당했을 때 어떻게 해?", "랜섬웨어 감염 시 대응 방법은?"

DEFINITION: 용어나 개념의 정의를 묻는 질문
예) "ISMS-P가 뭐야?", "개인정보란 무엇인가요?"

[질문]
{question}

[유형]
""")
    chain = prompt | llm
    result = chain.invoke({"question": state["question"]})
    judge = result.content.strip().upper()

    if judge in ["ACTION", "POLICY", "DEFINITION"]:
        question_type = judge
    else:
        print(f"⚠️ 분류 실패: {judge}")
        question_type = "POLICY"  # 안전 fallback
    
    print(f"질문 유형: {question_type}")
    return {**state, "question_type": question_type}

# 노드 2. 문서 검색 (Hybrid Search: 벡터 + 키워드)
def retrieve(state: GraphState) -> GraphState:
    print("📄 문서 검색 중...")

    k = 4 + (state["retrieve_count"] * 4)
    user_role = state.get("user_role", "EMPLOYEE")


    # 권한 레벨
    ROLE_LEVELS = {"EMPLOYEE": 1, "SECURITY": 2, "ADMIN": 3}
    user_level = ROLE_LEVELS.get(user_role, 1) 


    question = state["question"]
    if state["retrieve_count"] > 0:
        print("✏️ 질문 재작성 중...")
        rewrite_prompt = PromptTemplate.from_template("""
아래 질문을 문서 검색에 더 적합한 키워드 중심으로 재작성하세요.
간결하게 핵심 키워드만 남겨주세요.

[원래 질문]
{question}

[재작성된 질문]
""")
        rewrite_chain = rewrite_prompt | llm
        rewritten = rewrite_chain.invoke({"question": state["question"]})
        question = rewritten.content.strip()
        print(f"재작성된 질문: {question}")

    # 벡터 검색
    vectorstore = load_vectorstore()
    # 변경 - 권한 레벨에 따라 접근 가능한 permission 목록 만들기
    accessible_permissions = [
        role for role, level in ROLE_LEVELS.items()
        if level <= user_level
    ]

    # EMPLOYEE면 ["EMPLOYEE"]
    # SECURITY면 ["EMPLOYEE", "SECURITY"]
    # ADMIN이면 ["EMPLOYEE", "SECURITY", "ADMIN"]
    if len(accessible_permissions) == 1:
        filter_dict = {"permission": accessible_permissions[0]}
    else:
        filter_dict = {"$or": [{"permission": p} for p in accessible_permissions]}

    vector_docs = vectorstore.similarity_search(
        question,
        k=k,
        filter=filter_dict
    )






    # 키워드 검색 (BM25)
    from langchain_core.documents import Document
    texts, metadatas, ids = load_all_docs()
    bm25_docs_input = [
        Document(page_content=t, metadata=m)
        for t, m, i in zip(texts, metadatas, ids)
        if m.get("permission", "EMPLOYEE") in accessible_permissions
    ]
    bm25_retriever = BM25Retriever.from_documents(bm25_docs_input)
    bm25_retriever.k = k
    bm25_docs_result = bm25_retriever.invoke(question)

    # Hybrid: 벡터 + 키워드 합치고 중복 제거
    seen = set()
    combined = []
    for doc in vector_docs + bm25_docs_result:
        if doc.page_content not in seen:
            seen.add(doc.page_content)
            combined.append(doc)

    # 출처 페이지 번호 수집
    sources = []
    for doc in combined:
        source = doc.metadata.get("source", "알 수 없음")
        page = doc.metadata.get("page", "?")
        entry = {"source": source, "page": page}
        if entry not in sources:
            sources.append(entry)

    context = "\n\n".join([doc.page_content for doc in combined])
    return {**state, "context": context, "sources": sources}

# 노드 3. 문서 관련성 검증 (Grade_Docs)
def grade_docs(state: GraphState) -> GraphState:
    print("📊 문서 관련성 검증 중...")
    prompt = PromptTemplate.from_template("""
아래 문서 내용이 질문에 답하기에 충분한 정보를 담고 있는지 판단하세요.
반드시 아래 둘 중 하나만 정확히 답하세요.

RELEVANT
IRRELEVANT

[질문]
{question}

[문서 내용]
{context}

[판단]
""")
    chain = prompt | llm
    result = chain.invoke({
        "question": state["question"],
        "context": state["context"]
    })
    judge = result.content.strip().upper()
    is_relevant = "RELEVANT" in judge and "IRRELEVANT" not in judge
    print(f"문서 관련성: {'✅ 관련 있음' if is_relevant else '❌ 관련 없음'}")
    return {**state, "is_relevant": is_relevant}

# 노드 4. 답변 생성 (Generate)
def generate(state: GraphState) -> GraphState:
    print("✍️ 답변 생성 중...")

    if state["question_type"] == "ACTION":
        instruction = "단계별로 구체적인 조치 방법을 설명하세요."
    elif state["question_type"] == "DEFINITION":
        instruction = "용어의 정의와 개념을 명확하게 설명하세요."
    else:
        instruction = "관련 정책과 기준을 정확하게 설명하세요."

    prompt = PromptTemplate.from_template("""
당신은 기업 IT 보안 정책 전문가입니다.
아래 문서 내용을 바탕으로 질문에 답변하세요.
문서에 없는 내용은 절대 추측하지 마세요.
{instruction}

[문서 내용]
{context}

[질문]
{question}

[답변]
""")
    chain = prompt | llm
    answer = chain.invoke({
        "context": state["context"],
        "question": state["question"],
        "instruction": instruction
    })
    return {**state, "answer": answer.content}

# 노드 5. 환각 검증 (Check_Hallucination)
def check_hallucination(state: GraphState) -> GraphState:
    print("🔍 답변 검증 중...")
    prompt = PromptTemplate.from_template("""
아래 답변이 문서 내용에만 근거하는지 검증하세요.
반드시 아래 둘 중 하나만 정확히 답하세요.

PASS
FAIL

[문서 내용]
{context}

[답변]
{answer}

[검증 결과]
""")
    chain = prompt | llm
    result = chain.invoke({
        "context": state["context"],
        "answer": state["answer"]
    })
    judge = result.content.strip().upper()
    is_valid = "PASS" in judge and "FAIL" not in judge
    print(f"검증 결과: {'✅ PASS' if is_valid else '❌ FAIL'}")
    return {**state, "is_valid": is_valid}

# 분기 1. 문서 관련성 분기
def check_relevance(state: GraphState) -> str:
    if state["is_relevant"]:
        return "relevant"
    elif state["retrieve_count"] >= 2:
        print("⚠️ 재검색 한계 도달. 답변 생성으로 진행.")
        return "relevant"
    else:
        print(f"🔄 재검색 시도 ({state['retrieve_count'] + 1}회)")
        return "irrelevant"

# 분기 2. 환각 검증 분기
def should_retry(state: GraphState) -> str:
    if state["is_valid"]:
        return "end"
    elif state["retry_count"] >= 2:
        print("⚠️ 최대 재시도 횟수 초과.")
        return "end"
    else:
        print(f"🔄 답변 재생성 ({state['retry_count'] + 1}회)")
        return "retry"

# 카운트 증가 노드
def increment_retrieve(state: GraphState) -> GraphState:
    return {**state, "retrieve_count": state["retrieve_count"] + 1}

def increment_retry(state: GraphState) -> GraphState:
    return {**state, "retry_count": state["retry_count"] + 1}

# LangGraph 워크플로우 구성
def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("categorize", categorize)
    graph.add_node("retrieve", retrieve)
    graph.add_node("grade_docs", grade_docs)
    graph.add_node("generate", generate)
    graph.add_node("check_hallucination", check_hallucination)
    graph.add_node("increment_retrieve", increment_retrieve)
    graph.add_node("increment_retry", increment_retry)

    graph.set_entry_point("categorize")
    graph.add_edge("categorize", "retrieve")
    graph.add_edge("retrieve", "grade_docs")
    graph.add_conditional_edges(
        "grade_docs",
        check_relevance,
        {
            "relevant": "generate",
            "irrelevant": "increment_retrieve"
        }
    )
    graph.add_edge("increment_retrieve", "retrieve")
    graph.add_edge("generate", "check_hallucination")
    graph.add_conditional_edges(
        "check_hallucination",
        should_retry,
        {
            "end": END,
            "retry": "increment_retry"
        }
    )
    graph.add_edge("increment_retry", "generate")

    return graph.compile()

# 출처 포맷 함수
def format_sources(sources: list) -> str:
    if not sources:
        return ""
    source_lines = []
    grouped = {}
    for s in sources:
        name = s["source"]
        page = s["page"]
        if name not in grouped:
            grouped[name] = []
        grouped[name].append(str(page))
    for name, pages in grouped.items():
        source_lines.append(f"📄 {name} | p.{', p.'.join(pages)}")
    return "\n".join(source_lines)

# 실행 함수
def ask(question: str, user_role: str = "EMPLOYEE") -> dict:
    app = build_graph()
    result = app.invoke({
        "question": question,
        "question_type": "",
        "context": "",
        "answer": "",
        "is_valid": False,
        "is_relevant": False,
        "retry_count": 0,
        "retrieve_count": 0,
        "sources": [],
        "user_role": user_role
    })
    sources_text = format_sources(result["sources"])

    # 출처가 없으면 답변 차단
    if not sources_text:
        return {
            "answer": "⚠️ 접근 가능한 문서에서 관련 내용을 찾을 수 없습니다. 해당 내용은 더 높은 권한이 필요하거나 보유한 문서에 없는 내용입니다.",
            "sources": "",
            "question_type": result["question_type"],
            "is_valid": False,
            "is_relevant": False,
            "retry_count": result["retry_count"],
            "retrieve_count": result["retrieve_count"]
        }

    return {
        "answer": result["answer"],
        "sources": sources_text,
        "question_type": result["question_type"],
        "is_valid": result["is_valid"],
        "is_relevant": result["is_relevant"],
        "retry_count": result["retry_count"],
        "retrieve_count": result["retrieve_count"]
    }

# 테스트
if __name__ == "__main__":
    question = "오늘 점심이 뭘까?" 
    print(f"\n질문: {question}\n")
    result = ask(question)
    print(f"\n최종 답변:\n{result['answer']}")
    print(f"\n📚 출처:\n{result['sources']}")