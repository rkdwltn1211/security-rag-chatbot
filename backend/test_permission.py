import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

load_dotenv()
os.chdir(os.path.dirname(os.path.abspath(__file__)))

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma(persist_directory="vectorstore", embedding_function=embeddings)

result = vectorstore.get()

# 권한별 개수 세기
from collections import Counter
permissions = [m.get("permission", "없음") for m in result["metadatas"]]
counter = Counter(permissions)
print("권한별 청크 개수:", counter)

# EMPLOYEE 권한 문서 샘플 확인
employee_docs = [m for m in result["metadatas"] if m.get("permission") == "EMPLOYEE"]
print(f"\nEMPLOYEE 문서 수: {len(employee_docs)}")
if employee_docs:
    print("샘플:", employee_docs[0])