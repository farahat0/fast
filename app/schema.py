from pydantic import BaseModel  
from fastapi_users import schemas
import uuid
#this is the schema for the post data that we will use to create a post and return the post data as response
class PostCreate(BaseModel):  
    title: str  
    content: str  

class UserRead(schemas.BaseUser[uuid.UUID]):
    pass
class UserCreate(schemas.BaseUserCreate):
    pass
class UserUpdate(schemas.BaseUserUpdate):
    pass