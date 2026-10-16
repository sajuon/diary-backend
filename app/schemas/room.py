from pydantic import BaseModel, Field


# 소품 크기 배율 허용 범위 — 프론트 lib/room-items.ts의 MIN_SCALE / MAX_SCALE과 같아야 한다
MIN_SCALE = 0.6
MAX_SCALE = 1.8


class Placement(BaseModel):
    """저장 요청용. 범위를 벗어나면 422로 거절한다."""

    item_key: str = Field(min_length=1, max_length=50)
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
    # 크기 배율 (꾸미기에서 모서리를 끌어 조절). 예전 저장분은 없으면 1
    scale: float = Field(default=1.0, ge=MIN_SCALE, le=MAX_SCALE)


class PlacementOut(BaseModel):
    """응답용. DB에 범위 밖 값이 남아 있어도 조회가 실패(500)하지 않게 제약을 두지 않는다.
    값은 _room_payload에서 범위 안으로 맞춰서 내려준다."""

    item_key: str
    x: float
    y: float
    scale: float = 1.0


class RoomResponse(BaseModel):
    theme_key: str
    owned_theme_keys: list[str]
    letter_paper_key: str
    owned_letter_paper_keys: list[str]
    owned_room_item_keys: list[str]
    placements: list[PlacementOut]


class RoomThemeUpdateRequest(BaseModel):
    theme_key: str = Field(min_length=1, max_length=50)


class LetterPaperUpdateRequest(BaseModel):
    letter_paper_key: str = Field(min_length=1, max_length=50)


class PlacementsUpdateRequest(BaseModel):
    placements: list[Placement] = Field(max_length=40)
