from typing import Tuple
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
import dns.resolver
from disposable_email_domains import blocklist


import sentry_sdk
sentry_sdk.init(
    dsn="https://fe6d70b9d474c1d27e46b48a72cd4593\
        @o4504830500012032.ingest.sentry.io/4505820941254656",
    traces_sample_rate=0.25,
    profiles_sample_rate=0.25,
)


async def deduplication_and_spam_removal(email: EmailStr, domain: str) -> Tuple[bool, str]:
    if domain in blocklist:
        return False, "Email domain is in the blocklist of invalid, disposable emails."
    return True, ""

async def domain_validation(email: EmailStr, domain: str) -> Tuple[bool, str]:
    
    try:
        dns.resolver.resolve(domain, 'A')
        return True, ""
    except dns.resolver.NXDOMAIN:
        return False, "DNS entry not found for the domain."

async def risk_validation(email: EmailStr, domain: str) -> Tuple[bool, str]:
    
    # Replace with your high-risk email database check
    return True, ""

async def mta_validation(email: EmailStr, domain: str) -> Tuple[bool, str]:
    
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        for mx in mx_records:  # type: ignore
            if mx.preference == 0:
                return False, "Catch-all address detected."
        return True, ""
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return False, "MX record not found for the domain."



##### MAIN APP########

class Email(BaseModel):
    email: EmailStr

app = FastAPI()

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

