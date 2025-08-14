import os
from dotenv import load_dotenv
from typing import List, Literal, Optional

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
import re

from src.services.create_image import create_image, reshape_image, download_image

# API 키 로드
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY 환경 변수가 설정되어 있지 않습니다.")

# chromadb 로드
import chromadb
import pandas as pd

client = chromadb.PersistentClient(path="src/_data/chroma_db")
collection = client.get_or_create_collection(name="html_template_search_engine")

try:
    df = pd.read_csv('src/_data/data.csv')
    print("✅ CSV 파일 불러오기 성공!")
except FileNotFoundError:
    print("❌ 'data.csv' 파일을 찾을 수 없습니다. 파일 경로를 확인하세요.")
    exit()

collection.add(
    ids=df['id'].astype(str).tolist(),
    documents=df['concept_style'].tolist(),
    metadatas = df[['block_type', 'template', 'category']].to_dict('records'),
)

# -------------------------------------------------------------
# 1. Pydantic으로 데이터 구조 정의
# -------------------------------------------------------------

BlockType = Literal[
    "Introduction", "KeyFeatures", "Specifications", "UsageGuide", "Comparison", "BrandStory", "FAQ"
]

class StyleConcept(BaseModel):
    """페이지 전체에 적용될 공통 디자인 컨셉입니다."""
    concept_name: str = Field(description="이 스타일 컨셉의 이름 (예: '미니멀 클린', '네온 펑크')")
    color_palette: str = Field(description="페이지의 주요 색상, 배경색, 텍스트 색상")
    font_style: str = Field(description="제목과 본문에 사용할 폰트 스타일")
    overall_mood: str = Field(description="페이지가 전달해야 할 전체적인 분위기")
    css_inspiration: str = Field(description="HTML/CSS 작업 시 참고할 스타일링 가이드")

class ConceptBlock(BaseModel):
    """HTML 생성을 위한 블록 별 스타일 컨셉 및 내용 정보입니다."""
    block_type: BlockType = Field(description="블럭의 시맨틱한 유형")
    content: str = Field(description="""블럭에 들어가야 할 제품의 정보, 내용을 담습니다. 구체적으로 세세하게 작성해야 합니다.""")
    concept_style: str = Field(
        description="""이 블럭의 HTML/CSS 코드를 생성하기 위한 '콘셉트 스타일'을 작성하세요.
        레이아웃, 컴포넌트, 텍스트 톤앤매너, 이미지 배치 등에 대한 콘셉트 스타일을 구체적으로 세세하게 전부 명시해야 합니다. 
        블럭에 들어갈 콘텐츠 내용과 어울려야 합니다."""
    )

class ProductPage(BaseModel):
    """상품 상세 페이지 전체 구조입니다."""
    style_concept: StyleConcept = Field(description="페이지 전체의 일관된 스타일 가이드")
    concept_blocks: List[ConceptBlock] = Field(
        description="상품 상세 페이지의 콘셉 스타일을 구성하는 블럭 리스트",
        min_items=1,
    )

# -------------------------------------------------------------
# 2. LangChain 및 모델 설정
# -------------------------------------------------------------

def generate_product_page_concept(product_info: str, product_image_url: str) -> ProductPage:
    # 이미지 저장 및 유효성 검사
    download_image(product_image_url, ext=None)
    
    """
    상품 정보를 분석하여, HTML 생성을 위한 페이지 '설계도'를 생성합니다.
    (공통 스타일 컨셉 + 각 블럭별 통합 코딩 지시서)
    """
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    structured_llm = llm.with_structured_output(ProductPage)

    # 이미지 지시사항을 통합하고, 특별 태그 사용을 명시, LLM의 역할을 명확히 하고, 금지 조항과 예시를 추가하여 제어 강화
    system_prompt = """
    당신은 개발자를 위한 최종적이고 상세한 청사진을 만드는 세계적인 아트 디렉터입니다.
    출력물은 `style_concept`와 `ConceptBlock` 목록을 포함하는 Pydantic 객체여야 합니다.
    각 `ConceptBlock` 내부의 `concept_style`, `content`는 반드시 상세한 내용으로 구성된 단일 문자열이어야 합니다.

    **핵심 지침**
    1. **크리에이티브 디렉터가 되세요:** 각 블록에 대해 구체적이고 창의적이며 적절한 시각적 스타일을 고안하세요. 모든 것에 하나의 스타일을 사용하지 마세요. 블록의 목적을 생각하고 그에 따라 디자인하세요.
    2. **선택적 생성:** `product_info`에 충분한 정보가 있는 경우에만 블록을 생성하세요. 콘텐츠를 새로 만들지 마세요.
    3. **동일한 여러 블록타입 사용(선택):** 블록타입은 중복하여 사용 가능합니다. 긴 내용을 하나의 블록에 전부 담지 말고 분할하여 만드세요.
    4. **한국어 사용:** 모든 언어는 한국어를 사용해야합니다.
    """

    human_prompt = "{product_info}"
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt)
    ])

    chain = prompt | structured_llm
    return chain.invoke({"product_info": product_info})

def markdown_to_html(markdown_text: str) -> str:
    """
    마크다운 형식의 코드 블럭 문자열에서 순수한 HTML 코드만 추출합니다.
    """
    # 앞뒤의 불필요한 공백이나 개행 문자를 먼저 제거합니다.
    clean_text = markdown_text.strip()
    
    # '```html'로 시작하는 경우, 해당 부분을 제거합니다.
    if clean_text.startswith("```html"):
        clean_text = clean_text[7:]
        
    # '```'로 끝나는 경우, 해당 부분을 제거합니다.
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]

    clean_text = clean_text.replace("\n", "")
    return clean_text.strip()

# -------------------------------------------------------------
# 3. 콘셉트 html 템플릿 가져오기
# -------------------------------------------------------------

def get_concept_html_template(product_page: ProductPage) -> any:
    style_concept = product_page.style_concept
    concept_blocks = product_page.concept_blocks
    results = []

    for idx, block in enumerate(concept_blocks):
        print('create block..', idx)
        search_results = collection.query(
            query_texts=[block.concept_style],
            where={
                "$and": [
                    {"block_type":block.block_type},
                    {"category":"생활용품"} # 일단 고정
                ]
            },
            n_results=3
        )

        distances = search_results['distances'][0]
        templates = [x['template'] for x in search_results['metadatas'][0]]
        
        results.append({ 
            "template": [{ "distance": distances[i], "html": templates[i] } for i, _ in enumerate(distances)],
            "content": block.content
        })

    html_results = []

    for idx, result in enumerate(results):
        print('create html..', idx)
        html_results.append(create_html_block(result, style_concept))

    return html_results

class ProductCheck(BaseModel):
    """html 코드가 현재 상품 설명과 관련 있는지 확인합니다."""
    check: bool = Field(description="html 코드와 현재 상품 설명과 관련있는지 bool 값으로 리턴합니다.")
    reason: str = Field(description="검열 결과를 상세히 작성합니다.")

def check_html(block: any, html: str) -> bool:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, api_key=os.getenv("OPENAI_API_KEY"))
    structured_llm = llm.with_structured_output(ProductCheck)
    system_prompt = """
    당신은 HTML 코드 검열관 입니다. 당신의 임무는 주어진 HTML 코드와, 블록에 대한 정보가 일치하는지 확인하는 것입니다.
    
    ### **핵심 검열 가이드**

    1. **블록 정보 초과:** 블록에 없는 정보가 HTML 코드에 포함되어 있으면 안됩니다.

    2. **블록 정보 불일치:** 블록에 있는 정보와 HTML 코드에 포함된 정보가 불일치하면 안됩니다.
    
    3. **블록 정보 부족:** 블록에 있는 정보가 HTML 코드에 80% 이상 포함되어 있어야 합니다.

    ### **주의사항**

    * 위 가이드라인에 따라 검열을 통과하면 True, 실패하면 False 를 리턴하고 이유를 제시하세요.
    """

    human_prompt = "html 코드: {html_info}, 블록 정보: {block_info}"
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt)
    ])

    chain = prompt | structured_llm
    result = chain.invoke({"html_info": html, "block_info": block})
    print("block check.", result.check, result.reason)
    return result.check

# -------------------------------------------------------------
# 4. 템플릿 사용하여 블록 html 만들기
# -------------------------------------------------------------

def create_html_block(block: any, style: StyleConcept) -> str:
    enhancer_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, api_key=os.getenv("OPENAI_API_KEY"))

    system_prompt = """
    당신은 숙련된 HTML 템플릿 편집 전문가입니다. 당신의 임무는 주어진 HTML 템플릿의 **기존 구조와 레이아웃 스타일은 절대 변경하지 않으면서**, 새로 제공되는 데이터에 맞게 **문구, 이미지 프롬프트, 색상, 테마**와 같은 지정된 요소만을 정밀하게 수정하여 최종 HTML 코드를 생성하는 것입니다.

    ### **핵심 가이드 원칙**

    1.  **구조 보존의 원칙:** 가장 중요한 규칙은 원본 템플릿의 HTML 태그 구조(부모-자식 관계, 순서), CSS 클래스 및 ID, 레이아웃을 정의하는 핵심 스타일(예: `display`, `position`, `grid`, `flex`, 골격이 되는 `padding`과 `margin`)을 **절대 변경하지 않는 것**입니다. 템플릿의 뼈대는 그대로 유지해야 합니다.

    2.  **데이터 중심의 수정:** 당신의 역할은 창의적인 디자인 제안이 아니라, 주어진 데이터를 템플릿의 정확한 위치에 삽입하고 교체하는 것입니다. 문구는 문구로, 이미지 소스는 이미지 소스로, 색상 코드는 색상 코드로 정확하게 대체하는 데 집중하세요.
    
    3.  **목록의 아이템 추가:** 당신은 주어진 템플릿의 리스트 형태의 목록에 들어가야 할 아이템의 갯수를 변경할 수 있습니다. 리스트 아이템의 추가, 삭제를 적절히 사용하세요.

    ### **주의사항**

    * 최종 결과물은 다른 부가 설명 없이, 오직 완성된 **HTML 코드**여야만 합니다.
    * 요청되지 않은 HTML 구조 변경이나 창의적인 스타일 추가는 **절대 금지**입니다. 주어진 역할에 충실하게 데이터를 반영하는 데에만 집중하세요.
    * 기존에 작성된 템플릿을 그대로 사용해서는 안됩니다. 반드시 **주어진 상품 정보에 맞게 수정**해서 사용해야 합니다.
    """

    human_prompt_template = """
    **전반적인 스타일 컨셉을 따르세요:**
    {style_concept}
    **---**
    **기본 템플릿과 들어가야 할 내용:**
    {template_info}
    """
    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", human_prompt_template)])
    chain = prompt | enhancer_llm | StrOutputParser()
    
    html = chain.invoke({
        "style_concept": style.model_dump_json(indent=2),
        "template_info": block,
    })

    # print("html", html)
    # print("block", block["content"])
    
    check = check_html(block=block["content"], html=html)

    # 강화된 프롬프트로 새로운 블럭 객체를 만들어 반환
    return markdown_to_html(html) if check else None

# -------------------------------------------------------------
# 5. 이미지 생성하기
# -------------------------------------------------------------

def _get_image_url_from_prompt(prompt: str, reference_url: Optional[str]) -> str:
    """
    프롬프트를 받아 적절한 API를 호출하고 결과 URL을 반환하는 헬퍼 함수.
    로직 중복을 방지합니다.
    """
    if prompt.startswith("product:") and reference_url:
        # "product:" 접두사를 제거하고 reshape_image 호출
        response = reshape_image(prompt[8:].strip(), reference_url)
    else:
        # 그 외의 경우 create_image 호출
        response = create_image(prompt)
    
    return response.data[0].url


def _generate_images_in_html(html_string: str, product_image_url: Optional[str]) -> str:
    """단일 HTML 문자열 내의 모든 이미지 프롬프트를 실제 이미지 URL로 변환합니다."""
    
    # 1. CSS의 background-image: url(...) 처리
    def process_css_url(match):
        prompt = match.group(1)
        new_url = _get_image_url_from_prompt(prompt, product_image_url)
        return f"url('{new_url}')"

    # 참고: 제공된 데이터의 url()이 작은따옴표를 사용하므로 패턴을 수정했습니다.
    html_after_css = re.sub(r"url\('([^']*)'\)", process_css_url, html_string)

    # 2. <img> 태그의 src 속성 처리
    soup = BeautifulSoup(html_after_css, 'lxml')
    all_images = soup.find_all('img')

    for tag in all_images:
        if tag.get('src'):
            prompt = tag['src']
            tag['src'] = _get_image_url_from_prompt(prompt, product_image_url)
            
    return str(soup)


def process_html_documents(
    html_list: List[str], 
    product_image_url: Optional[str] = None
) -> List[str]:
    """
    HTML 문자열 리스트를 받아 각각을 처리하고,
    처리된 HTML 문자열 리스트를 반환하는 메인 함수.
    """
    processed_html_list = []
    for html_doc in html_list:
        if html_doc is None:
            continue
        processed_doc = _generate_images_in_html(html_doc, product_image_url)
        processed_doc = processed_doc.replace('\n', '')
        processed_doc = processed_doc.replace("\'", '"')
        processed_html_list.append(processed_doc)
        
    return processed_html_list

def product_to_html(product_info: str, product_image_url: str) -> List[str]:
    """상품 정보를 받아 html 형식의 html 코드를 반환합니다."""
    print("request product_to_html...")
    page_layout = generate_product_page_concept(product_info, product_image_url)
    html_results = get_concept_html_template(page_layout)
    html_results = process_html_documents(html_results, product_image_url)
    return html_results
    