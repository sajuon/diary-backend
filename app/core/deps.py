from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.core.security import oauth2_scheme, decode_access_token

from app.models.user import User
from app.models.auth_token import AuthToken


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _is_token_blacklisted(db: Session, token: str, payload: dict) -> bool:
    """
    블랙리스트 정책:
    1) payload에 jti가 있으면 token_jti로 조회
    2) jti가 없으면 token 문자열 자체를 token_jti에 넣어둔 형태도 지원
    """
    jti = payload.get("jti") or token

    # 만료된 토큰은 어차피 접근 불가지만, DB에 저장된 경우도 있을 수 있음
    q = db.query(AuthToken).filter(AuthToken.token_jti == jti)
    return db.query(q.exists()).scalar()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰")

    # exp 확인(혹시 라이브러리 설정이 바뀌어도 안전하게)
    exp = payload.get("exp")
    if exp is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰")

    now_ts = datetime.now(timezone.utc).timestamp()
    if float(exp) < float(now_ts):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="토큰이 만료되었습니다")

    # 블랙리스트 체크(로그아웃 처리된 토큰)
    if _is_token_blacklisted(db, token, payload):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그아웃된 토큰입니다")

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="사용자를 찾을 수 없습니다")

    return user
