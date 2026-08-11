from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.auth import create_session, create_user, current_user, delete_session, get_user_by_username, public_user, verify_password

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_\-]+$")
    display_name: str = Field(default="", max_length=40)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


@router.post("/auth/register")
def register(request: RegisterRequest) -> dict:
    user = create_user(
        username=request.username.strip(),
        display_name=request.display_name.strip() or request.username.strip(),
        password=request.password,
    )
    token = create_session(user["id"])
    return {"token": token, "user": public_user(user)}


@router.post("/auth/login")
def login(request: LoginRequest) -> dict:
    user = get_user_by_username(request.username.strip())
    if user is None or not verify_password(request.password, str(user["password_hash"])):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_session(user["id"])
    return {"token": token, "user": public_user(user)}


@router.get("/auth/me")
def me(user: dict = Depends(current_user)) -> dict:
    return {"user": public_user(user)}


@router.post("/auth/logout")
def logout(authorization: str = Header(default="")) -> dict[str, bool]:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        delete_session(token.strip())
    return {"ok": True}
