from collections.abc import AsyncGenerator
import uuid
from click import argument
from fastapi import Depends
from sqlalchemy import Column, String, Text , DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime
from fastapi_users.db import SQLAlchemyUserDatabase, SQLAlchemyBaseUserTableUUID


DATABASE_URL="sqlite+aiosqlite:///./test.db"


class base(DeclarativeBase):
    pass

class User(SQLAlchemyBaseUserTableUUID, base):
    posts = relationship("post", back_populates="user")

class post(base):
    __tablename__= "posts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    caption= Column(Text)
    url= Column(String,nullable=False)
    file_type= Column(String,nullable=False)
    created_at= Column(DateTime, default=datetime.utcnow)
    file_name= Column(String, nullable=False)
    user = relationship("User", back_populates="posts")

#create the database engine and session
engine=create_async_engine(DATABASE_URL)
#create the session maker
async_session= async_sessionmaker(engine, expire_on_commit=False)
#create the database table

async def create_db_table():
    async with engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all) 
#give you the ablity to get the session and close it after use
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session

async def get_user_db(session: AsyncSession=Depends(get_session)):
    yield SQLAlchemyUserDatabase(session, User) 