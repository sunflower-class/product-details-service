import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate


# .env 파일에서 환경 변수를 로드합니다.
load_dotenv()

# os.environ을 사용하여 환경 변수를 가져옵니다.
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")

if not TOGETHER_API_KEY:
    raise ValueError("TOGETHER_API_KEY 환경 변수가 설정되어 있지 않습니다.")

from together import Together

def translate_prompt(prompt: str) -> any:
    """
    상품 정보를 분석하여, HTML 생성을 위한 페이지 '설계도'를 생성합니다.
    (공통 스타일 컨셉 + 각 블럭별 통합 코딩 지시서)
    """
    print("prompt translate...")
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    system_prompt = """
    당신은 최고의 한글을 영어로 번역하는 이미지 프롬프트 번역가입니다.
    요청한 이미지 프롬프트를 영어로 번역하여 반환하세요.
    번역한 이미지 프롬프트만 긴 텍스트 문장으로 반환해야 합니다.
    """

    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", prompt)])
    chain = prompt | llm | StrOutputParser()
    
    en_prompt = chain.invoke({})

    return en_prompt


# size: small(256*256), default(512*512), large(1024*1024)
def create_image(prompt: str, size: str = "default") -> any:
    print("create_image...")
    client = Together(
        api_key=TOGETHER_API_KEY,
    )
    size_list = {
        "small": [256, 256],
        "default": [512, 512],
        "large": [1024, 1024]
    }

    # model_name, steps
    models = {
        "free": ["FLUX.1-schnell-Free", None],
        "schnell": ["FLUX.1-schnell", 4],
        "dev": ["FLUX.1-dev", 28],
        "kontext-dev": ["FLUX.1-kontext-dev", 28],
    }

    model_key = "free"

    print("prompt", prompt)
    en_prompt = translate_prompt(prompt=prompt)
    print("en_prompt", en_prompt)

    response = client.images.generate(
        model=f"black-forest-labs/{models[model_key][0]}",
        steps=models[model_key][1],
        prompt=en_prompt,
        width=size_list[size][0],
        height=size_list[size][1]
    )

    return response

# size: small(256*256), default(512*512), large(1024*1024)
def reshape_image(prompt: str, image_url: str, size: str = "default") -> any:
    print("reshape_image...")
    client = Together(
        api_key=TOGETHER_API_KEY,
    )
    size_list = {
        "small": [256, 256],
        "default": [512, 512],
        "large": [1024, 1024]
    }

    # model_name, steps
    models = {
        "kontext-dev": ["FLUX.1-kontext-dev", 28],
    }

    model_key = "kontext-dev"

    en_prompt = translate_prompt(prompt=prompt)

    response = client.images.generate(
        model=f"black-forest-labs/{models[model_key][0]}",
        steps=models[model_key][1],
        prompt=en_prompt,
        width=size_list[size][0],
        height=size_list[size][0],
        image_url=image_url,
    )

    return response

import requests

# 확장자 제외한 이름 사용
def download_image(
        url: str, 
        filename: str | None = None, 
        path="./src/_data/images", 
        ext: str | None = 'jpg',
    ) -> any:
    last_part = url.split('/')[-1]
    filename = filename if filename != None else last_part
    extension = f'.{ext}' if ext != None else ''
    filepath = f'{path}/{filename}{extension}'

    try:
        response = requests.get(url)
        # 요청 성공 여부 확인
        if response.status_code == 200:
            # 'wb' (write binary) 모드로 파일을 열고 이미지 데이터를 씀
            with open(filepath, 'wb') as f:
                f.write(response.content)
            print(f"이미지 다운로드 완료: {filepath}")
        else:
            print(f"오류 발생: HTTP {response.status_code}")
    except Exception as e:
        print(f"다운로드 중 오류 발생: {e}")
        