# /home/dori/diary-backend/app/api/auth.py
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db, get_current_user
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    oauth2_scheme,
)
from app.crud import user as crud_user
from app.models.user import User
from app.models.auth_token import AuthToken
from app.schemas.auth import (
    RegisterRequest,
    UserResponse,
    ProfileUpdateRequest,
    OAuthLoginRequest,
)
from app.services.oauth import (
    OAuthError,
    get_user_info_from_code,
    get_user_info_async,
)


router = APIRouter(prefix="/api/auth", tags=["Auth"])


class ReviewerLoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    """TWA 등 쿠키가 유실되는 환경을 위한 fallback 바디."""
    refresh_token: Optional[str] = None


class NativeOAuthRequest(BaseModel):
    """
    네이티브 앱(카카오/구글 SDK)이 단말에서 직접 받은 access_token으로 로그인.
    서버가 해당 토큰으로 provider에 사용자 정보를 다시 조회해서 검증한다.
    """
    provider: str
    access_token: str


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
        domain=settings.REFRESH_COOKIE_DOMAIN,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path="/",
        domain=settings.REFRESH_COOKIE_DOMAIN,
    )


def _blacklist_token(
    db: Session,
    user_id: int,
    token_jti: str,
    token_type: str,
    expires_at,
    reason: str,
) -> None:
    exists = (
        db.query(AuthToken)
        .filter(AuthToken.token_jti == token_jti)
        .first()
    )
    if exists:
        return

    row = AuthToken(
        user_id=user_id,
        token_jti=token_jti,
        token_type=token_type,
        expires_at=expires_at,
        revoked_at=datetime.now(timezone.utc),
        reason=reason,
    )
    db.add(row)
    db.commit()


def _is_blacklisted(db: Session, token_jti: str) -> bool:
    q = db.query(AuthToken).filter(AuthToken.token_jti == token_jti)
    return db.query(q.exists()).scalar()


def _issue_tokens(response: Response, user: User) -> dict:
    """access/refresh 토큰 발급 + 쿠키 설정 + 응답 바디 구성 (공통)."""
    access_token = create_access_token({"user_id": user.id})
    refresh_token = create_refresh_token({"user_id": user.id})
    _set_refresh_cookie(response, refresh_token)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


def _get_or_create_oauth_user(db: Session, provider: str, info: dict) -> User:
    """
    OAuth provider가 준 사용자 정보로 유저를 조회하거나 생성한다.
    /oauth/exchange(웹)와 /oauth/native(앱)가 공유한다.
    """
    provider_id = info.get("id")
    if provider_id is None:
        raise HTTPException(status_code=400, detail="Provider did not return an id")

    user = crud_user.get_user_by_provider(db, provider, provider_id)
    if not user:
        nickname = info.get("nickname") or f"{provider}_{provider_id}"
        user = crud_user.create_user(
            db,
            nickname=nickname,
            email=info.get("email"),
            provider=provider,
            provider_id=provider_id,
        )
    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    if data.email:
        existing = crud_user.get_user_by_email(db, data.email)
        if existing:
            raise HTTPException(status_code=400, detail="이미 가입된 이메일입니다")

    hashed = hash_password(data.password)
    user = crud_user.create_user(
        db,
        nickname=data.nickname,
        email=data.email,
        hashed_password=hashed,
        provider="local",
    )
    return user


@router.post("/login")
def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = crud_user.get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.password or ""):
        raise HTTPException(status_code=400, detail="이메일 또는 비밀번호 오류")

    return _issue_tokens(response, user)


@router.post("/reviewer-login")
def reviewer_login(
    data: ReviewerLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Google Play 심사(리뷰어) 전용 로그인.
    카카오 OAuth를 우회해서 사전에 DB에 만들어둔 테스트 유저로 바로 로그인시킨다.
    .env의 REVIEWER_TEST_EMAIL / REVIEWER_TEST_PASSWORD 와 정확히 일치할 때만 동작한다.
    """
    if not settings.REVIEWER_TEST_EMAIL or not settings.REVIEWER_TEST_PASSWORD or not settings.REVIEWER_TEST_USER_ID:
        raise HTTPException(status_code=404, detail="Not found")

    if (
        data.username != settings.REVIEWER_TEST_EMAIL
        or data.password != settings.REVIEWER_TEST_PASSWORD
    ):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호 오류")

    user = db.query(User).filter(User.id == settings.REVIEWER_TEST_USER_ID).first()
    if not user:
        raise HTTPException(status_code=404, detail="테스트 유저가 존재하지 않습니다")

    return _issue_tokens(response, user)


@router.post("/oauth/exchange")
async def oauth_exchange(
    data: OAuthLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """웹 OAuth: 브라우저가 받은 authorization code를 서버가 토큰으로 교환."""
    try:
        info = await get_user_info_from_code(
            data.provider,
            data.code,
            data.redirect_uri,
        )
    except OAuthError:
        raise HTTPException(
            status_code=401,
            detail="소셜 로그인 토큰이 유효하지 않습니다",
        )

    user = _get_or_create_oauth_user(db, data.provider, info)
    return _issue_tokens(response, user)


@router.post("/oauth/native")
async def oauth_native(
    data: NativeOAuthRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    네이티브 앱 OAuth: 단말의 카카오/구글 SDK가 이미 받은 access_token으로 로그인.

    클라이언트가 보낸 사용자 정보를 그대로 믿지 않고, 서버가 그 토큰으로
    provider에 직접 조회해서 검증한다. 토큰이 위조되었거나 만료되었으면
    provider 호출이 실패하므로 남의 계정으로 로그인할 수 없다.
    """
    provider = (data.provider or "").strip().lower()
    if provider not in ("kakao", "google"):
        raise HTTPException(status_code=400, detail="지원하지 않는 provider입니다")

    if not data.access_token:
        raise HTTPException(status_code=400, detail="access_token이 없습니다")

    try:
        info = await get_user_info_async(provider, data.access_token)
    except OAuthError:
        raise HTTPException(
            status_code=401,
            detail="소셜 로그인 토큰이 유효하지 않습니다",
        )

    user = _get_or_create_oauth_user(db, provider, info)
    return _issue_tokens(response, user)


@router.post("/refresh")
def refresh_access_token(
    request: Request,
    response: Response,
    body: Optional[RefreshRequest] = None,
    db: Session = Depends(get_db),
):
    # 쿠키 우선, 없으면 바디 fallback (TWA / 네이티브 앱 대응)
    refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not refresh_token and body is not None:
        refresh_token = body.refresh_token

    if not refresh_token:
        raise HTTPException(status_code=401, detail="리프레시 토큰이 없습니다")

    payload = decode_refresh_token(refresh_token)
    if payload is None:
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다")

    exp = payload.get("exp")
    if exp is None:
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다")

    now_ts = datetime.now(timezone.utc).timestamp()
    if float(exp) < float(now_ts):
        raise HTTPException(status_code=401, detail="리프레시 토큰이 만료되었습니다")

    jti = payload.get("jti")
    if not jti:
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다")

    if _is_blacklisted(db, jti):
        raise HTTPException(status_code=401, detail="로그아웃된 리프레시 토큰입니다")

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")

    _blacklist_token(
        db=db,
        user_id=user.id,
        token_jti=jti,
        token_type="refresh",
        expires_at=datetime.fromtimestamp(float(exp), tz=timezone.utc),
        reason="refresh_rotated",
    )

    return _issue_tokens(response, user)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    body: Optional[RefreshRequest] = None,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    access_payload = decode_access_token(token)
    if access_payload:
        access_jti = access_payload.get("jti")
        access_exp = access_payload.get("exp")
        user_id = access_payload.get("user_id")
        if access_jti and access_exp and user_id:
            _blacklist_token(
                db=db,
                user_id=int(user_id),
                token_jti=access_jti,
                token_type="access",
                expires_at=datetime.fromtimestamp(float(access_exp), tz=timezone.utc),
                reason="logout",
            )

    refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not refresh_token and body is not None:
        refresh_token = body.refresh_token

    if refresh_token:
        refresh_payload = decode_refresh_token(refresh_token)
        if refresh_payload:
            refresh_jti = refresh_payload.get("jti")
            refresh_exp = refresh_payload.get("exp")
            user_id = refresh_payload.get("user_id")
            if refresh_jti and refresh_exp and user_id:
                _blacklist_token(
                    db=db,
                    user_id=int(user_id),
                    token_jti=refresh_jti,
                    token_type="refresh",
                    expires_at=datetime.fromtimestamp(float(refresh_exp), tz=timezone.utc),
                    reason="logout",
                )

    _clear_refresh_cookie(response)
    return {"message": "로그아웃되었습니다"}


@router.get("/me", response_model=UserResponse)
def get_current_user_info(user: User = Depends(get_current_user)):
    return user


@router.put("/profile", response_model=UserResponse)
def update_profile(
    data: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated = crud_user.update_user_profile(
        db,
        user,
        nickname=data.nickname,
        profile_image=data.profile_image,
    )
    return updated