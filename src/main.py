from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from core.config import settings
from core.logger import log_uvicorn
from api import main_router
from lifespan_app import Lifespan

lifespan_app = Lifespan()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await lifespan_app.startup()
    log_uvicorn.info("Start application!")
    yield
    await lifespan_app.shutdown()
    log_uvicorn.info("Terminated. Good day!")

app = FastAPI(title="Session-Auth-Service", lifespan=lifespan)

origins = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]
app.add_middleware(
    CORSMiddleware, # для корректной работы с фронтэндом, нужно именно для бразера, т.к. при отправке запроса из браузера, ему необходимо убедиться, что запрос поступает от доверенного источника
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(main_router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.runtime.host,
        port=settings.runtime.port,
        reload=settings.runtime.reload,
    )
