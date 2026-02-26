from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from app.schema import PostCreate
from app.db import post, create_db_table, get_session
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy import select
from app.images import imagekit
import shutil
import os
import uuid
import tempfile


# create a lifespan function to create the database table when the app starts and close the connection when the app stops
@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_table()
    yield


# when the app starts it will create the database table and when the app stops it will close the connection
app = FastAPI(lifespan=lifespan)
# above is the code to create the database table when the app starts and close the connection when the app stops


# to create a post endpoint to upload a file and save the post data in the database and return the post data as response
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
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
        upload_result = imagekit.files.upload(
            file=open(temp_file_path, "rb"),
            file_name=file.filename,
            use_unique_file_name=True,
            tags=["backend upload"],
        )

        # treggre other function to run after this function is done #used db in this function):
        post2 = post(
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
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        file.file.close()


# return the post data as response
@app.get("/feed")
async def get_feed(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(post).order_by(post.created_at.desc()))
    posts = [row[0] for row in result.all()]
    post_data = []
    for post3 in posts:
        post_data.append(
            {
                "id": str(post3.id),
                "caption": post3.caption,
                "url": post3.url,
                "file_type": post3.file_type,
                "file_name": post3.file_name,
                "created_at": post3.created_at,
            }
        )
    return {"posts": post_data}
