from pydantic import BaseModel, ConfigDict

class ProductOut(BaseModel):
    id:int
    name:str
    price:float
    stock:int