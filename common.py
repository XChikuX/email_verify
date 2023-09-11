from typing import Tuple
import dns.resolver
from disposable_email_domains import blocklist
import smtplib
import socket
import logging
from rich.logging import RichHandler

FORMAT = "[<->] %(asctime)s |%(process)d| %(message)s"

logging.basicConfig(
    level="NOTSET",
    format=FORMAT,
    datefmt="%Y-%m-%d %H:%M:%S %z",
    handlers=[RichHandler()],
)

logger = logging.getLogger("rich")


async def deduplication_and_spam_removal(email: str, domain: str) -> Tuple[bool, str]:
    if domain in blocklist:
        return False, "Email domain is in the blocklist of invalid, disposable emails."
    return True, ""

async def domain_validation(email: str, domain: str) -> Tuple[bool, str]:
    
    try:
        dns.resolver.resolve(domain, 'A')
        return True, ""
    except dns.resolver.NXDOMAIN:
        return False, "DNS entry not found for the domain."

async def risk_validation(email: str, domain: str) -> Tuple[bool, str]:
    
    # Replace with your high-risk email database check
    return True, ""

async def mta_validation(email: str, domain: str) -> Tuple[bool, str]:
    
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        for mx in mx_records:  # type: ignore
            if mx.preference == 0:
                return False, "Catch-all address detected."
        return True, ""
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return False, "MX record not found for the domain."

async def check_email_deliverability(email: str, domain: str) -> Tuple[bool, str]:
    mx_records = dns.resolver.resolve(domain, 'MX')
    for mx in mx_records:  # type: ignore
        # Extracting the exchange attribute from the mx object
        mail_server = str(mx.exchange).rstrip('.')
        logger.info(f"Pinging: {mail_server}")
        if await network_calls(mail_server, email):
            return True, ""
    return False, "Email address is not deliverable."

async def network_calls(mx, email, timeout=3):
    ''' Utility function to make network calls to verify email address '''
    result = False
    try:
        smtp = smtplib.SMTP(mx, timeout=timeout)
        status, _ = smtp.ehlo()
        if status >= 400:
            smtp.quit()
            logger.debug(f'{mx} answer: {status} - {_}\n')
            return False
        smtp.mail('')
        status, _ = smtp.rcpt(email)
        if status >= 400:
            logger.debug(f'{mx} answer: {status} - {_}\n')
            result = False
        if status >= 200 and status <= 250:
            result = True

        logger.debug(f'{mx} answer: {status} - {_}\n')
        smtp.quit()

    except smtplib.SMTPServerDisconnected:
        logger.debug(f'Server does not permit verify user, {mx} disconnected.\n')
    except smtplib.SMTPConnectError:
        logger.debug(f'Unable to connect to {mx}.\n')
    except socket.timeout as e:
        logger.debug(f'Timeout connecting to server {mx}: {e}.\n')
        return None
    except socket.error as e:
        logger.debug(f'ServerError or socket.error exception raised {e}.\n')
        return None

    return result