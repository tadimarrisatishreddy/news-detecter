from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    full_name: str
    username: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str
from pydantic import BaseModel, EmailStr, Field


# -------------------------
# USER REGISTRATION
# -------------------------

class UserRegister(BaseModel):

    full_name: str

    username: str

    email: EmailStr

    password: str


# -------------------------
# USER LOGIN
# -------------------------

class UserLogin(BaseModel):

    username: str

    password: str


# -------------------------
# NEWS INPUT
# -------------------------

class NewsInput(BaseModel):

    news_text: str = Field(
        ...,
        min_length=20,
        max_length=10000,
        description="News article or claim to analyze"
    )