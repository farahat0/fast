from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from app.schema import PostCreate
from app.db import post, create_db_table, get_session, User
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy import select
from app.images import imagekit
import shutil
import os
import uuid
import tempfile
from sqlalchemy import delete
from app.users import auth_backend, fastapi_users, current_active_user
from app.schema import UserRead, UserCreate, UserUpdate


# create a lifespan function to create the database table when the app starts and close the connection when the app stops
@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_table()
    yield


# when the app starts it will create the database table and when the app stops it will close the connection
app = FastAPI(lifespan=lifespan)
# above is the code to create the database table when the app starts and close the connection when the app stops
app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])
app.include_router(
    fastapi_users.get_reset_password_router(), prefix="/auth", tags=["auth"]
)
app.include_router(
    fastapi_users.get_verify_router(UserRead), prefix="/auth", tags=["auth"]
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

# linking the auth router to the app with the prefix /auth/jwt and the tag auth


# to create a post endpoint to upload a file and save the post data in the database and return the post data as response
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user: User=Depends(current_active_user),
    caption: str = Form(""),
    session: AsyncSession = Depends(get_session),
):

    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(file.filename)[1]
        ) as temp_file:
            temp_file_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)

        # ImageKit v5+ syntax: upload options are passed directly as arguments
        # Using "with open" prevents the WinError 32 (file being used by another process)
        with open(temp_file_path, "rb") as f:
            upload_result = imagekit.files.upload(
                file=f,
                file_name=file.filename,
                use_unique_file_name=True,
                tags=["backend upload"],
            )

        # treggre other function to run after this function is done #used db in this function):
        post2 = post(
            user_id=user.id,
            caption=caption,
            url=upload_result.url,
            file_type="video" if file.content_type.startswith("video") else "image",
            file_name=upload_result.name,
        )
        session.add(post2)
        await session.commit()
        await session.refresh(post2)
        return post2
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Close FastAPI's file handle first so Windows releases its lock
        file.file.close()
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except PermissionError:
                pass


# return the post data as response
@app.get("/feed")
async def get_feed(session: AsyncSession = Depends(get_session), user: User=Depends(current_active_user)):
    result = await session.execute(select(post).order_by(post.created_at.desc()))
    posts = [row[0] for row in result.all()]
    result_by_mail= await session.execute(select(User))
    users = [row[0] for row in result_by_mail.all()]
    user_dict = {u.id: u.email for u in users}
    post_data = []
    for post3 in posts:
        post_data.append(
            {
                "id": str(post3.id),
                "caption": post3.caption,
                "user_id": str(post3.user_id),
                "url": post3.url,
                "file_type": post3.file_type,
                "file_name": post3.file_name,
                "created_at": post3.created_at,
                "is_owner": post3.user_id == user.id,  # Add this field to indicate if the current user is the owner of the post    
                "user_email": user_dict.get(post3.user_id, "Unknown")
            }
        )
    return {"posts": post_data}


"""''
@app.delete("/delete/{id}")
async def delete_post(id: str, session: AsyncSession = Depends(get_session)):
    try:
        uuid_id = uuid.UUID(id)
        result = await session.execute(select(post).where(post.id == uuid_id))
        post_to_delete = result.scalar.first()

        if not post_to_delete:
            raise HTTPException(status_code=404, detail="Post not found")
        await session.delete(post_to_delete)
        await session.commit()

        return {"detail": "Post deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
""" ""


@app.delete("/delete/{post_id}")
async def delete_post(post_id: str, session: AsyncSession = Depends(get_session), user: User=Depends(current_active_user)):
    try:
        # FIX: Convert the string post_id from the URL into a UUID object
        try:
            target_uuid = uuid.UUID(post_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid UUID format")

        # 1. Fetch the post using the UUID object
        result = await session.execute(select(post).where(post.id == target_uuid))
        db_post = result.scalar_one_or_none()

        if not db_post:
            raise HTTPException(status_code=404, detail="Post not found")
        if db_post.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this post")
        # 2. Delete from ImageKit using the stored file_name/ID
        try:
            # ImageKit v5 deletion syntax
            imagekit.files.delete(file_id=db_post.file_name)
        except Exception as ik_e:
            print(f"ImageKit cleanup skipped or failed: {ik_e}")

        # 3. Delete the record from the database
        await session.delete(db_post)
        await session.commit()

        return {"message": "Post deleted successfully"}

    except Exception as e:
        await session.rollback()
        # This will now capture the specific error if it fails again
        raise HTTPException(status_code=500, detail=str(e))
