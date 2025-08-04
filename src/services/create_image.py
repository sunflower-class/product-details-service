import os
from dotenv import load_dotenv

# .env 파일에서 환경 변수를 로드합니다.
load_dotenv()

# os.environ을 사용하여 환경 변수를 가져옵니다.
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")

if not TOGETHER_API_KEY:
    raise ValueError("TOGETHER_API_KEY 환경 변수가 설정되어 있지 않습니다.")

from together import Together

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

    response = client.images.generate(
        model=f"black-forest-labs/{models[model_key][0]}",
        steps=models[model_key][1],
        prompt=prompt,
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

    response = client.images.generate(
        model=f"black-forest-labs/{models[model_key][0]}",
        steps=models[model_key][1],
        prompt=prompt,
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
        