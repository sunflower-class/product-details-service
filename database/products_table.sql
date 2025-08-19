-- Create products table for product-details-db
-- 프론트엔드에서 전달되는 상품 정보를 저장하는 테이블

-- Connect to the database
\c product_details_db;

-- Create products table
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    
    -- 기본 상품 정보
    name VARCHAR(200) NOT NULL,                    -- 상품명 (파싱된 결과)
    description TEXT,                              -- 상품 설명 (product_data에서 파싱)
    category VARCHAR(100),                         -- 카테고리
    brand VARCHAR(100),                           -- 브랜드
    price DECIMAL(10, 2),                         -- 가격
    currency VARCHAR(3) DEFAULT 'KRW',            -- 통화 (KRW, USD, EUR 등)
    
    -- 프론트엔드 원본 데이터
    original_product_data TEXT NOT NULL,          -- product_data (원본 텍스트)
    main_image_url VARCHAR(500),                  -- product_image_url
    
    -- 추가 마케팅 정보
    features JSONB,                               -- features 배열 (JSON)
    target_customer VARCHAR(200),                -- target_customer
    tone VARCHAR(50),                            -- tone (professional, casual, friendly 등)
    
    -- 상품 상태 및 메타데이터
    status VARCHAR(20) DEFAULT 'active',          -- active, inactive, discontinued
    is_published BOOLEAN DEFAULT FALSE,          -- 퍼블리시 여부
    view_count INTEGER DEFAULT 0,               -- 조회수
    
    -- 사용자 정보
    user_id VARCHAR(100) NOT NULL,               -- 생성한 사용자 ID
    user_session VARCHAR(100),                   -- 세션 ID (선택)
    
    -- 연관 관계
    product_details_id INTEGER,                  -- product_details 테이블과 연결 (선택적)
    
    -- 타임스탬프
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP,                     -- 퍼블리시된 시간
    
    -- 제약조건
    CONSTRAINT chk_price_positive CHECK (price >= 0),
    CONSTRAINT chk_view_count_positive CHECK (view_count >= 0),
    CONSTRAINT chk_status_valid CHECK (status IN ('active', 'inactive', 'discontinued')),
    CONSTRAINT chk_tone_valid CHECK (tone IN ('professional', 'casual', 'friendly', 'luxury', 'playful', 'serious') OR tone IS NULL)
);

-- 인덱스 생성
CREATE INDEX idx_products_user_id ON products(user_id);
CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_products_brand ON products(brand);
CREATE INDEX idx_products_status ON products(status);
CREATE INDEX idx_products_published ON products(is_published);
CREATE INDEX idx_products_created_at ON products(created_at);
CREATE INDEX idx_products_price ON products(price);
CREATE INDEX idx_products_product_details ON products(product_details_id);

-- Full-text search 인덱스 (상품명, 설명, 브랜드 검색용)
-- 한국어 설정이 없으므로 기본 'simple' 설정 사용
-- CREATE INDEX idx_products_search ON products USING GIN (
--     to_tsvector('simple', COALESCE(name, '') || ' ' || COALESCE(description, '') || ' ' || COALESCE(brand, ''))
-- );
CREATE INDEX idx_products_search ON products USING GIN (
    to_tsvector('simple', COALESCE(name, '') || ' ' || COALESCE(description, '') || ' ' || COALESCE(brand, ''))
);

-- 트리거: updated_at 자동 갱신
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_products_updated_at 
    BEFORE UPDATE ON products 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- 트리거: published_at 자동 설정
CREATE OR REPLACE FUNCTION update_published_at_column()
RETURNS TRIGGER AS $$
BEGIN
    -- is_published가 false에서 true로 변경될 때 published_at 설정
    IF OLD.is_published = FALSE AND NEW.is_published = TRUE THEN
        NEW.published_at = CURRENT_TIMESTAMP;
    -- is_published가 true에서 false로 변경될 때 published_at 초기화
    ELSIF OLD.is_published = TRUE AND NEW.is_published = FALSE THEN
        NEW.published_at = NULL;
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_products_published_at 
    BEFORE UPDATE ON products 
    FOR EACH ROW 
    EXECUTE FUNCTION update_published_at_column();

-- 외래키 제약조건 (product_details와 연결)
-- product_details_id가 NULL이 아닌 경우에만 체크
ALTER TABLE products 
ADD CONSTRAINT fk_products_product_details 
FOREIGN KEY (product_details_id) 
REFERENCES product_details(id) 
ON DELETE SET NULL;

-- 샘플 데이터 (테스트용)
INSERT INTO products (
    name, description, category, brand, price, 
    original_product_data, main_image_url, 
    features, target_customer, tone, user_id
) VALUES 
(
    '프리미엄 무선 이어폰', 
    '고품질 사운드와 뛰어난 배터리 수명을 자랑하는 프리미엄 무선 이어폰입니다.', 
    '전자제품', 
    'TechBrand', 
    199000, 
    '프리미엄 무선 이어폰 - 고품질 사운드, 긴 배터리 수명, 노이즈 캔슬링 기능', 
    'https://example.com/earphones.jpg',
    '["노이즈 캔슬링", "30시간 배터리", "IPX7 방수", "고품질 오디오"]'::jsonb,
    '음악 애호가, 직장인', 
    'professional',
    'test-user-001'
),
(
    '천연 스킨케어 세트', 
    '민감한 피부를 위한 천연 성분의 스킨케어 제품 세트입니다.', 
    '뷰티', 
    'NatureCare', 
    89000, 
    '천연 스킨케어 세트 - 민감 피부용, 천연 성분 100%, 클렌저+토너+크림', 
    'https://example.com/skincare.jpg',
    '["천연 성분 100%", "민감 피부 적합", "무향료", "비건 인증"]'::jsonb,
    '20-30대 여성, 민감 피부', 
    'friendly',
    'test-user-002'
);

-- 뷰: 상품 통계 조회용
CREATE VIEW products_stats AS
SELECT 
    COUNT(*) as total_products,
    COUNT(*) FILTER (WHERE status = 'active') as active_products,
    COUNT(*) FILTER (WHERE is_published = true) as published_products,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(DISTINCT category) as unique_categories,
    AVG(price) as avg_price,
    SUM(view_count) as total_views
FROM products;

-- 뷰: 사용자별 상품 통계
CREATE VIEW user_products_stats AS
SELECT 
    user_id,
    COUNT(*) as total_products,
    COUNT(*) FILTER (WHERE status = 'active') as active_products,
    COUNT(*) FILTER (WHERE is_published = true) as published_products,
    AVG(price) as avg_price,
    SUM(view_count) as total_views,
    MAX(created_at) as last_created_at
FROM products
GROUP BY user_id;

-- 권한 설정 (필요시)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON products TO product_service_user;
-- GRANT USAGE, SELECT ON SEQUENCE products_id_seq TO product_service_user;