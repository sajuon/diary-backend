from pydantic import BaseModel, Field


class Placement(BaseModel):
    item_key: str = Field(min_length=1, max_length=50)
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)


class RoomResponse(BaseModel):
    theme_key: str
    owned_theme_keys: list[str]
    letter_paper_key: str
    owned_letter_paper_keys: list[str]
    owned_room_item_keys: list[str]
    placements: list[Placement]


class RoomThemeUpdateRequest(BaseModel):
    theme_key: str = Field(min_length=1, max_length=50)


class LetterPaperUpdateRequest(BaseModel):
    letter_paper_key: str = Field(min_length=1, max_length=50)


class PlacementsUpdateRequest(BaseModel):
    placements: list[Placement] = Field(max_length=40)
