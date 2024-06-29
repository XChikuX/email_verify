from typing import Tuple, Dict, Callable, Awaitable
import dns.asyncresolver as DNSResolver
import dns.resolver as DNS
import asyncwhois  # type: ignore
from disposable_email_domains import blocklist
import aiosmtplib
import asyncio
import logging
from rich.logging import RichHandler
import anyio
import pendulum

FORMAT = "[<->] %(asctime)s |%(process)d| %(message)s"

logging.basicConfig(
    level="DEBUG",
    format=FORMAT,
    datefmt="%Y-%m-%d %H:%M:%S %z",
    handlers=[RichHandler()],
)

logger = logging.getLogger("rich")


class MXRecord:
    def __init__(self, email_address: str):
        self.email = email_address
        self.domain = email_address.split("@")[1]
        self.records: DNS.Answer = None  # type: ignore

    async def resolve(self):
        # Check if the records are already resolved
        if not self.records:
            try:
                mx_records = await DNSResolver.resolve(self.domain, "MX")
            except (DNS.NXDOMAIN, DNS.NoAnswer, DNS.LifetimeTimeout):
                logger.error("DNS entry not found for the domain.")
            else:
                # Prioritize the MX records in the middle of the list
                mx_records = sorted(mx_records, key=lambda x: x.preference)  # type: ignore
                mid_index = len(mx_records) // 2
                self.records = mx_records[mid_index - 1 : mid_index + 2]


# Tiered Cache
class AsyncEmailCache:
    def __init__(self, awaitable: Callable[..., Awaitable], hours: int = 8):
        self._awaitable = awaitable
        self._cache: Dict[str, Dict[str, bool]] = {}  # {domain: {email: is_valid}}
        self._cache_time: int = hours
        self._timestamps: Dict[
            str, Dict[str, pendulum.DateTime]
        ] = {}  # {domain: {email: timestamp}}
        self._lock = anyio.Lock()

    async def __call__(self, email: str) -> bool:
        domain = email.split("@")[-1]
        async with self._lock:
            if domain not in self._cache:
                # Keep Track of the failure rate for each domain
                # If the failure rate is high, then we can add a PR to the blocklist
                self._cache[domain] = {}
                self._timestamps[domain] = {}

            # Check if the email is in the cache and not older than 8 hours
            if email not in self._cache[domain] or pendulum.now() - self._timestamps[
                domain
            ].get(email, pendulum.now()) > pendulum.duration(hours=self._cache_time):
                # If not, then verify the email
                is_valid = await self._awaitable(email)
                self._cache[domain][email] = is_valid
                self._timestamps[domain][email] = pendulum.now()
            return self._cache[domain][email]

    def invalidate(self, email: str):
        domain = email.split("@")[-1]
        if domain in self._cache and email in self._cache[domain]:
            del self._cache[domain][email]
            del self._timestamps[domain][email]


# Function to calculate the age of the domain
async def calculate_domain_age(domain_name) -> int:
    "TODO: Fix some issue in this"
    domain_info = await asyncwhois.aio_whois(domain_name)
    # Get the creation date
    logger.info(domain_info)
    creation_date = domain_info["created"]  # <------ FIX THIS
    # If the creation_date is a list (multiple values), take the first one
    if isinstance(creation_date, list):
        creation_date = creation_date[0]
    # Calculate the age
    current_date = pendulum.now("UTC")
    age = int(current_date.diff(creation_date).in_years())
    return age  # Return the age in years


async def deduplication_and_spam_removal(mx: MXRecord) -> Tuple[bool, str]:
    if mx.domain in blocklist:
        return False, "Email domain is in the blocklist of invalid, disposable emails."
    return True, ""


async def domain_validation(mx: MXRecord) -> Tuple[bool, str]:
    try:
        await DNSResolver.resolve(mx.domain, "A")
        # TODO: FIX THIS
        # if await calculate_domain_age(mx.domain) < 1:
        #     return False, "Domain is less than 1 year old."
        return True, ""
    except (DNS.NXDOMAIN, DNS.LifetimeTimeout, DNSResolver.NoAnswer):
        return False, "DNS entry not found for the domain."


async def risk_validation(mx: MXRecord) -> Tuple[bool, str]:
    # Replace with your high-risk email database check
    return True, ""


async def mta_validation(mx: MXRecord) -> Tuple[bool, str]:
    await mx.resolve()
    for mx in mx.records:  # type: ignore
        if mx.preference == 0:  # type: ignore
            return False, "Catch-all address detected."
    return True, ""


async def check_email_deliverability(MX: MXRecord) -> Tuple[bool, str]:
    await MX.resolve()
    for mx in MX.records:  # type: ignore
        # Extracting the exchange attribute from the mx object
        mail_server = str(mx.exchange).rstrip(".")  # type: ignore
        logger.debug(f"Pinging: {mail_server}")
        if await network_calls(mail_server, MX.email):
            return True, ""
    return False, "Email address is not deliverable."


async def network_calls(mx, email, port=25, timeout=3, use_tls=False):
    """Utility function to make network calls to verify email address"""
    result = False
    try:
        smtp = aiosmtplib.SMTP(hostname=mx, port=port, timeout=timeout, use_tls=use_tls)
        await smtp.connect()
        status, _ = await smtp.ehlo()
        if status >= 400:
            await smtp.quit()
            logger.debug(f"{mx} answer: {status} - {_}\n")
            return False
        await smtp.mail("")

        # Upgrade the connection to TLS using STARTTLS
        if port == 587:
            logger.info("Upgrading connection to TLS")
            starttls_response = await smtp.starttls(validate_certs=False)
            # starttls_response = await smtp.starttls()
            if starttls_response.code != 220:
                await smtp.quit()
                logger.debug(
                    f"{mx} answer: {starttls_response.code} - {starttls_response.message}\n"
                )
                return False

        status, _ = await smtp.rcpt(email)
        if status >= 400:
            logger.debug(f"{mx} answer: {status} - {_}\n")
            result = False
        if status >= 200 and status <= 250:
            result = True

        logger.debug(f"{mx} answer: {status} - {_}\n")
        await smtp.quit()

    except aiosmtplib.SMTPRecipientRefused:
        logger.debug(f"{mx} refused recipient.\n")
    except aiosmtplib.SMTPRecipientsRefused:
        logger.debug(f"{mx} refused multiple recipients.\n")
    except aiosmtplib.SMTPHeloError:
        logger.debug(f"{mx} refused HELO.\n")
    except aiosmtplib.SMTPSenderRefused:
        logger.debug(f"{mx} refused sender.\n")
    except aiosmtplib.SMTPServerDisconnected:
        logger.debug(f"Server does not permit verify user, {mx} disconnected.\n")
    except aiosmtplib.SMTPConnectError as e:
        logger.debug(f"Unable to connect to {mx}.\n {e}")

    #     smtp = smtplib.SMTP(mx, port=port, timeout=timeout)
    #     status, _ = smtp.ehlo()
    #     if status >= 400:
    #         smtp.quit()
    #         logger.debug(f"{mx} answer: {status} - {_}\n")
    #         return False

    #     # Upgrade the connection to TLS using STARTTLS
    #     if port == 587:
    #         status, _ = smtp.starttls()
    #         if status != 220:
    #             smtp.quit()
    #             logger.debug(f"{mx} answer: {status} - {_}\n")
    #             return False

    #     smtp.mail("")
    #     status, _ = smtp.rcpt(email)
    #     if status >= 400:
    #         logger.debug(f"{mx} answer: {status} - {_}\n")
    #         result = False
    #     if status >= 200 and status <= 250:
    #         result = True

    #     logger.debug(f"{mx} answer: {status} - {_}\n")
    #     smtp.quit()

    # except smtplib.SMTPRecipientsRefused:
    #     logger.debug(f"{mx} refused recipient.\n")
    # except smtplib.SMTPHeloError:
    #     logger.debug(f"{mx} refused HELO.\n")
    # except smtplib.SMTPSenderRefused:
    #     logger.debug(f"{mx} refused sender.\n")
    # except smtplib.SMTPServerDisconnected:
    #     logger.debug(f"Server does not permit verify user, {mx} disconnected.\n")
    # except smtplib.SMTPConnectError:
    #     logger.debug(f"Unable to connect to {mx}.\n")
    # except socket.timeout as e:
    #     logger.debug(f"Timeout connecting to server {mx}: {e}.\n")
    #     return None
    # except socket.error as e:
    #     logger.debug(f"ServerError or socket.error exception raised {e}.\n")
    #     return None

    return result


async def send_mail_async():
    # Test the email address
    import ssl

    # Create a custom SSL context
    context = ssl.create_default_context()

    # If you need to trust a custom CA or a self-signed certificate
    context.load_verify_locations(cafile="./ssl/psync.club.crt")

    # If the server requires client authentication
    context.load_cert_chain(
        certfile="./ssl/cert_chain.crt", keyfile="./ssl/psync.club.pem"
    )
    async with aiosmtplib.SMTP(
        hostname="alt1.gmail-smtp-in.l.google.com",
        port=587,
        use_tls=True,
        timeout=3,
        tls_context=context,
    ) as smtp:
        await smtp.connect()
        await smtp.starttls()
        status, _ = await smtp.ehlo()
        if status >= 400:
            await smtp.quit()
            print(f"answer: {status} - {_}\n")
            smtp.close()
            return False
        await smtp.mail("")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.gather(send_mail_async()))
    loop.close()
