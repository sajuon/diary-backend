from pydantic import BaseModel, Field


class RoomResponse(BaseModel):
    theme_key: str
    owned_theme_keys: list[str]


class RoomThemeUpdateRequest(BaseModel):
    theme_key: str = Field(min_length=1, max_length=50)
