#!/usr/bin/env python3
"""
ChromaDB에 CSV 템플릿 데이터 업로드 스크립트
"""
import os
import pandas as pd
import chromadb
from chromadb.config import Settings

def main():
    print("🚀 ChromaDB 템플릿 데이터 업로드 시작...")
    
    # 1. CSV 파일 읽기
    csv_path = 'src/_data/data.csv'
    if not os.path.exists(csv_path):
        print(f"❌ CSV 파일을 찾을 수 없습니다: {csv_path}")
        return False
    
    df = pd.read_csv(csv_path)
    print(f"📊 CSV 데이터 로드 완료: {len(df)}개 템플릿")
    
    # 2. ChromaDB 클라이언트 연결 (K8s 내부 서비스)
    try:
        client = chromadb.HttpClient(
            host='localhost',
            port=8000
        )
        print("✅ ChromaDB 연결 성공")
    except Exception as e:
        print(f"❌ ChromaDB 연결 실패: {e}")
        return False
    
    # 3. 기존 컬렉션 목록 확인
    try:
        existing_collections = client.list_collections()
        print(f"📋 기존 컬렉션: {[c.name for c in existing_collections]}")
    except Exception as e:
        print(f"⚠️ 컬렉션 목록 조회 실패: {e}")
    
    # 4. 새 컬렉션 생성 (기존 데이터와 완전히 분리)
    collection_name = "product_templates"
    try:
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Product detail page templates for similarity search"}
        )
        print(f"✅ 컬렉션 생성/연결 성공: {collection_name}")
    except Exception as e:
        print(f"❌ 컬렉션 생성 실패: {e}")
        return False
    
    # 5. 기존 데이터 확인 (중복 업로드 방지)
    try:
        existing_count = collection.count()
        if existing_count > 0:
            print(f"⚠️ 컬렉션에 이미 {existing_count}개 데이터가 있습니다.")
            response = input("기존 데이터를 삭제하고 새로 업로드하시겠습니까? (y/N): ")
            if response.lower() == 'y':
                client.delete_collection(collection_name)
                collection = client.create_collection(
                    name=collection_name,
                    metadata={"description": "Product detail page templates for similarity search"}
                )
                print("🗑️ 기존 데이터 삭제 후 새 컬렉션 생성")
            else:
                print("❌ 업로드를 취소합니다.")
                return False
    except Exception as e:
        print(f"⚠️ 기존 데이터 확인 중 오류: {e}")
    
    # 6. 데이터 업로드
    print("📤 데이터 업로드 중...")
    try:
        documents = []
        metadatas = []
        ids = []
        
        for idx, row in df.iterrows():
            documents.append(row['template'])
            metadatas.append({
                'block_type': str(row['block_type']),
                'category': str(row['category']),
                'concept_style': str(row['concept_style'])
            })
            ids.append(f"template_{row['id']}")
        
        # 배치로 업로드
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        print(f"✅ {len(documents)}개 템플릿 업로드 완료!")
        
    except Exception as e:
        print(f"❌ 데이터 업로드 실패: {e}")
        return False
    
    # 7. 업로드 검증
    try:
        final_count = collection.count()
        print(f"📊 최종 컬렉션 데이터 수: {final_count}")
        
        # 샘플 쿼리 테스트
        test_results = collection.query(
            query_texts=["깔끔한 스타일"],
            n_results=3
        )
        print(f"🔍 테스트 쿼리 성공: {len(test_results['documents'][0])}개 결과")
        
    except Exception as e:
        print(f"⚠️ 검증 중 오류: {e}")
    
    print("🎉 ChromaDB 템플릿 데이터 업로드 완료!")
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)