# python imports
from typing import Annotated
import asyncio
# sqlalchemy imports
from sqlalchemy.ext.asyncio import AsyncSession
# fastapi imports
from fastapi import routing, Depends, HTTPException,status
# app imports
from app.models import Product
from app.schemas import ProductOut
from app.cache import cache_get, cache_set
from app.database import get_db
# =====================================================================
router = routing.APIRouter()
# ====================================================================
@router.get('/products/{product_id}')
async def get_product(product_id:int, db:Annotated[AsyncSession, Depends(get_db)]):
    key = f'product:{product_id}'

    cache_data = await cache_get(key)
    if cache_data is not None:
        return {'source':'cache','data':cache_data}
    
    await asyncio.sleep(1)  # Simulate a delay for database query
    product= await db.get(Product,product_id)

    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    data = ProductOut.model_validate(product).model_dump()
    await cache_set(key, data)
    return{'source':'database','data':data}
