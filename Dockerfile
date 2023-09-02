FROM python:3.12.0rc1-alpine3.18

WORKDIR /app

COPY . ./

RUN pip install -r requirements.txt

ENTRYPOINT [ "python3", "-m", "hypercorn", "verify:app", "--bind", "0.0.0.0:1234"]
