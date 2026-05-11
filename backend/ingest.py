import os
from dotenv import load_dotenv
import fitz
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

load_dotenv()
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 문서별 권한 설정
DOC_PERMISSIONS = {
    "2019_패스워드_선택_및_이용_안내서.pdf": "EMPLOYEE",
    "★개인정보 처리방침 작성지침(2025.4.).pdf": "EMPLOYEE",
    "ISMS-P 인증제도 안내서(2024.07).pdf": "SECURITY",
    "230803-KISA-보도자료(KISA, 랜섬웨어 대응을 위한 가이드라인 개정본 배포).pdf": "SECURITY",
    "[KISA]클라우드서비스_보안인증제_안내서(2020.11).pdf": "SECURITY",
    "주요정보통신기반시설_기술적_취약점_분석_평가_방법_상세가이드.pdf": "ADMIN",
}

# 권한 레벨 정의
ROLE_LEVELS = {
    "EMPLOYEE": 1,
    "SECURITY": 2,
    "ADMIN": 3
}

def load_pdfs(data_folder="data"):
    docs = []
    for filename in os.listdir(data_folder):
        if filename.endswith(".pdf"):
            filepath = os.path.join(data_folder, filename)
            pdf = fitz.open(filepath)
            permission = DOC_PERMISSIONS.get(filename, "EMPLOYEE")
            for page_num, page in enumerate(pdf, start=1):
                text = page.get_text()
                if text.strip():
                    docs.append({
                        "text": text,
                        "source": filename,
                        "page": page_num,
                        "permission": permission  # 권한 메타데이터 추가
                    })
            print(f"✅ {filename} 로드 완료 ({len(pdf)}페이지) - 권한: {permission}")
    return docs

def split_docs(docs):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )
    chunks = []
    for doc in docs:
        splits = splitter.split_text(doc["text"])
        for split in splits:
            chunks.append({
                "text": split,
                "source": doc["source"],
                "page": doc["page"],
                "permission": doc["permission"]  # 권한 유지
            })
    print(f"✅ 총 {len(chunks)}개 청크 생성 완료")
    return chunks

def save_to_vectorstore(chunks):
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    texts = [c["text"] for c in chunks]
    metadatas = [
        {
            "source": c["source"],
            "page": c["page"],
            "permission": c["permission"]  # 권한 메타데이터 저장
        }
        for c in chunks
    ]
    vectorstore = Chroma.from_texts(
        texts=texts,
        embedding=embeddings,
        metadatas=metadatas,
        persist_directory="vectorstore"
    )
    print(f"✅ ChromaDB 저장 완료!")
    return vectorstore

if __name__ == "__main__":
    print("📄 PDF 로딩 중...")
    docs = load_pdfs()

    print("✂️ 텍스트 청크 분할 중...")
    chunks = split_docs(docs)

    print("💾 Vector DB 저장 중...")
    save_to_vectorstore(chunks)

    print("🎉 모든 작업 완료!")