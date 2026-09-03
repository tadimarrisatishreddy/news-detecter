from main import User


@app.get("/profile")

def profile(current_user=Depends(get_current_user)):

    return {
        "message":"Welcome",
        "user":current_user
    }
