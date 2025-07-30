import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer
from PIL import Image
import os
import base64
import openai
import shutil
from dotenv import load_dotenv

def generate_caption_for_image(client, image_path: str) -> str:
    """GPT-4o Vision 모델을 사용하여 이미지에 대한 상세한 설명을 생성합니다."""
    print(f"   - 🖼️ '{image_path}' 캡션 생성 중...")
    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": "Describe this image in detail..."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]}
            ], max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"    - 캡션 생성 오류: {e}")
        return ""

def build_rag_index(model, client_openai, client_chroma, csv_path: str, image_directory: str):
    """(하이브리드용) 이미지 벡터와 텍스트 벡터를 각각의 컬렉션에 저장합니다."""
    # (폴더 삭제 로직을 main 블록으로 이동시킴)
    
    collection_image = client_chroma.get_or_create_collection(name="image_vectors", metadata={"hnsw:space": "cosine"})
    collection_text = client_chroma.get_or_create_collection(name="text_vectors", metadata={"hnsw:space": "cosine"})
    
    print(f"\n--- 🔄 '{csv_path}' 파일 기반 인덱싱 시작 ---")
    df = pd.read_csv(csv_path)

    for index, row in df.iterrows():
        item_id = f"item_{index}"
        image_name = row['이미지 파일명']
        image_path = os.path.join(image_directory, image_name)
        if not os.path.exists(image_path):
            print(f"   - ⚠️ 경고: '{image_path}' 파일이 없어 건너뜁니다.")
            continue
            
        image_embedding = model.encode(Image.open(image_path))
        caption = generate_caption_for_image(client_openai, image_path)
        tags = str(row['추출된 키워드'])
        text_to_embed = f"Tags: {tags}. Caption: {caption}"
        text_embedding = model.encode(text_to_embed)
        metadata = {"이름": str(image_name), "태그": tags, "경로": image_path, "캡션": caption, "url": row['cloud_url']}
        
        collection_image.add(embeddings=[image_embedding.tolist()], metadatas=[metadata], ids=[item_id])
        collection_text.add(embeddings=[text_embedding.tolist()], metadatas=[metadata], ids=[item_id])
        
        print(f"   - ✅ '{item_id}' ({image_name}) 인덱싱 완료")
    print("\n--- ✨ 인덱싱 작업 완료 ---")


if __name__ == "__main__":
    # 1. 환경 변수 로드
    load_dotenv()
    
    # 2. 경로 설정
    DB_PATH = "./chroma_db"
    CSV_FILE_PATH = "/Users/seoyeong/product-details-service/test/image_keywords_cloud.csv" 
    IMAGE_DIRECTORY = "/Users/seoyeong/product-details-service/test/generated_images"

    # 3. DB 폴더 삭제 (가장 먼저 실행)
    if os.path.exists(DB_PATH):
        print(f"⚠️ 기존 '{DB_PATH}' 폴더를 삭제합니다.")
        shutil.rmtree(DB_PATH)

    # 4. 모델 및 클라이언트 초기화 (폴더 삭제 후 실행)
    print("🤖 모델 및 클라이언트를 초기화합니다...")
    model = SentenceTransformer('clip-ViT-B-32')
    client_openai = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    client_chroma = chromadb.PersistentClient(path=DB_PATH) # 수정된 DB_PATH 사용
    print("✅ 초기화 완료.")

    # 5. RAG 인덱스 구축 실행
    print("--- RAG 인덱스 구축을 시작합니다 ---")
    build_rag_index(model, client_openai, client_chroma, CSV_FILE_PATH, IMAGE_DIRECTORY)
    print("--- RAG 인덱스 구축을 완료했습니다 ---")