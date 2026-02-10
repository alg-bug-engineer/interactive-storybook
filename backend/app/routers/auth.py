"""认证 API：注册、登录、当前用户、升级付费"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.utils.user_store import (
    validate_email,
    get_user_by_email,
    verify_user,
    create_user,
    set_user_paid,
    create_token,
    get_email_by_token,
    delete_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def _get_current_email(credentials: HTTPAuthorizationCredentials | None) -> str | None:
    if not credentials or not credentials.credentials:
        return None
    return get_email_by_token(credentials.credentials)


async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    """依赖：要求已登录，返回用户信息 dict。"""
    email = _get_current_email(credentials)
    if not email:
        raise HTTPException(status_code=401, detail="请先登录")
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    return user


@router.post("/register")
async def register(body: RegisterRequest):
    """注册：邮箱+密码，校验邮箱格式，注册后为免费用户。"""
    email = (body.email or "").strip()
    password = body.password or ""
    if not validate_email(email):
        raise HTTPException(status_code=400, detail="请输入正确的邮箱格式")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    try:
        user = create_user(email, password)
        token = create_token(email)
        return {"token": token, "user": user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
async def login(body: LoginRequest):
    """登录：邮箱+密码。"""
    email = (body.email or "").strip()
    password = body.password or ""
    if not email or not password:
        raise HTTPException(status_code=400, detail="请输入邮箱和密码")
    if not verify_user(email, password):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=500, detail="用户数据异常")
    token = create_token(email)
    return {"token": token, "user": user}


@router.get("/me")
async def me(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    """获取当前登录用户信息。未登录返回 401。"""
    email = _get_current_email(credentials)
    if not email:
        raise HTTPException(status_code=401, detail="未登录")
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=401, detail="登录已失效")
    return user


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    """登出：使当前 token 失效。"""
    if credentials and credentials.credentials:
        delete_token(credentials.credentials)
    return {"ok": True}


@router.post("/upgrade")
async def upgrade(current_user: dict = Depends(get_current_user)):
    """（模拟）升级为付费用户：关闭付款码后前端调用，将当前用户设为付费。"""
    set_user_paid(current_user["email"])
    user = get_user_by_email(current_user["email"])
    return {"user": user}
