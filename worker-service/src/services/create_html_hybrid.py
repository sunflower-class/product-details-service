"""
하이브리드 HTML 생성 모듈
고정 HTML 구조 + GPT 콘텐츠 생성을 결합하여 안정적이면서도 유연한 HTML 생성
"""
import os
from dotenv import load_dotenv
from typing import List, Dict, Any
import json

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.services.create_image import download_image

# API 키 로드
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY 환경 변수가 설정되어 있지 않습니다.")

# 안정적인 HTML 템플릿 구조
STABLE_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        .product-section {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
            font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, sans-serif;
        }}
        .hero-section {{
            background: linear-gradient(135deg, {primary_color} 0%, {secondary_color} 100%);
            color: white;
            padding: 60px 40px;
            border-radius: 20px;
            margin-bottom: 40px;
        }}
        .hero-title {{
            font-size: 2.5em;
            font-weight: 700;
            margin-bottom: 20px;
        }}
        .hero-description {{
            font-size: 1.2em;
            line-height: 1.6;
            opacity: 0.95;
        }}
        .feature-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 30px;
            margin: 40px 0;
        }}
        .feature-card {{
            background: #ffffff;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            transition: transform 0.3s;
        }}
        .feature-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.12);
        }}
        .feature-title {{
            font-size: 1.4em;
            color: {primary_color};
            margin-bottom: 15px;
            font-weight: 600;
        }}
        .specs-table {{
            width: 100%;
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
        }}
        .specs-table th {{
            background: {primary_color};
            color: white;
            padding: 15px;
            text-align: left;
        }}
        .specs-table td {{
            padding: 15px;
            border-bottom: 1px solid #f0f0f0;
        }}
        .image-gallery {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 40px 0;
        }}
        .image-container {{
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s;
        }}
        .image-container:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
        }}
        .product-image {{
            width: 100%;
            height: 200px;
            object-fit: cover;
            display: block;
        }}
        .image-caption {{
            padding: 15px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    {sections}
</body>
</html>
"""

SECTION_TEMPLATES = {
    'hero': """
    <div class="product-section hero-section">
        <h1 class="hero-title">{title}</h1>
        <p class="hero-description">{description}</p>
    </div>
    """,
    
    'features': """
    <div class="product-section">
        <h2 style="font-size: 2em; margin-bottom: 30px; color: #333;">주요 특징</h2>
        <div class="feature-grid">
            {feature_cards}
        </div>
    </div>
    """,
    
    'feature_card': """
    <div class="feature-card">
        <h3 class="feature-title">{title}</h3>
        <p style="color: #666; line-height: 1.6;">{description}</p>
    </div>
    """,
    
    'specifications': """
    <div class="product-section">
        <h2 style="font-size: 2em; margin-bottom: 30px; color: #333;">제품 사양</h2>
        <table class="specs-table">
            {spec_rows}
        </table>
    </div>
    """,
    
    'spec_row': """
    <tr>
        <th style="width: 30%;">{label}</th>
        <td>{value}</td>
    </tr>
    """
}

class FeatureItem(BaseModel):
    """특징 아이템"""
    title: str = Field(description="특징 제목")
    description: str = Field(description="특징 설명")

class SpecificationItem(BaseModel):
    """사양 아이템"""
    label: str = Field(description="사양 항목명")
    value: str = Field(description="사양 값")

class ProductContent(BaseModel):
    """GPT가 생성할 구조화된 콘텐츠"""
    hero_title: str = Field(description="제품 메인 타이틀")
    hero_description: str = Field(description="제품 메인 설명 (2-3문장)")
    primary_color: str = Field(description="주 색상 (hex 코드)", default="#4A90E2")
    secondary_color: str = Field(description="보조 색상 (hex 코드)", default="#7BB3F0")
    features: List[FeatureItem] = Field(description="특징 리스트 (2-6개)")
    specifications: List[SpecificationItem] = Field(description="사양 리스트")

def generate_structured_content(product_info: str, reference_templates: List[Dict[str, Any]] = None) -> ProductContent:
    """상품 정보에서 구조화된 콘텐츠를 추출합니다."""
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.3,
        api_key=OPENAI_API_KEY
    )
    
    structured_llm = llm.with_structured_output(ProductContent)
    
    # 참고 템플릿이 있으면 실제 HTML 템플릿을 최우선으로 사용
    template_reference = ""
    if reference_templates:
        template_reference = "\n\n=== 🎯 우선 참고할 HTML 템플릿 예시 (이 스타일을 최대한 따라하세요!) ===\n"
        for i, template in enumerate(reference_templates[:2], 1):
            template_reference += f"\n--- 템플릿 {i} ---\n"
            template_reference += f"스타일 설명: {template.get('concept_style', '')}\n"
            template_reference += f"HTML 구조:\n{template.get('template_html', '')[:800]}...\n"  # 첫 800자만
        template_reference += "\n⚠️ 위 템플릿들의 디자인 패턴과 구조를 최대한 활용하여 새로운 상품에 맞게 변형해주세요!\n"
    
    # 템플릿이 있으면 템플릿 우선 프롬프트, 없으면 기본 프롬프트
    if reference_templates:
        system_prompt = f"""
        당신은 제공된 HTML 템플릿을 참고하여 새로운 상품에 맞는 구조화된 데이터를 추출하는 전문가입니다.
        
        🎯 **중요**: 아래 제공된 템플릿의 디자인 패턴, 색상 스타일, 레이아웃 구조를 최대한 따라해주세요!
        
        상품 정보에서 다음을 추출하세요:
        1. 매력적인 제품 타이틀과 설명 (템플릿 스타일 참고)
        2. 템플릿의 색상 테마와 유사한 색상 선택
        3. 템플릿 구조를 참고한 주요 특징 (2-6개)
        4. 제품 사양 정보
        
        모든 내용은 한국어로 작성하고, 제공된 템플릿의 톤앤매너와 스타일을 최대한 반영하세요.
        {template_reference}
        """
    else:
        system_prompt = f"""
        당신은 상품 정보를 분석하여 구조화된 데이터를 추출하는 전문가입니다.
        제공된 상품 정보에서 다음을 추출하세요:
        
        1. 매력적인 제품 타이틀과 설명
        2. 제품과 어울리는 색상 테마
        3. 주요 특징 (2-6개)
        4. 제품 사양 정보
        
        모든 내용은 한국어로 작성하고, 마케팅 관점에서 매력적으로 작성하세요.
        {template_reference}
        """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "상품 정보:\n{product_info}")
    ])
    
    chain = prompt | structured_llm
    
    return chain.invoke({"product_info": product_info})

def generate_template_based_html(
    product_info: str,
    product_image_url: str,
    reference_templates: List[Dict[str, Any]],
    additional_image_urls: List[str] = None
) -> str:
    """
    ChromaDB 추천 템플릿을 기반으로 직접 HTML 생성 (최우선 모드)
    """
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.3,
        api_key=OPENAI_API_KEY
    )
    
    # 참고 템플릿들을 프롬프트에 포함
    template_examples = ""
    for i, template in enumerate(reference_templates[:2], 1):
        template_examples += f"\n=== 참고 템플릿 {i} ===\n"
        template_examples += f"디자인 컨셉: {template.get('concept_style', '')}\n"
        template_examples += f"HTML 구조:\n{template.get('template_html', '')}\n\n"
    
    # 허용된 이미지 URL들만 필터링 (S3 URL 우선)
    valid_image_urls = []
    if additional_image_urls:
        for url in additional_image_urls:
            # S3 URL, 또는 특정 도메인만 허용
            if any(domain in url for domain in ['.s3.', 'amazonaws.com', 'blob.core.windows.net']):
                valid_image_urls.append(url)
            elif url.startswith('https://') and not any(blocked in url for blocked in ['placehold', 'placeholder', 'example.com']):
                valid_image_urls.append(url)
    
    # 허용된 이미지 URL들 포매팅
    image_urls_str = ""
    if valid_image_urls:
        image_urls_str = "\n허용된 이미지 URLs (반드시 이것만 사용):\n" + "\n".join([f"- {url}" for url in valid_image_urls])
    
    system_prompt = f"""
    당신은 HTML 템플릿을 참고하여 새로운 상품의 상세페이지 HTML을 생성하는 전문가입니다.
    
    🎯 **핵심 지시사항**:
    1. 템플릿의 디자인 스타일과 레이아웃 구조는 유지하되, 텍스트 내용은 완전히 새로운 상품 정보로 교체하세요
    2. 템플릿에 있는 상품명, 설명, 특징 등을 그대로 복사하지 말고 제공된 상품 정보를 기반으로 작성하세요
    3. 색상 스킴, 폰트 스타일, 여백, 그리드 구조 등 디자인 요소만 참고하세요
    4. 이미지는 오직 제공된 허용된 이미지 URL들만 사용하세요 (placehold, placeholder 등 더미 URL 절대 금지)
    5. 여러 이미지가 제공된 경우 갤러리나 다양한 섹션에 배치하세요
    
    ⚠️ **주의사항**:
    - 템플릿의 텍스트를 그대로 사용하지 마세요
    - "PREMIUM PRODUCT", "EXCEPTIONAL QUALITY" 등 템플릿의 제목을 복사하지 마세요
    - 제공된 상품 정보에서 실제 상품명과 특징을 추출하여 사용하세요
    
    {template_examples}
    
    위 템플릿들의 **디자인 스타일**만 참고하여 새로운 상품의 HTML을 생성해주세요.
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", f"상품 정보: {product_info}\n메인 이미지 URL: {product_image_url}{image_urls_str}\n\n위 상품 정보와 이미지들을 사용하여 참고 템플릿의 스타일을 따르는 HTML 상세페이지를 생성해주세요. 템플릿의 텍스트는 사용하지 말고 상품 정보를 기반으로 새로 작성하세요.")
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    return chain.invoke({
        "product_info": product_info,
        "product_image_url": product_image_url
    })

def build_html_from_content(content: ProductContent) -> str:
    """구조화된 콘텐츠를 안정적인 HTML로 변환합니다."""
    
    sections = []
    
    # Hero 섹션
    hero_html = SECTION_TEMPLATES['hero'].format(
        title=content.hero_title,
        description=content.hero_description
    )
    sections.append(hero_html)
    
    # Features 섹션
    if content.features:
        feature_cards = []
        for feature in content.features:
            card_html = SECTION_TEMPLATES['feature_card'].format(
                title=feature.title,
                description=feature.description
            )
            feature_cards.append(card_html)
        
        features_html = SECTION_TEMPLATES['features'].format(
            feature_cards=''.join(feature_cards)
        )
        sections.append(features_html)
    
    # Specifications 섹션
    if content.specifications:
        spec_rows = []
        for spec in content.specifications:
            row_html = SECTION_TEMPLATES['spec_row'].format(
                label=spec.label,
                value=spec.value
            )
            spec_rows.append(row_html)
        
        specs_html = SECTION_TEMPLATES['specifications'].format(
            spec_rows=''.join(spec_rows)
        )
        sections.append(specs_html)
    
    # 최종 HTML 조립
    final_html = STABLE_TEMPLATE.format(
        primary_color=content.primary_color,
        secondary_color=content.secondary_color,
        sections=''.join(sections)
    )
    
    return final_html

def generate_hybrid_html(
    product_info: str,
    product_image_url: str,
    reference_templates: List[Dict[str, Any]] = None,
    additional_image_urls: List[str] = None
) -> List[str]:
    """
    하이브리드 방식으로 안정적인 HTML을 생성합니다.
    
    Args:
        product_info: 상품 정보
        product_image_url: 상품 이미지 URL
        reference_templates: 참조 템플릿들
        additional_image_urls: 추가 이미지 URL들 (AI 생성 이미지)
        
    Returns:
        생성된 HTML (전체 페이지)
    """
    
    # 이미지 다운로드 (유효성 검사) - 빈 URL 체크
    if product_image_url and product_image_url.strip():
        try:
            download_image(product_image_url, ext=None)
        except Exception as e:
            print(f"다운로드 중 오류 발생: {e}")
    else:
        print("⚠️ 이미지 URL이 제공되지 않았습니다.")
    
    try:
        # 템플릿이 있으면 템플릿 기반 직접 HTML 생성, 없으면 기존 방식
        if reference_templates and len(reference_templates) > 0:
            print(f"📚 {len(reference_templates)}개의 참조 템플릿을 사용하여 HTML 생성")
            # 1. 템플릿 기반 직접 HTML 생성 (최우선) - 추가 이미지 전달
            html = generate_template_based_html(
                product_info, 
                product_image_url, 
                reference_templates,
                additional_image_urls=additional_image_urls
            )
        else:
            print("⚠️ 참조 템플릿이 없음, 기본 구조화 방식으로 HTML 생성")
            # 2. 기존 방식: 구조화된 콘텐츠 생성 후 템플릿 적용
            # reference_templates를 None으로 전달하여 안전하게 처리
            content = generate_structured_content(product_info, None)
            html = build_html_from_content(content)
            
            # 추가 이미지가 있으면 HTML에 삽입
            if additional_image_urls:
                image_gallery = f"""
                <div style="margin-top: 40px;">
                    <h3 style="margin-bottom: 20px;">상품 이미지</h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px;">
                """
                for img_url in additional_image_urls:
                    image_gallery += f'<img src="{img_url}" style="width: 100%; border-radius: 8px;" />'
                image_gallery += "</div></div>"
                html = html.replace("</body>", f"{image_gallery}</body>")
        
        # 3. 섹션별로 분리하여 반환 (기존 API와 호환)
        sections = html.split('<div class="product-section')
        result = []
        for section in sections[1:]:  # 첫 번째는 헤더이므로 제외
            result.append('<div class="product-section' + section.split('</div>')[0] + '</div>')
        
        return result if result else [html]
        
    except Exception as e:
        print(f"Error generating hybrid HTML: {e}")
        # 폴백: 기본 HTML 반환
        fallback_html = f"""
        <div style="padding: 40px; font-family: sans-serif;">
            <h1 style="color: #333;">상품 정보</h1>
            <p style="color: #666; line-height: 1.6;">{product_info[:500]}...</p>
        </div>
        """
        return [fallback_html]

def generate_minimal_safe_html(product_info: str) -> str:
    """
    최소한의 안전한 HTML만 생성합니다.
    GPT 의존도를 최소화하고 안정성을 최대화합니다.
    """
    
    # 간단한 키워드 추출
    title = product_info.split('.')[0][:50] if product_info else "상품"
    
    html = f"""
    <div style="max-width: 800px; margin: 0 auto; padding: 40px 20px; font-family: 'Noto Sans KR', sans-serif;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; border-radius: 15px; margin-bottom: 30px;">
            <h1 style="font-size: 2em; margin-bottom: 20px;">{title}</h1>
            <p style="font-size: 1.1em; line-height: 1.6; opacity: 0.95;">
                {product_info[:200]}...
            </p>
        </div>
        
        <div style="background: white; padding: 30px; border-radius: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.1);">
            <h2 style="color: #333; margin-bottom: 20px;">상품 상세 정보</h2>
            <div style="color: #666; line-height: 1.8;">
                {product_info}
            </div>
        </div>
    </div>
    """
    
    return html