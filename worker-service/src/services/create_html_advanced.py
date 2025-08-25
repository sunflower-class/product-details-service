"""
고급 HTML 생성 모듈 - 기존 검증된 방식 적용
상품 분석 → 블록별 콘셉트 → ChromaDB 템플릿 매칭 → 구조 보존 HTML 생성
"""
import os
from dotenv import load_dotenv
from typing import List, Literal, Optional, Dict, Any
import re

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup

# ChromaDB 클라이언트 (K8s 환경)
import chromadb
from src.services.template_recommendation_service import template_recommender

# API 키 로드
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# -------------------------------------------------------------
# 1. Pydantic으로 데이터 구조 정의 (기존 방식 그대로)
# -------------------------------------------------------------

BlockType = Literal[
    "Introduction", "KeyFeatures", "Specifications", "UsageGuide", "Comparison", "BrandStory", "FAQ"
]

class StyleConcept(BaseModel):
    """페이지 전체에 적용될 공통 디자인 컨셉"""
    concept_name: str = Field(description="이 스타일 컨셉의 이름 (예: '미니멀 클린', '네온 펑크')")
    color_palette: str = Field(description="페이지의 주요 색상, 배경색, 텍스트 색상")
    font_style: str = Field(description="제목과 본문에 사용할 폰트 스타일")
    overall_mood: str = Field(description="페이지가 전달해야 할 전체적인 분위기")
    css_inspiration: str = Field(description="HTML/CSS 작업 시 참고할 스타일링 가이드")

class ConceptBlock(BaseModel):
    """HTML 생성을 위한 블록 별 스타일 컨셉 및 내용 정보"""
    block_type: BlockType = Field(description="블럭의 시맨틱한 유형")
    content: str = Field(description="블럭에 들어가야 할 제품의 정보, 내용을 담습니다. 구체적으로 세세하게 작성해야 합니다.")
    concept_style: str = Field(
        description="""이 블럭의 HTML/CSS 코드를 생성하기 위한 '콘셉트 스타일'을 작성하세요.
        레이아웃, 컴포넌트, 텍스트 톤앤매너, 이미지 배치 등에 대한 콘셉트 스타일을 구체적으로 세세하게 전부 명시해야 합니다. 
        블럭에 들어갈 콘텐츠 내용과 어울려야 합니다."""
    )

class ProductPage(BaseModel):
    """상품 상세 페이지 전체 구조"""
    style_concept: StyleConcept = Field(description="페이지 전체의 일관된 스타일 가이드")
    concept_blocks: List[ConceptBlock] = Field(
        description="상품 상세 페이지의 콘셉 스타일을 구성하는 블럭 리스트",
        min_items=1,
    )

# -------------------------------------------------------------
# 2. 상품 분석하여 페이지 설계도 생성 (기존 방식)
# -------------------------------------------------------------

def generate_product_page_concept(product_info: str, product_image_url: str) -> ProductPage:
    """
    상품 정보를 분석하여, HTML 생성을 위한 페이지 '설계도'를 생성합니다.
    (공통 스타일 컨셉 + 각 블럭별 통합 코딩 지시서)
    """
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,
        api_key=OPENAI_API_KEY
    )
    structured_llm = llm.with_structured_output(ProductPage)

    system_prompt = """
    당신은 개발자를 위한 최종적이고 상세한 청사진을 만드는 세계적인 아트 디렉터입니다.
    출력물은 `style_concept`와 `ConceptBlock` 목록을 포함하는 Pydantic 객체여야 합니다.
    각 `ConceptBlock` 내부의 `concept_style`, `content`는 반드시 상세한 내용으로 구성된 단일 문자열이어야 합니다.

    **핵심 지침**
    1. **크리에이티브 디렉터가 되세요:** 각 블록에 대해 구체적이고 창의적이며 적절한 시각적 스타일을 고안하세요. 모든 것에 하나의 스타일을 사용하지 마세요. 블록의 목적을 생각하고 그에 따라 디자인하세요.
    2. **선택적 생성:** `product_info`에 충분한 정보가 있는 경우에만 블록을 생성하세요. 콘텐츠를 새로 만들지 마세요.
    3. **동일한 여러 블록타입 사용(선택):** 블록타입은 중복하여 사용 가능합니다. 긴 내용을 하나의 블록에 전부 담지 말고 분할하여 만드세요.
    4. **최소 갯수 생성:** `ConceptBlock`은 최소 8개 이상 생성해야 합니다.
    5. **한국어 사용:** 모든 언어는 한국어를 사용해야합니다.
    """

    human_prompt = "{product_info}"
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt)
    ])

    chain = prompt | structured_llm
    return chain.invoke({"product_info": product_info})

# -------------------------------------------------------------
# 3. ChromaDB에서 콘셉트 매칭하여 HTML 템플릿 가져오기
# -------------------------------------------------------------

def get_concept_html_template(
    product_page: ProductPage, 
    product_info: str, 
    additional_image_urls: List[str] = None
) -> List[str]:
    """블록별로 ChromaDB에서 최적의 템플릿을 찾아 HTML 생성"""
    style_concept = product_page.style_concept
    concept_blocks = product_page.concept_blocks
    html_results = []

    for idx, block in enumerate(concept_blocks):
        print(f'🔍 블록 {idx+1} 생성 중: {block.block_type}')
        
        # ChromaDB에서 유사한 템플릿 검색
        try:
            # template_recommender 사용 (K8s 환경에 맞게)
            search_results = template_recommender.get_recommended_templates(
                style_query=block.concept_style,
                block_type=block.block_type,
                n_results=3
            )
            
            if not search_results:
                print(f"⚠️ 블록 {block.block_type}에 대한 템플릿을 찾을 수 없음")
                continue
            
            # 템플릿 구조화
            templates = []
            for result in search_results:
                templates.append({
                    "distance": 1 - result.get('similarity_score', 0),  # 거리로 변환
                    "html": result.get('template_html', '')
                })
            
            block_data = {
                "template": templates,
                "content": block.content
            }
            
            # HTML 블록 생성
            html_block = create_html_block(block_data, style_concept, product_info, additional_image_urls)
            if html_block:
                html_results.append(html_block)
                print(f"✅ 블록 {idx+1} 생성 완료")
            else:
                print(f"❌ 블록 {idx+1} 생성 실패")
                
        except Exception as e:
            print(f"❌ 블록 {idx+1} 생성 중 오류: {e}")
            continue

    return html_results

# -------------------------------------------------------------
# 4. 템플릿 구조 보존하며 HTML 블록 생성 (기존 방식)
# -------------------------------------------------------------

def validate_and_fix_html(
    block_content: str, 
    html: str, 
    product_info: str,
    additional_image_urls: List[str] = None
) -> str:
    """HTML을 검증하고, 문제가 있으면 수정된 HTML을 반환"""
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2, api_key=OPENAI_API_KEY)
        
        # 허용된 이미지 URL들만 필터링 (S3 URL 우선)
        valid_image_urls = []
        if additional_image_urls:
            for url in additional_image_urls:
                # S3 URL, 또는 특정 도메인만 허용
                if any(domain in url for domain in ['.s3.', 'amazonaws.com', 'blob.core.windows.net']):
                    valid_image_urls.append(url)
                elif url.startswith('https://') and not any(blocked in url for blocked in ['placehold', 'placeholder', 'example.com']):
                    valid_image_urls.append(url)
        
        # 이미지 URL 정보 포함
        image_info = ""
        if valid_image_urls:
            image_info = f"\n\n**허용된 이미지 URL들 (반드시 이것만 사용)**:\n" + "\n".join([f"- {url}" for url in valid_image_urls])
        
        system_prompt = f"""
        당신은 HTML 검증 및 수정 전문가입니다. 생성된 HTML을 검증하고 필요시 수정하는 것이 임무입니다.
        
        ### **검증 및 수정 가이드**
        1. **관련없는 정보 제거**: 상품 정보와 관련없는 내용은 완전히 제거하세요
        2. **누락된 정보 추가**: 블록 내용에 있지만 HTML에 누락된 중요 정보를 추가하세요
        3. **이미지 URL 엄격 검증**: 오직 제공된 허용 이미지 URL들만 사용하세요
        4. **구조 유지**: 원본 HTML의 스타일과 구조는 최대한 보존하세요
        5. **완성된 HTML만 반환**: 설명이나 주석 없이 완성된 HTML 코드만 출력하세요
        
        ### **이미지 URL 규칙 (매우 중요)**
        - 반드시 제공된 허용된 이미지 URL들만 사용하세요
        - placehold, placeholder, example.com 등의 더미 URL은 절대 사용 금지
        - 템플릿에 있는 예시 이미지 URL은 허용된 실제 URL로 교체
        - img 태그의 src 속성에는 오직 허용된 URL만 사용
        
        ### **기타 주의사항**
        - 템플릿 예시 텍스트("PREMIUM PRODUCT", "EXCEPTIONAL QUALITY" 등)는 실제 상품 정보로 교체
        - 관련없는 다른 상품 정보는 절대 포함하지 않기
        
        {image_info}
        """
        
        human_prompt = f"""
        **원본 HTML**: {html}
        
        **블록 정보**: {block_content}
        
        **실제 상품 정보**: {product_info}
        
        위 HTML을 검증하고, 상품 정보와 맞지 않는 내용은 제거하고, 누락된 내용은 추가하여 수정된 HTML을 반환하세요.
        """
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt)
        ])
        
        chain = prompt | llm | StrOutputParser()
        corrected_html = chain.invoke({})
        
        # 마크다운 코드 블록 제거
        corrected_html = markdown_to_html(corrected_html)
        
        # 추가 검증: HTML에서 잘못된 이미지 URL 제거
        corrected_html = _validate_image_urls_in_html(corrected_html, valid_image_urls)
        
        print(f"✅ HTML 검증 및 수정 완료")
        return corrected_html
        
    except Exception as e:
        print(f"❌ HTML 검증/수정 중 오류: {e}")
        return html  # 오류 시 원본 반환

def _validate_image_urls_in_html(html: str, valid_image_urls: List[str]) -> str:
    """HTML에서 잘못된 이미지 URL을 찾아서 올바른 URL로 교체하거나 제거"""
    try:
        import re
        
        if not valid_image_urls:
            return html
        
        # img 태그의 src 속성 찾기
        img_pattern = r'<img[^>]*src=["\']([^"\']*)["\'][^>]*>'
        
        def replace_image_src(match):
            full_tag = match.group(0)
            src_url = match.group(1)
            
            # 허용된 URL인지 확인
            if src_url in valid_image_urls:
                return full_tag  # 그대로 유지
            
            # 잘못된 URL인 경우
            if any(blocked in src_url.lower() for blocked in ['placehold', 'placeholder', 'example.com', '[', ']']):
                # 첫 번째 유효한 이미지로 교체
                if valid_image_urls:
                    new_src = valid_image_urls[0]
                    new_tag = full_tag.replace(src_url, new_src)
                    print(f"🔄 이미지 URL 교체: {src_url[:50]}... → {new_src[:50]}...")
                    return new_tag
                else:
                    print(f"⚠️ 잘못된 이미지 태그 제거: {src_url[:50]}...")
                    return ""  # 태그 자체를 제거
            
            return full_tag  # 다른 경우는 그대로 유지
        
        # 모든 img 태그 처리
        corrected_html = re.sub(img_pattern, replace_image_src, html, flags=re.IGNORECASE)
        
        return corrected_html
        
    except Exception as e:
        print(f"❌ 이미지 URL 검증 중 오류: {e}")
        return html

def create_html_block(
    block: Dict[str, Any], 
    style: StyleConcept, 
    product_info: str, 
    additional_image_urls: List[str] = None
) -> Optional[str]:
    """템플릿을 사용하여 구조를 보존하면서 새로운 HTML 블록 생성"""
    try:
        enhancer_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, api_key=OPENAI_API_KEY)

        # 허용된 이미지 URL들만 필터링 후 정보 포함
        valid_image_urls = []
        if additional_image_urls:
            for url in additional_image_urls:
                if any(domain in url for domain in ['.s3.', 'amazonaws.com', 'blob.core.windows.net']):
                    valid_image_urls.append(url)
                elif url.startswith('https://') and not any(blocked in url for blocked in ['placehold', 'placeholder', 'example.com']):
                    valid_image_urls.append(url)
        
        image_info = ""
        if valid_image_urls:
            image_info = f"\n\n**허용된 이미지 URL들 (반드시 이것만 사용)**:\n" + "\n".join([f"- {url}" for url in valid_image_urls])

        system_prompt = f"""
        당신은 숙련된 HTML 템플릿 편집 전문가입니다. 주어진 HTML 템플릿의 **기존 구조와 레이아웃 스타일은 절대 변경하지 않으면서**, 새로 제공되는 실제 상품 데이터로 내용을 완전히 교체하여 최종 HTML 코드를 생성하는 것입니다.

        ### **핵심 가이드 원칙**
        1. **구조 보존의 원칙:** HTML 태그 구조, CSS 클래스/ID, 레이아웃 스타일을 **절대 변경하지 않습니다**.
        2. **완전한 텍스트 교체:** 템플릿의 모든 텍스트를 실제 상품 정보로 교체하세요. 템플릿 예시를 절대 그대로 두지 마세요.
        3. **실제 이미지만 사용:** 오직 제공된 허용된 이미지 URL만 사용하고, 모든 img 태그에 적용하세요.
        4. **상품명 정확 추출:** 상품 정보에서 실제 상품명을 찾아서 제목에 사용하세요.
        5. **관련없는 정보 금지:** 다른 상품이나 브랜드 정보는 절대 포함하지 마세요.

        ### **절대 금지사항**
        ❌ 템플릿 예시 텍스트 그대로 사용 ("PREMIUM PRODUCT", "EXCEPTIONAL QUALITY" 등)
        ❌ placeholder 이미지 URL 사용 (placehold, example.com 등)
        ❌ 상품 정보와 관련없는 다른 제품 정보 추가
        ❌ 템플릿에 있던 다른 브랜드명이나 제품명 유지
        
        ### **반드시 해야할 작업**
        ✅ 모든 제목을 실제 상품명으로 교체
        ✅ 모든 설명을 실제 상품 정보로 교체  
        ✅ 모든 이미지를 제공된 허용 URL로 교체
        ✅ 상품의 실제 특징과 장점으로 내용 교체

        {image_info}
        """

        human_prompt_template = """
        **스타일 컨셉 (디자인만 참고):**
        {style_concept}
        **---**
        **기본 템플릿 (구조와 스타일만 참고, 텍스트는 교체):**
        {template_info}
        **---**
        **실제 상품 정보 (이것으로 모든 텍스트 교체):** 
        {product_info}
        
        📋 **작업 지시:**
        1. 위 템플릿의 HTML 구조와 CSS 스타일은 그대로 유지
        2. 템플릿의 모든 텍스트를 실제 상품 정보로 완전히 교체
        3. 상품명, 설명, 특징 모두 실제 상품 정보에서 추출하여 사용
        4. 제공된 허용 이미지 URL들을 모든 img 태그에 적용
        5. 템플릿 예시 텍스트는 한 글자도 남기지 말고 모두 교체
        
        완성된 HTML 코드만 출력하세요.
        """
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt), 
            ("human", human_prompt_template)
        ])
        
        chain = prompt | enhancer_llm | StrOutputParser()
        
        html = chain.invoke({
            "style_concept": style.model_dump_json(indent=2),
            "template_info": block,
            "product_info": product_info
        })

        # 마크다운 코드 블록 제거
        html = markdown_to_html(html)
        
        # HTML 검증 및 수정
        corrected_html = validate_and_fix_html(
            block_content=block["content"], 
            html=html, 
            product_info=product_info,
            additional_image_urls=additional_image_urls
        )
        
        return corrected_html
        
    except Exception as e:
        print(f"❌ HTML 블록 생성 중 오류: {e}")
        return None

def _create_image_gallery_html(image_urls: List[str]) -> str:
    """추가 이미지들로 갤러리 HTML 생성 (고급 방식용)"""
    
    gallery_items = []
    for url in image_urls:
        gallery_items.append(f'''
            <div style="flex: 1; margin: 10px; max-width: 300px;">
                <img src="{url}" alt="Product Image" style="width: 100%; height: 250px; object-fit: cover; border-radius: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);" />
            </div>
        ''')
    
    return f'''
    <div style="margin: 40px 0; padding: 30px 20px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);">
        <h3 style="text-align: center; margin-bottom: 25px; color: #333; font-size: 24px; font-weight: bold;">상품 이미지 갤러리</h3>
        <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 15px; max-width: 1000px; margin: 0 auto;">
            {"".join(gallery_items)}
        </div>
    </div>
    '''

def markdown_to_html(markdown_text: str) -> str:
    """마크다운 형식의 코드 블럭에서 순수한 HTML 코드만 추출"""
    clean_text = markdown_text.strip()
    
    if clean_text.startswith("```html"):
        clean_text = clean_text[7:]
        
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]

    clean_text = clean_text.replace("\n", "")
    return clean_text.strip()

# -------------------------------------------------------------
# 5. 메인 함수 (기존 방식 적용)
# -------------------------------------------------------------

def generate_advanced_html(
    product_info: str,
    product_image_url: str,
    additional_image_urls: List[str] = None
) -> List[str]:
    """
    고급 HTML 생성: 상품 분석 → 블록별 콘셉트 → ChromaDB 매칭 → 구조 보존 생성
    
    Args:
        product_info: 상품 정보
        product_image_url: 메인 이미지 URL
        additional_image_urls: 추가 이미지 URL들 (AI 생성 이미지)
    """
    print("🚀 고급 HTML 생성 시작...")
    
    try:
        # 1단계: 상품 정보를 분석하여 페이지 설계도 생성
        print("1️⃣ 상품 페이지 설계도 생성 중...")
        page_layout = generate_product_page_concept(product_info, product_image_url)
        
        # 2단계: 블록별로 ChromaDB에서 템플릿을 찾아 HTML 생성
        print("2️⃣ 블록별 템플릿 매칭 및 HTML 생성 중...")
        html_results = get_concept_html_template(page_layout, product_info, additional_image_urls)
        
        # 3단계: 추가 이미지가 있으면 갤러리 HTML 추가
        if additional_image_urls and len(additional_image_urls) > 0:
            print(f"3️⃣ 추가 이미지 {len(additional_image_urls)}개로 갤러리 생성 중...")
            image_gallery_html = _create_image_gallery_html(additional_image_urls)
            html_results.append(image_gallery_html)
        
        print(f"✅ 고급 HTML 생성 완료: {len(html_results)}개 블록")
        return html_results
        
    except Exception as e:
        print(f"❌ 고급 HTML 생성 실패: {e}")
        return []