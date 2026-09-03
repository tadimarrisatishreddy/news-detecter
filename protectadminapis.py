@app.get("/admin/users")

def get_all_users(
    current_user=Depends(admin_required),
    db: Session=Depends(get_db)
):

    return db.query(User).all()