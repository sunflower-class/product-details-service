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
            html_block = create_html_block(block_data, style_concept)
            if html_block:
                html_results.append(html_block)
                print(f"✅ 블록 {idx+1} 생성 완료")
            else:
                print(f"❌ 블록 {idx+1} 검증 실패")
                
        except Exception as e:
            print(f"❌ 블록 {idx+1} 생성 중 오류: {e}")
            continue

    return html_results

# -------------------------------------------------------------
# 4. 템플릿 구조 보존하며 HTML 블록 생성 (기존 방식)
# -------------------------------------------------------------

class ProductCheck(BaseModel):
    """HTML 코드가 현재 상품 설명과 관련 있는지 확인"""
    check: bool = Field(description="HTML 코드와 현재 상품 설명과 관련있는지 bool 값으로 리턴")
    reason: str = Field(description="검열 결과를 상세히 작성")

def check_html(block_content: str, html: str) -> bool:
    """생성된 HTML이 블록 내용과 일치하는지 검증"""
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, api_key=OPENAI_API_KEY)
        structured_llm = llm.with_structured_output(ProductCheck)
        
        system_prompt = """
        당신은 HTML 코드 검열관입니다. 주어진 HTML 코드와 블록에 대한 정보가 일치하는지 확인하는 것이 임무입니다.
        
        ### **핵심 검열 가이드**
        1. **블록 정보 초과:** 블록에 없는 정보가 HTML 코드에 포함되어 있으면 안됩니다.
        2. **블록 정보 불일치:** 블록에 있는 정보와 HTML 코드에 포함된 정보가 불일치하면 안됩니다.
        3. **블록 정보 부족:** 블록에 있는 정보가 HTML 코드에 대부분 포함되어 있어야 합니다.

        위 가이드라인에 따라 검열을 통과하면 True, 실패하면 False를 리턴하고 이유를 제시하세요.
        """

        human_prompt = "HTML 코드: {html_info}, 블록 정보: {block_info}"
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt)
        ])

        chain = prompt | structured_llm
        result = chain.invoke({"html_info": html, "block_info": block_content})
        print(f"📋 블록 검증: {result.check} - {result.reason}")
        return result.check
        
    except Exception as e:
        print(f"❌ HTML 검증 중 오류: {e}")
        return True  # 검증 실패 시 통과로 처리

def create_html_block(block: Dict[str, Any], style: StyleConcept) -> Optional[str]:
    """템플릿을 사용하여 구조를 보존하면서 새로운 HTML 블록 생성"""
    try:
        enhancer_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, api_key=OPENAI_API_KEY)

        system_prompt = """
        당신은 숙련된 HTML 템플릿 편집 전문가입니다. 주어진 HTML 템플릿의 **기존 구조와 레이아웃 스타일은 절대 변경하지 않으면서**, 새로 제공되는 데이터에 맞게 **문구, 이미지 프롬프트, 색상, 테마**와 같은 지정된 요소만을 정밀하게 수정하여 최종 HTML 코드를 생성하는 것입니다.

        ### **핵심 가이드 원칙**
        1. **구조 보존의 원칙:** 원본 템플릿의 HTML 태그 구조, CSS 클래스 및 ID, 레이아웃을 정의하는 핵심 스타일을 **절대 변경하지 않습니다**.
        2. **데이터 중심의 수정:** 주어진 데이터를 템플릿의 정확한 위치에 삽입하고 교체하는 것에 집중하세요.
        3. **목록의 아이템 추가:** 템플릿의 리스트 형태의 목록에 들어가야 할 아이템의 갯수를 변경할 수 있습니다.

        ### **주의사항**
        * 최종 결과물은 완성된 **HTML 코드**만 출력하세요.
        * 요청되지 않은 HTML 구조 변경이나 창의적인 스타일 추가는 **절대 금지**입니다.
        * 기존 템플릿을 그대로 사용하지 말고 반드시 **주어진 상품 정보에 맞게 수정**하세요.
        * 이미지 URL은 실제 이미지 URL로 교체하세요.
        """

        human_prompt_template = """
        **전반적인 스타일 컨셉을 따르세요:**
        {style_concept}
        **---**
        **기본 템플릿과 들어가야 할 내용:**
        {template_info}
        """
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt), 
            ("human", human_prompt_template)
        ])
        
        chain = prompt | enhancer_llm | StrOutputParser()
        
        html = chain.invoke({
            "style_concept": style.model_dump_json(indent=2),
            "template_info": block,
        })

        # 마크다운 코드 블록 제거
        html = markdown_to_html(html)
        
        # HTML 검증
        check = check_html(block_content=block["content"], html=html)
        
        return html if check else None
        
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