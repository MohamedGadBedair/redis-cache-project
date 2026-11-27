# async context manager imports
from contextlib import asynccontextmanager
import asyncio
# fastapi imports
from fastapi import FastAPI
# sqlalchemy imports
from sqlalchemy import select, func
# app imports
from app.database import Base, SessionLocal, engine
from app.redis_client import redis_client
from app.circuit_breaker import breaker
# routers imports
from app.routers import products

# ====================================================================
# app lifespan event to check redis connection and close it on shutdown
@asynccontextmanager
async def lifespan(app:FastAPI):
    # create the database tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # check if the database is connected
    async with SessionLocal() as session:
        try:
            await session.execute(select(func.now()))
            print('Database is connected')
        except Exception as e:
            print('Database is not connected')
            print(e)
    # check if the redis is connected
    try: 
        await redis_client.ping()
        print('Redis is connected')
    except Exception as e:
        print('Redis is not connected')
        print(e)
    yield 
    await redis_client.close()

# create the FastAPI app with the lifespan event
app = FastAPI(lifespan=lifespan)    
# ====================================================================
# include the routers
app.include_router(products.router, prefix="/products", tags=["products"])
# ================================================================
# health check endpoint
@app.get("/health")
async def health():
    try:
        await asyncio.wait_for(redis_client.ping(), timeout=1)
        redis_status='ok'
    except Exception:
        redis_status = 'down'
    return {"app":'ok',"redis":redis_status ,"circuit":breaker.state.value}
    
