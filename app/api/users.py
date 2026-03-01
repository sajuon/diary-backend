from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
import os
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.auth import UserResponse



router = APIRouter(prefix="/api/users", tags=["Users"])

# GET /api/users/me 엔드포인트를 router 선언 이후로 이동
@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return user

# ...기존 엔드포인트들...

@router.post("/me/profile-image")
async def upload_profile_image(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 파일 확장자 체크
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")
    # 저장 경로
    save_dir = os.path.join(os.getcwd(), "static", "profile_images")
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"user_{user.id}_{file.filename}")
    # 파일 저장
    with open(save_path, "wb") as f:
        f.write(await file.read())
    # DB에 경로 저장 (예: /static/profile_images/user_1_xxx.png)
    rel_path = f"/static/profile_images/user_{user.id}_{file.filename}"
    user.profile_image = rel_path
    db.commit()
    db.refresh(user)
    return JSONResponse({"profile_image": rel_path})

# GET /api/users/me 엔드포인트를 router 선언 이후로 이동
@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return user



class UpdateMeRequest(BaseModel):
    nickname: str | None = None
    profile_image: str | None = None

class AddPearlsRequest(BaseModel):
    amount: int



@router.put("/me", response_model=UserResponse)
def update_me(
    data: UpdateMeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated = False
    if data.nickname is not None:
        user.nickname = data.nickname
        updated = True
    if data.profile_image is not None:
        user.profile_image = data.profile_image
        updated = True
    if updated:
        db.commit()
        db.refresh(user)
    return user


@router.post("/me/add-pearls", response_model=UserResponse)
def add_pearls(
    data: AddPearlsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="추가할 진주 개수는 양수여야 합니다")
    
    user.pearls += data.amount
    db.commit()
    db.refresh(user)
    return user
