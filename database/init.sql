-- Create database
CREATE DATABASE product_details_db;

-- Connect to the database
\c product_details_db;

-- Create tables
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    color VARCHAR(7) DEFAULT '#4A90E2',
    icon VARCHAR(50),
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    preview_image VARCHAR(500),
    block_type VARCHAR(50) NOT NULL,
    html_structure TEXT NOT NULL,
    primary_color VARCHAR(7) DEFAULT '#4A90E2',
    secondary_color VARCHAR(7) DEFAULT '#7BB3F0',
    usage_count INTEGER DEFAULT 0,
    is_featured BOOLEAN DEFAULT FALSE,
    difficulty_level INTEGER DEFAULT 1 CHECK (difficulty_level >= 1 AND difficulty_level <= 3),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE template_categories (
    template_id INTEGER REFERENCES templates(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
    PRIMARY KEY (template_id, category_id)
);

-- 생성된 상품 상세페이지 저장
CREATE TABLE product_details (
    id SERIAL PRIMARY KEY,
    product_id INTEGER, -- 실제 상품 ID (나중에 연결, NULL 가능)
    user_id VARCHAR(100) NOT NULL, -- 헤더 X-User-Id
    user_session VARCHAR(100), -- 세션 ID (추가 정보)
    original_product_info TEXT NOT NULL, -- 사용자가 입력한 원본 상품 정보
    generated_html JSONB NOT NULL, -- 생성된 HTML 블록들 (JSON 배열)
    used_templates INTEGER[], -- 사용된 템플릿 ID들
    used_categories INTEGER[], -- 사용된 카테고리 ID들
    status VARCHAR(20) DEFAULT 'draft', -- 'draft', 'published', 'archived'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 상품 이미지 저장
CREATE TABLE product_images (
    id SERIAL PRIMARY KEY,
    product_details_id INTEGER NOT NULL REFERENCES product_details(id) ON DELETE CASCADE,
    product_id INTEGER, -- 실제 상품 ID (선택적)
    user_id VARCHAR(100) NOT NULL, -- 헤더 X-User-Id
    original_prompt TEXT, -- GENERATED일 때만 필요
    translated_prompt TEXT, -- GENERATED일 때만 필요
    s3_url VARCHAR(500), -- S3 설정 전까지는 NULL 허용
    temp_url VARCHAR(500), -- Together AI 임시 URL 또는 원본 URL
    image_source VARCHAR(20) DEFAULT 'GENERATED', -- 'GENERATED', 'ORIGINAL'
    image_type VARCHAR(50) DEFAULT 'product', -- 'product', 'background', 'icon', etc.
    width INTEGER,
    height INTEGER,
    file_size BIGINT,
    is_uploaded_to_s3 BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스
CREATE INDEX idx_product_details_product_id ON product_details(product_id);
CREATE INDEX idx_product_details_user_id ON product_details(user_id);
CREATE INDEX idx_product_details_session ON product_details(user_session);
CREATE INDEX idx_product_images_product_details ON product_images(product_details_id);
CREATE INDEX idx_product_images_user_id ON product_images(user_id);
CREATE INDEX idx_product_images_product_id ON product_images(product_id);

-- Basic data
INSERT INTO categories (name, description, color, display_order) VALUES
('전체', '모든 템플릿', '#333333', 0),
('인기', '인기 템플릿', '#FF6B6B', 1),
('심플', '깔끔한 디자인', '#4ECDC4', 2),
('모던', '현대적인 스타일', '#45B7D1', 3);

INSERT INTO templates (name, description, block_type, html_structure, is_featured) VALUES
('그라디언트 히어로', '그라디언트 배경의 메인 섹션', 'hero', 
'<div style="background: linear-gradient(135deg, {{primary_color}} 0%, {{secondary_color}} 100%); color: white; padding: 60px 40px; border-radius: 20px; text-align: center;">
<h1 style="font-size: 2.5em; margin-bottom: 20px;">{{title}}</h1>
<p style="font-size: 1.2em; line-height: 1.6;">{{description}}</p>
</div>', true);

-- Link template to categories  
INSERT INTO template_categories (template_id, category_id) VALUES (1, 1), (1, 2), (1, 4);