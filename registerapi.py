@app.post("/register")
def register(user: UserRegister, db: Session = Depends(get_db)):

    hashed_password = hash_password(user.password)

    new_user = User(
        full_name=user.full_name,
        username=user.username,
        email=user.email,
        password=hashed_password,
        role="user"
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "User registered successfully"
    }