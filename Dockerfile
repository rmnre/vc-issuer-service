FROM python:3.10.10-alpine3.17 as build

WORKDIR /usr/app
RUN python -m venv /usr/app/venv
ENV PATH="/usr/app/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt

FROM python:3.10.10-alpine3.17@sha256:184186aa66d3a18c1ead6436c112aaf6516b9db846ce69742c632803efe013b5

RUN addgroup -g 111 python && \
    adduser -SHD -u 111 -G python python

RUN mkdir /usr/app && chown python:python /usr/app
WORKDIR /usr/app

COPY --chown=python:python --from=build /usr/app/venv ./venv
COPY --chown=python:python . ./

USER 111

ENV PATH="/usr/app/venv/bin:$PATH"
ENTRYPOINT ["python", "-OO","-m", "issuer_service"]
HEALTHCHECK --interval=5m --timeout=10s --start-period=5s --retries=3 \
 CMD wget -q --tries=1 --spider http://localhost:4567/health || exit 1
