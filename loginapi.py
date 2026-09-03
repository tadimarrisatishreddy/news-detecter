@app.post("/login")
def login(data: UserLogin, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.email == data.email).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid Email")

    if not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid Password")

    return {
        "message": "Login Successful"
    }