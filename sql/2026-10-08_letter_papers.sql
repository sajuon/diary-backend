-- 편지지 테마 (2026-10-08)
-- 실행: mysql 접속 후  USE diary_backend;  SOURCE /home/dori/diary-backend/sql/2026-10-08_letter_papers.sql;
-- 1) ALTER는 한 번만 실행 (이미 컬럼이 있으면 "Duplicate column" 에러가 나는데, 무시해도 됨)

ALTER TABLE user_rooms
    ADD COLUMN letter_paper_key VARCHAR(50) NOT NULL DEFAULT 'default' AFTER theme_key;

-- 2) 편지지 상품 5개 (여러 번 실행해도 중복 생성 안 됨)
INSERT INTO shop_items (name, description, price, item_type, item_key, is_active, created_at)
VALUES
    ('줄노트',      '연한 가로줄이 있는 노트 편지지',  150, 'letter_paper', 'lined',     1, NOW()),
    ('모눈 노트',   '사각 모눈 무늬 편지지',           150, 'letter_paper', 'grid',      1, NOW()),
    ('꽃 편지',     '모서리에 꽃 장식이 있는 편지지',  200, 'letter_paper', 'flower',    1, NOW()),
    ('밤하늘 편지', '남색 종이에 별이 뜬 편지지',      200, 'letter_paper', 'night_sky', 1, NOW()),
    ('바다 우표',   '하늘색 종이에 우표가 붙은 편지지', 200, 'letter_paper', 'sea_stamp', 1, NOW())
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    description = VALUES(description),
    price = VALUES(price),
    is_active = VALUES(is_active);
