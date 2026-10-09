-- 포춘쿠키 하루 기록 (오늘의 무료 쿠키 + 상점 쿠키, 종류별 하루 1개) (2026-10-09)
-- 실행: mysql -u diary_user -p diary_backend < sql/2026-10-09_fortune_cookies.sql
-- 여러 번 실행해도 안전 (IF NOT EXISTS)

CREATE TABLE IF NOT EXISTS fortune_cookies (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    kind VARCHAR(10) NOT NULL,
    date_key VARCHAR(10) NOT NULL,
    reward INT NOT NULL,
    message VARCHAR(200) NOT NULL,
    source VARCHAR(10) NOT NULL DEFAULT 'llm',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_fortune_cookie_user_kind_date (user_id, kind, date_key),
    KEY ix_fortune_cookies_user_id (user_id),
    CONSTRAINT fk_fortune_cookie_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
