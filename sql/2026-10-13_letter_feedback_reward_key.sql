-- 편지 피드백 보상 키를 편지 단위(letter:<id>)에서 일기 단위(entry:<diary_entry_id>)로 이전.
-- 답장 재생성 후 새 답장에 피드백해도 보상이 다시 지급되지 않게 하기 위함.
-- 배포 전에 1회 실행. 여러 번 실행해도 안전 (이미 바뀐 행은 매칭되지 않음).

UPDATE pearl_transactions pt
JOIN otter_letters ol
  ON pt.ref_key = CONCAT('letter:', ol.id)
SET pt.ref_key = CONCAT('entry:', ol.diary_entry_id)
WHERE pt.reason = 'letter_feedback';

-- 확인: 남은 legacy 키 (0이어야 정상. 남아 있다면 편지가 이미 삭제된 행)
SELECT COUNT(*) AS legacy_left
FROM pearl_transactions
WHERE reason = 'letter_feedback' AND ref_key LIKE 'letter:%';
