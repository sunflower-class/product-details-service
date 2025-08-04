from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse # HTMLResponse 임포트
from sentence_transformers import SentenceTransformer
import chromadb
import openai
from dotenv import load_dotenv
import os

# --- 0. 초기화 ---
load_dotenv()
print("🤖 API 서버 시작... 모델 및 클라이언트를 초기화합니다.")

model = SentenceTransformer('clip-ViT-B-32')
client_openai = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
client_chroma = chromadb.PersistentClient(path="./chroma_db") 
collection_image = client_chroma.get_collection(name="image_vectors")
collection_text = client_chroma.get_collection(name="text_vectors")

print("✅ 초기화 완료.")

app = FastAPI()

# --- 1. 검색 API 엔드포인트 정의 (HTML 반환하도록 수정) ---
@app.get("/search", response_class=HTMLResponse)
async def search_endpoint(query: str):
    """
    사용자의 쿼리를 받아 스마트 검색을 수행하고 결과를 HTML 페이지로 반환합니다.
    """
    if not query:
        raise HTTPException(status_code=400, detail="'query' 파라미터가 필요합니다.")

    try:
        corrected_query = query
        query_words = set(word for word in corrected_query.lower().split() if len(word) > 2)
        query_embedding = model.encode(corrected_query).tolist()
        CANDIDATE_COUNT = 20
        image_results = collection_image.query(query_embeddings=[query_embedding], n_results=CANDIDATE_COUNT)
        text_results = collection_text.query(query_embeddings=[query_embedding], n_results=CANDIDATE_COUNT)

        rrf_scores = {}
        k = 60
        for rank, item_id in enumerate(image_results['ids'][0]):
            if item_id not in rrf_scores: rrf_scores[item_id] = {'score': 0, 'metadata': image_results['metadatas'][0][rank]}
            rrf_scores[item_id]['score'] += 1 / (k + rank)

        for rank, item_id in enumerate(text_results['ids'][0]):
            if item_id not in rrf_scores: rrf_scores[item_id] = {'score': 0, 'metadata': text_results['metadatas'][0][rank]}
            rrf_scores[item_id]['score'] += 1 / (k + rank)
        
        KEYWORD_BOOST = 1.0 
        for item_id, data in rrf_scores.items():
            tags = data['metadata'].get('태그', '').lower()
            if any(word in tags for word in query_words):
                 rrf_scores[item_id]['score'] += KEYWORD_BOOST

        sorted_results = sorted(rrf_scores.items(), key=lambda item: item[1]['score'], reverse=True)
        
        # 5. 결과 반환: JSON 대신 HTML 문자열 생성
        html_content = f"""
        <html>
            <head>
                <title>검색 결과: {query}</title>
                <style>
                    body {{ font-family: sans-serif; margin: 20px; }}
                    .result {{ border: 1px solid #ccc; border-radius: 8px; padding: 15px; margin-bottom: 20px; max-width: 800px; }}
                    img {{ max-width: 300px; border-radius: 4px; float: left; margin-right: 15px; }}
                    p {{ margin: 2px 0; }}
                    .clear {{ clear: both; }}
                </style>
            </head>
            <body>
                <h1>검색 결과: "{query}"</h1>
        """
        
        if not sorted_results:
            html_content += "<p>검색 결과가 없습니다.</p>"
        else:
            for item_id, data in sorted_results[:5]:
                metadata = data['metadata']
                image_url = metadata.get('url', '')
                name = metadata.get('이름', '')
                caption = metadata.get('캡션', '')
                score = data['score']
                boost_info = "(⭐ 키워드 부스트됨)" if score >= KEYWORD_BOOST else ""

                html_content += f"""
                <div class="result">
                    <img src="{image_url}" alt="{name}">
                    <p><b>ID:</b> {item_id}</p>
                    <p><b>이름:</b> {name}</p>
                    <p><b>점수:</b> {score:.4f} {boost_info}</p>
                    <p><b>캡션:</b> {caption}</p>
                    <div class="clear"></div>
                </div>
                """
        
        html_content += "</body></html>"
        
        return HTMLResponse(content=html_content)


    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류 발생: {e}")

# (로컬 테스트용 실행 코드는 동일)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    # 확인 예시 : http://127.0.0.1:8000/search?query=a%20man%20blowing%20birthday%20candles
    # 뒤에 query=뒤에 검색어를 넣기