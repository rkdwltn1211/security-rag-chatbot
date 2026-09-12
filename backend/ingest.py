import os
import hashlib
import json
from collections import Counter
from pathlib import Path
from settings import chroma_directory
import pymupdf
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

BACKEND_DIR = Path(__file__).resolve().parent
os.chdir(BACKEND_DIR)

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

OCR_TESSDATA = Path(os.getenv('TESSDATA_PREFIX', str(BACKEND_DIR / '.tessdata')))


def extract_page_text(page, min_text_chars=40, tessdata=OCR_TESSDATA):
    """Keep native text; OCR only sparse pages containing scanned/outlined content."""
    text = page.get_text()
    if len(''.join(text.split())) >= min_text_chars:
        return text, False
    if not page.get_images() and not page.get_drawings():
        return text, False  # Blank pages and short text-only titles need no OCR.
    if not all((Path(tessdata) / f'{lang}.traineddata').is_file() for lang in ('kor', 'eng')):
        raise RuntimeError('OCR 언어 데이터가 없습니다. python setup_ocr.py를 먼저 실행하세요.')
    textpage = page.get_textpage_ocr(language='kor+eng', dpi=300, full=True, tessdata=str(tessdata))
    ocr_text = page.get_text(textpage=textpage)
    # Never replace useful native text with an empty or poorer OCR result.
    if len(''.join(ocr_text.split())) > len(''.join(text.split())):
        text = ocr_text
    return text, True


def load_pdfs(data_folder="data"):
    docs = []
    for filename in os.listdir(data_folder):
        if filename.endswith(".pdf"):
            filepath = os.path.join(data_folder, filename)
            permission = DOC_PERMISSIONS.get(filename, "EMPLOYEE")
            ocr_pages = 0
            with pymupdf.open(filepath) as pdf:
                for page_num, page in enumerate(pdf, start=1):
                    text, used_ocr = extract_page_text(page)
                    if used_ocr:
                        ocr_pages += 1
                        print(f"🔎 OCR {filename} p.{page_num}", flush=True)
                    if text.strip():
                        docs.append({
                            "text": text,
                            "source": filename,
                            "page": page_num,
                            "permission": permission
                        })
                print(f"✅ {filename} 로드 완료 ({len(pdf)}페이지, OCR {ocr_pages}페이지) - 권한: {permission}", flush=True)
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

def save_to_vectorstore(chunks, persist_directory=None):
    persist_directory = persist_directory or chroma_directory()
    if not chunks:
        raise ValueError('추출한 청크가 없어 기존 검색 데이터를 유지합니다.')
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
    vectorstore = Chroma(embedding_function=embeddings, persist_directory=persist_directory)
    sources = sorted({c['source'] for c in chunks})
    previous_ids = set(vectorstore.get(where={'source': {'$in': sources}}, include=[])['ids'])
    occurrences = Counter()
    ids = []
    for chunk in chunks:
        key = (chunk['source'], chunk['page'], chunk['permission'], chunk['text'])
        occurrence = occurrences[key]
        occurrences[key] += 1
        ids.append(hashlib.sha256(json.dumps([*key, occurrence], ensure_ascii=False).encode('utf-8')).hexdigest())
    pending = [i for i, chunk_id in enumerate(ids) if chunk_id not in previous_ids]
    for start in range(0, len(pending), 128):
        batch = pending[start:start + 128]
        vectorstore.add_texts(texts=[texts[i] for i in batch], metadatas=[metadatas[i] for i in batch], ids=[ids[i] for i in batch])
        print(f"💾 임베딩 저장 {min(start + 128, len(pending))}/{len(pending)}", flush=True)
    # Remove superseded chunks only after every new batch has been stored successfully.
    stale_ids = sorted(previous_ids - set(ids))
    for start in range(0, len(stale_ids), 128):
        vectorstore.delete(ids=stale_ids[start:start + 128])
    print(f"✅ ChromaDB 저장 완료!")
    return vectorstore

if __name__ == "__main__":
    print("📄 PDF 로딩 중...")
    docs = load_pdfs()

    print("✂️ 텍스트 청크 분할 중...")
    chunks = split_docs(docs)
    print(f"문서별 청크 수: {dict(Counter(c['source'] for c in chunks))}", flush=True)

    print("💾 Vector DB 저장 중...")
    save_to_vectorstore(chunks)

    print("🎉 모든 작업 완료!")
