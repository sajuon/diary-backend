-- 해도리 성격 + 간식 보관함 (2026-10-08)
-- 실행: mysql 접속 후  USE diary_backend;  SOURCE /home/dori/diary-backend/sql/2026-10-08_haedori_personality.sql;
-- 여러 번 실행해도 안전 (IF NOT EXISTS)

CREATE TABLE IF NOT EXISTS haedori_states (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    cheer INT NOT NULL DEFAULT 0,
    listen INT NOT NULL DEFAULT 0,
    playful INT NOT NULL DEFAULT 0,
    advice INT NOT NULL DEFAULT 0,
    fed_count INT NOT NULL DEFAULT 0,
    snacks JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_haedori_states_user_id (user_id),
    CONSTRAINT fk_haedori_states_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
