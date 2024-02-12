from fastapi import FastAPI
from fastapi.responses import FileResponse, ORJSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from brotli_asgi import BrotliMiddleware  # type: ignore
from pydantic import BaseModel, EmailStr
from contextlib import asynccontextmanager
from common import (
    logger,
    AsyncEmailCache,
    Tuple,
    MXRecord,
    deduplication_and_spam_removal,
    domain_validation,
    risk_validation,
    mta_validation,
    check_email_deliverability,
)

import sentry_sdk
import toml

sentry_sdk.init(
    dsn="https://ab18ed27c74dec467fdcab9eccf383b2\
        @o4505872417554432.ingest.sentry.io/4505872417751040",
    traces_sample_rate=0.25,
    profiles_sample_rate=0.25,
)

"""                VERSION INFO                """
VERSION: str = toml.load("pyproject.toml")["tool"]["poetry"]["version"]
logger.debug(f"Psync Version: {VERSION}")


##### MAIN APP########
class Email(BaseModel):
    email: EmailStr


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the FastAPI app
    logger.info(
        "[bold green blink]Trampoline is Starting Up![/]", extra={"markup": True}
    )
    yield
    # Clean up the ML models and release the resources
    logger.info(
        "[bold blue blink]Trampoline is Shutting Down Gracefully![/]",
        extra={"markup": True},
    )


origins = [
    "https://psync.dev",
    "https://psync.club",
    "https://psy.nc",
    "https://psync.app",
    "https://psyncapp.com",
    "https://thedating.club",
    "https://gsrikanth.cc",
]

trampoline = FastAPI(title="Trampoline", lifespan=lifespan)

# Enable CORS
trampoline.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,
)
# Enable Brotli compression
trampoline.add_middleware(BrotliMiddleware)

# Mount static files
trampoline.mount("/web", StaticFiles(directory="web"), name="landing")


@trampoline.get("/", include_in_schema=False)
async def root():
    """The root of the FastAPI app"""
    return FileResponse("web/index.html", status_code=200, media_type="text/html")


@trampoline.get("/favicon.ico")
async def favicon() -> FileResponse:
    return FileResponse("favicon.ico")


# Step 1: Create a new async function to handle the original email verification logic
async def process_email(email_address: str) -> Tuple[bool, str]:
    steps = [
        deduplication_and_spam_removal,
        domain_validation,
        risk_validation,
        mta_validation,
        check_email_deliverability,
    ]
    mx = MXRecord(email_address)
    for step in steps:
        is_valid, message = await step(mx)
        if not is_valid:
            return False, message

    return True, "Email is valid."


# Step 2: Initialize an instance of AsyncEmailCache with process_email as the awaitable
email_cache = AsyncEmailCache(process_email)


# Rate limit this using: https://slowapi.readthedocs.io/en/latest/
@trampoline.post("/verify_email")
async def verify_email(email: Email) -> ORJSONResponse:
    # Step 3: Update the verify_email route to use the cache
    is_valid: bool = False
    message: str = ""
    is_valid, message = await email_cache(email.email)  # type: ignore
    result = "valid" if is_valid else "invalid"
    return ORJSONResponse({"result": result, "message": message})
