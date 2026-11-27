# python imports
from typing import Annotated
import asyncio
# sqlalchemy imports
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
# fastapi imports
from fastapi import routing, Depends, HTTPException,status,Query
# app imports
from app.cache import get_or_set, invalidate_product
from app.cache_keys import product_key, product_list_key
from app.config import settings
from app.models import Product
from app.schemas import ProductOut, ProductCreate, ProductUpdate
from app.database import get_db
from app.circuit_breaker import breaker
# =====================================================================
router = routing.APIRouter()
# ====================================================================
product_ttl = 60  # Cache time-to-live in seconds

# endpoint to get product by id
@router.get('/{product_id}')
async def get_product(product_id:int, db:Annotated[AsyncSession, Depends(get_db)]):
   async def load():
      await asyncio.sleep(1)  # Simulate a delay for demonstration purposes
      product = await db.get(Product, product_id)
      return ProductOut.model_validate(product).model_dump() if product else None
   
   data,souce = await get_or_set(product_key(product_id),settings.ttl_product,load)
   if data is None:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
   return {"data": data, "source": souce}


@router.get('/')
async def list_products(
   db:Annotated[AsyncSession, Depends(get_db)],
   page:int=Query(1, ge=1),
   limit:int=Query(5,ge=1,le=50),
):
   async def load():
      # await asyncio.sleep(1)
      rows = await db.scalars(
         select(Product).offset((page-1)*limit).limit(limit)
         )
      return [ProductOut.model_validate(row).model_dump() for row in rows]
   
   data,source = await get_or_set(product_list_key(page,limit),settings.ttl_product,load)
   return {"data": data, "source": source}

@router.post('/',status_code=status.HTTP_201_CREATED)
async def create_product(
   body:ProductCreate,
   db:Annotated[AsyncSession, Depends(get_db)]
):
   product=Product(**body.model_dump())
   db.add(product)
   await db.commit()
   await db.refresh(product)
   await invalidate_product(product.id)

@router.put('/{product_id}')
async def update_product(
    product_id:int,
    body:ProductUpdate,
    db:Annotated[AsyncSession, Depends(get_db)],
):
   product = await db.get(Product, product_id)
   
   if product is None:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
   for field, value in body.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
   await db.commit()

   await invalidate_product(product.id)
   return ProductOut.model_validate(product).model_dump()

@router.delete('/{product_id}',status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id:int,
    db:Annotated[AsyncSession, Depends(get_db)],
):
   product = await db.get(Product, product_id)
   if product is None:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
   
   await db.delete(product)
   await db.commit()

   await invalidate_product(product_id)
