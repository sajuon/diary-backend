import httpx
from typing import Dict, Optional


class OAuthError(Exception):
    pass


async def exchange_google_code(code: str, redirect_uri: Optional[str] = None) -> Dict[str, Optional[str]]:
    token_url = "https://oauth2.googleapis.com/token"
    from app.core.config import settings

    client_id = settings.GOOGLE_CLIENT_ID
    client_secret = settings.GOOGLE_CLIENT_SECRET
    redirect = redirect_uri or settings.GOOGLE_REDIRECT_URI

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            token_url,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )

        if token_resp.status_code != 200:
            raise OAuthError(f"Google token exchange failed: {token_resp.text}")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        if not access_token:
            raise OAuthError("No access_token in Google response")

    return await _get_google_user_async(access_token)


async def exchange_kakao_code(code: str, redirect_uri: Optional[str] = None) -> Dict[str, Optional[str]]:
    """Kakao 인증 코드를 액세스 토큰으로 교환하고 사용자 정보 반환"""
    token_url = "https://kauth.kakao.com/oauth/token"
    from app.core.config import settings

    client_id = settings.KAKAO_CLIENT_ID
    client_secret = settings.KAKAO_CLIENT_SECRET
    redirect = redirect_uri or settings.KAKAO_REDIRECT_URI

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret or "",
                "redirect_uri": redirect,
                "code": code,
            },
            timeout=10,
        )

        if token_resp.status_code != 200:
            raise OAuthError(f"Kakao token exchange failed: {token_resp.text}")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        if not access_token:
            raise OAuthError("No access_token in Kakao response")

    return await _get_kakao_user_async(access_token)


async def get_user_info_from_code(provider: str, code: str, redirect_uri: Optional[str] = None) -> Dict[str, Optional[str]]:
    """코드로부터 사용자 정보 획득 (코드 -> 토큰 -> 프로필)"""
    if provider == "google":
        return await exchange_google_code(code, redirect_uri)
    elif provider == "kakao":
        return await exchange_kakao_code(code, redirect_uri)
    else:
        raise OAuthError(f"Unsupported provider: {provider}")


async def get_user_info_async(provider: str, access_token: str) -> Dict[str, Optional[str]]:
    """
    액세스 토큰으로부터 사용자 정보 획득 (async).
    네이티브 앱(카카오 SDK)이 직접 받은 access_token 검증에 사용한다.
    """
    if provider == "kakao":
        return await _get_kakao_user_async(access_token)
    elif provider == "google":
        return await _get_google_user_async(access_token)
    else:
        raise OAuthError(f"Unsupported provider: {provider}")


def _parse_kakao_user(data: dict) -> Dict[str, Optional[str]]:
    kakao_id = data.get("id")
    kakao_account = data.get("kakao_account", {}) or {}
    profile = kakao_account.get("profile", {}) or {}
    return {
        "id": str(kakao_id) if kakao_id is not None else None,
        "email": kakao_account.get("email"),
        "nickname": profile.get("nickname"),
        "profile_image": profile.get("thumbnail_image_url"),
    }


def _parse_google_user(data: dict) -> Dict[str, Optional[str]]:
    google_id = data.get("sub") or data.get("id")
    return {
        "id": str(google_id) if google_id is not None else None,
        "email": data.get("email"),
        "nickname": data.get("name") or data.get("email"),
        "profile_image": data.get("picture"),
    }


KAKAO_USER_URL = "https://kapi.kakao.com/v2/user/me"
GOOGLE_USER_URL = "https://openidconnect.googleapis.com/v1/userinfo"


async def _get_kakao_user_async(access_token: str) -> Dict[str, Optional[str]]:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(KAKAO_USER_URL, headers=headers, timeout=10)
    if resp.status_code != 200:
        raise OAuthError("Failed to fetch Kakao user info")
    return _parse_kakao_user(resp.json())


async def _get_google_user_async(access_token: str) -> Dict[str, Optional[str]]:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(GOOGLE_USER_URL, headers=headers, timeout=10)
    if resp.status_code != 200:
        raise OAuthError("Failed to fetch Google user info")
    return _parse_google_user(resp.json())
