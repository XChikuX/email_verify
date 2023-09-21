
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from contextlib import asynccontextmanager
from common import (
    logger,
    AsyncEmailCache,
    Tuple,
    deduplication_and_spam_removal,
    domain_validation,
    risk_validation,
    mta_validation,
    check_email_deliverability
)


import sentry_sdk
sentry_sdk.init(
    dsn="https://fe6d70b9d474c1d27e46b48a72cd4593\
        @o4504830500012032.ingest.sentry.io/4505820941254656",
    traces_sample_rate=0.25,
    profiles_sample_rate=0.25,
)




##### MAIN APP########
class Email(BaseModel):
    email: EmailStr

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the FastAPI app
    logger.info("[bold green blink]Server is Starting Up![/]", extra={"markup": True})
    yield
    # Clean up the ML models and release the resources
    logger.info(
        "[bold blue blink]Server is Shutting Down Gracefully![/]",
        extra={"markup": True},
    )

app = FastAPI(title="Email Verify", lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/favicon.ico")
async def favicon() -> FileResponse:
    return FileResponse("favicon.ico")


# Step 1: Create a new async function to handle the original email verification logic
async def process_email(email_address: str) -> Tuple[bool, str]:
    domain = email_address.split('@')[1]
    steps = [
        deduplication_and_spam_removal,
        domain_validation,
        risk_validation,
        mta_validation,
        check_email_deliverability
    ]
    
    for step in steps:
        is_valid, message = await step(email_address, domain)
        if not is_valid:
            return False, message
    
    return True, "Email is valid."

# Step 2: Initialize an instance of AsyncEmailCache with process_email as the awaitable
email_cache = AsyncEmailCache(process_email)

@app.post("/verify_email")
async def verify_email(email: Email) -> dict:
    # Step 3: Update the verify_email route to use the cache
    is_valid:bool = False
    message: str = ""
    is_valid, message = await email_cache(email.email) # type: ignore
    result = "valid" if is_valid else "invalid"
    return {"result": result, "message": message}