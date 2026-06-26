FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY dashboard ./dashboard

RUN mkdir -p /srv/artifacts/models

# Hugging Face Spaces expects port 7860; we serve Streamlit there.
# FastAPI runs alongside on 8000 for local Docker users (HF only exposes 7860).
EXPOSE 7860 8000

# Idempotent bootstrap: generate data + train if artifacts missing, then start
# both processes. Streamlit on 7860 is the public surface; FastAPI on 8000 is
# local-only when run via plain Docker.
CMD ["bash", "-lc", "\
    [ -f artifacts/rms.db ] || (python -m app.data.generator && python -m app.train.train_base && python -m app.train.init_sgd) && \
    uvicorn app.main:app --host 0.0.0.0 --port 8000 & \
    streamlit run dashboard/streamlit_app.py --server.port 7860 --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false \
"]
