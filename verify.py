
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from contextlib import asynccontextmanager
from common import (
    logger,
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


@app.post("/verify_email")
async def verify_email(email: Email) -> dict:
    steps = [
        deduplication_and_spam_removal,
        domain_validation,
        risk_validation,
        mta_validation,
        # check_email_deliverability
    ]
    domain = email.email.split('@')[1]
    for step in steps:
        is_valid, message = await step(email.email, domain)
        if not is_valid:
            return {"result": "invalid", "message": message}
    
    return {"result": "valid", "message": "Email is valid."}

