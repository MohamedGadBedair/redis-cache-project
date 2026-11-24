from pydantic import BaseModel, ConfigDict, Field

class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:int
    name:str
    price:float
    stock:int

class ProductCreate(BaseModel):
    name:str =Field(max_length=100,min_length=1)
    price:float = Field(gt=0)
    stock:int = Field(ge=0)

class ProductUpdate(BaseModel):
    name:str | None =Field(default=None,max_length=100,min_length=1)
    price:float | None = Field(default=None,gt=0)
    stock:int | None = Field(default=None,ge=0)
