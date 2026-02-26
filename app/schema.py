from pydantic import BaseModel  
#this is the schema for the post data that we will use to create a post and return the post data as response
class PostCreate(BaseModel):  
    title: str  
    content: str  
   