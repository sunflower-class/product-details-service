-- product_details 테이블에 thumbnail 컬럼 추가
-- 첫 번째 이미지의 S3 URL을 저장하는 nullable 컬럼

-- Connect to the database
\c product_details_db;

-- thumbnail 컬럼 추가 (nullable)
ALTER TABLE product_details 
ADD COLUMN thumbnail VARCHAR(500) NULL;

-- thumbnail 컬럼에 대한 코멘트 추가
COMMENT ON COLUMN product_details.thumbnail IS '첫 번째 이미지의 S3 URL (썸네일용)';

-- thumbnail 인덱스 추가 (NULL 값 제외)
CREATE INDEX idx_product_details_thumbnail ON product_details(thumbnail) WHERE thumbnail IS NOT NULL;

-- 기존 데이터에 대해 첫 번째 이미지의 S3 URL로 thumbnail 업데이트
-- (s3_url이 있는 첫 번째 이미지 선택)
UPDATE product_details 
SET thumbnail = (
    SELECT pi.s3_url 
    FROM product_images pi 
    WHERE pi.product_details_id = product_details.id 
      AND pi.s3_url IS NOT NULL 
      AND pi.is_uploaded_to_s3 = TRUE
    ORDER BY pi.created_at ASC 
    LIMIT 1
)
WHERE EXISTS (
    SELECT 1 
    FROM product_images pi 
    WHERE pi.product_details_id = product_details.id 
      AND pi.s3_url IS NOT NULL 
      AND pi.is_uploaded_to_s3 = TRUE
);

-- 업데이트된 레코드 수 확인
SELECT 
    COUNT(*) as total_product_details,
    COUNT(thumbnail) as with_thumbnail,
    COUNT(*) - COUNT(thumbnail) as without_thumbnail
FROM product_details;

-- 샘플 확인
SELECT 
    id, 
    user_id, 
    thumbnail,
    created_at
FROM product_details 
ORDER BY created_at DESC 
LIMIT 5;