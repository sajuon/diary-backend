-- 해도리 방 소품 (2026-10-08)
-- 실행: mysql 접속 후  USE diary_backend;  SOURCE /home/dori/diary-backend/sql/2026-10-08_room_items.sql;
-- 1) ALTER는 한 번만 실행 (이미 컬럼이 있으면 "Duplicate column" 에러가 나는데, 무시해도 됨)

ALTER TABLE user_rooms
    ADD COLUMN placements JSON NULL AFTER letter_paper_key;

-- 2) 소품 10개 (여러 번 실행해도 중복 생성 안 됨)
INSERT INTO shop_items (name, description, price, item_type, item_key, is_active, created_at)
VALUES
    ('벽시계',      '벽에 거는 동그란 시계',     120, 'room_item', 'wall_clock',  1, NOW()),
    ('하트 액자',   '하트 그림이 든 작은 액자',   80, 'room_item', 'heart_frame', 1, NOW()),
    ('동그란 창문', '햇살이 드는 둥근 창',       150, 'room_item', 'round_window',1, NOW()),
    ('달력',        '날짜를 넘기는 벽 달력',      60, 'room_item', 'calendar',    1, NOW()),
    ('벽 선반',     '작은 화분을 올린 선반',     100, 'room_item', 'wall_shelf',  1, NOW()),
    ('화분',        '초록 잎이 난 작은 화분',     80, 'room_item', 'plant',       1, NOW()),
    ('스탠드 조명', '따뜻한 빛의 스탠드',        120, 'room_item', 'floor_lamp',  1, NOW()),
    ('책장',        '책이 꽂힌 나무 책장',       200, 'room_item', 'bookshelf',   1, NOW()),
    ('쿠션',        '말랑한 분홍 쿠션',           60, 'room_item', 'cushion',     1, NOW()),
    ('러그',        '바닥에 까는 민트색 러그',   150, 'room_item', 'rug',         1, NOW())
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    description = VALUES(description),
    price = VALUES(price),
    is_active = VALUES(is_active);
