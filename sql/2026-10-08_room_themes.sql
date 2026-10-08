-- 해도리 방 테마 (2026-10-08)
-- 실행: mysql 접속 후  USE diary_backend;  SOURCE /home/dori/diary-backend/sql/2026-10-08_room_themes.sql;
-- 1) ALTER는 한 번만 실행 (이미 컬럼이 있으면 "Duplicate column" 에러가 나는데, 무시해도 됨)

ALTER TABLE shop_items
    ADD COLUMN item_key VARCHAR(50) NULL AFTER item_type,
    ADD UNIQUE KEY uq_shop_items_item_key (item_key);

-- 2) 적용 중인 테마 (사용자당 1행)
CREATE TABLE IF NOT EXISTS user_rooms (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    theme_key VARCHAR(50) NOT NULL DEFAULT 'default',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_user_rooms_user_id (user_id),
    CONSTRAINT fk_user_rooms_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3) 진주 상점 테마 상품 5개 (여러 번 실행해도 중복 생성 안 됨)
INSERT INTO shop_items (name, description, price, item_type, item_key, is_active, created_at)
VALUES
    ('밤바다',     '별이 반짝이는 남색 밤바다 방',   300, 'theme', 'night_sea', 1, NOW()),
    ('벚꽃',       '연분홍 꽃잎이 흩날리는 봄 방',   300, 'theme', 'cherry',    1, NOW()),
    ('숲속',       '초록 줄무늬 벽과 나무 바닥',     300, 'theme', 'forest',    1, NOW()),
    ('가을 단풍',  '주황빛으로 물든 따뜻한 방',      300, 'theme', 'autumn',    1, NOW()),
    ('눈 오는 날', '하얀 눈송이와 체크 바닥',        300, 'theme', 'snow',      1, NOW())
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    description = VALUES(description),
    price = VALUES(price),
    is_active = VALUES(is_active);
