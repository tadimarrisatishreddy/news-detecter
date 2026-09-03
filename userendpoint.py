@app.get("/profile")

def profile(
    current_user=Depends(get_current_user)
):

    return current_user