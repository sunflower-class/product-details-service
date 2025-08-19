-- product_details와 products 간의 외래키 관계 설정
-- product 삭제 시 관련 product_details도 자동 삭제 (CASCADE)

-- Connect to the database
\c product_details_db;

-- 1. 먼저 products 테이블이 존재하는지 확인
SELECT EXISTS (
   SELECT FROM information_schema.tables 
   WHERE table_schema = 'public' 
   AND table_name = 'products'
);

-- 2. 기존 외래키 제약조건이 있다면 삭제 (있을 경우만)
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_product_details_product_id' 
        AND table_name = 'product_details'
    ) THEN
        ALTER TABLE product_details DROP CONSTRAINT fk_product_details_product_id;
        RAISE NOTICE 'Existing foreign key constraint dropped';
    END IF;
END $$;

-- 3. 데이터 정리: 존재하지 않는 product_id를 참조하는 레코드들 확인 및 정리
SELECT 'Checking for invalid product_id references...' as step;

-- 문제가 되는 레코드 확인
SELECT 
    pd.id as product_details_id,
    pd.product_id,
    pd.user_id,
    'Invalid product_id reference' as issue
FROM product_details pd
LEFT JOIN products p ON pd.product_id = p.id
WHERE pd.product_id IS NOT NULL 
  AND p.id IS NULL;

-- 존재하지 않는 product_id를 NULL로 설정 (외래키 제약조건 위반 방지)
UPDATE product_details 
SET product_id = NULL 
WHERE product_id IS NOT NULL 
  AND product_id NOT IN (SELECT id FROM products);

-- 정리된 레코드 수 확인
SELECT 
    COUNT(*) as total_product_details,
    COUNT(product_id) as with_valid_product_id,
    COUNT(*) - COUNT(product_id) as with_null_product_id
FROM product_details;

-- 4. 이제 안전하게 외래키 제약조건 추가
-- CASCADE 옵션으로 product 삭제 시 관련 product_details도 자동 삭제
ALTER TABLE product_details 
ADD CONSTRAINT fk_product_details_product_id 
FOREIGN KEY (product_id) 
REFERENCES products(id) 
ON DELETE CASCADE 
ON UPDATE CASCADE;

-- 5. 인덱스 확인 및 생성 (성능 향상)
CREATE INDEX IF NOT EXISTS idx_product_details_product_id_fk 
ON product_details(product_id);

-- 6. 제약조건 확인
SELECT 
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    rc.delete_rule,
    rc.update_rule
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
JOIN information_schema.referential_constraints AS rc
    ON tc.constraint_name = rc.constraint_name
    AND tc.table_schema = rc.constraint_schema
WHERE tc.constraint_type = 'FOREIGN KEY' 
AND tc.table_name = 'product_details'
AND tc.constraint_name = 'fk_product_details_product_id';

-- 7. 샘플 데이터 확인 (product_details에서 product_id가 NULL이 아닌 레코드들)
SELECT 
    pd.id as product_details_id,
    pd.product_id,
    pd.user_id,
    pd.status,
    pd.created_at,
    p.name as product_name
FROM product_details pd
LEFT JOIN products p ON pd.product_id = p.id
WHERE pd.product_id IS NOT NULL
ORDER BY pd.created_at DESC
LIMIT 5;

-- 8. 통계 확인
SELECT 
    'product_details' as table_name,
    COUNT(*) as total_records,
    COUNT(product_id) as with_product_id,
    COUNT(*) - COUNT(product_id) as without_product_id
FROM product_details

UNION ALL

SELECT 
    'products' as table_name,
    COUNT(*) as total_records,
    0 as with_product_id,
    0 as without_product_id
FROM products;

-- 9. CASCADE 동작 테스트를 위한 안내
SELECT 
    'Foreign key constraint with CASCADE created successfully' as status,
    'When a product is deleted, all related product_details will be automatically deleted' as note;