# Test Directory README

이 디렉토리에는 `product-details-service`의 테스트 관련 스크립트와 데이터가 포함되어 있습니다.

## 📁 파일 구성

*   `generated_images/`: 테스트에 사용될 이미지 파일들이 저장된 디렉토리입니다.
*   `image_keywords.csv`: 각 이미지 파일명과 이미지에 대한 핵심 키워드를 담고 있는 CSV 파일입니다.
*   `image_keywords_cloud.csv`: `image_keywords.csv`에 이미지의 클라우드 URL이 추가된 버전입니다.
*   `test.ipynb`: 이미지 키워드 생성 및 Azure 업로드를 위한 Jupyter 노트북입니다.
*   `images_rag.py`: 이미지 검색을 위한 RAG(Retrieval-Augmented Generation) 인덱스를 구축하는 스크립트입니다.
*   `api.py`: FastAPI 기반의 이미지 검색 API 서버입니다.

## 🚀 실행 순서

**중요: 반드시 아래 순서대로 실행해야 합니다!**

### 1단계: 이미지 키워드 생성 및 Azure 업로드
```bash
# test.ipynb 실행
jupyter notebook test.ipynb
```
- 노트북에서 "이미지 키워드 만들기" 섹션 실행
- "azure 업로드" 섹션 실행
- 결과로 `image_keywords_cloud.csv` 파일이 생성됩니다

### 2단계: RAG 인덱스 구축
```bash
python images_rag.py
```
- `image_keywords_cloud.csv`와 `generated_images/` 디렉토리의 이미지들을 사용
- ChromaDB에 벡터 인덱스를 생성합니다
- 실행 시 기존 `chroma_db` 폴더를 삭제하고 새로 생성합니다

### 3단계: API 서버 실행
```bash
python api.py
```
- FastAPI 서버가 `http://127.0.0.1:8000`에서 실행됩니다
- 검색 예시: `http://127.0.0.1:8000/search?query=a%20man%20blowing%20birthday%20candles`



### 주의사항
- API 서버는 `images_rag.py` 실행 후에만 정상 작동합니다
- 이미지 파일들이 `generated_images/` 폴더에 있어야 합니다

## 🔧 각 파일의 역할

- **`test.ipynb`**: 이미지 생성, 키워드 추출, Azure 업로드 작업
- **`images_rag.py`**: 이미지와 텍스트를 벡터화하여 검색 인덱스 구축
- **`api.py`**: 웹 API를 통해 이미지 검색 서비스 제공
- **`image_keywords_cloud.csv`**: 이미지 메타데이터와 클라우드 URL 정보
