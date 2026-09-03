from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dependencies import get_db, get_current_user
from models import User
from schemas import NewsInput


router = APIRouter(
    prefix="/news",
    tags=["News Input & NLP"]
)


@router.post("/submit")
def submit_news(
    news: NewsInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return {
        "message": "News submitted successfully",
        "user": current_user.username,
        "news_text": news.text
    }