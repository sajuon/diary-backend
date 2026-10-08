-- 진주 보상 시스템 + 편지 피드백 테이블 (2026-10-08)
-- 실행: mysql -u diary_user -p diary_backend < sql/2026-10-08_pearl_rewards.sql
-- 여러 번 실행해도 안전 (IF NOT EXISTS)

CREATE TABLE IF NOT EXISTS pearl_transactions (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    amount INT NOT NULL,
    reason VARCHAR(40) NOT NULL,
    ref_key VARCHAR(64) NULL,
    balance_after INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_pearl_tx_user_reason_ref (user_id, reason, ref_key),
    KEY ix_pearl_transactions_user_id (user_id),
    CONSTRAINT fk_pearl_tx_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS letter_feedback (
    id BIGINT NOT NULL AUTO_INCREMENT,
    letter_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    rating VARCHAR(10) NOT NULL,
    comment VARCHAR(300) NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_letter_feedback_letter_id (letter_id),
    KEY ix_letter_feedback_user_id (user_id),
    CONSTRAINT fk_letter_feedback_letter FOREIGN KEY (letter_id) REFERENCES otter_letters (id) ON DELETE CASCADE,
    CONSTRAINT fk_letter_feedback_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
