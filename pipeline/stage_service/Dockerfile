# Stage service image: the Python pipeline + JDK 17 + Maven + the MTL engines,
# behind the thin FastAPI wrapper that n8n calls.
#
# Build context is the REPOSITORY ROOT (the container needs engines/, benchmark/,
# workflows/, pipeline/, and the nested data project):
#
#   docker build -f pipeline/stage_service/Dockerfile -t llm4mtl-stage-service .
#
FROM maven:3.9-eclipse-temurin-17

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
RUN python3 -m pip install --no-cache-dir --break-system-packages -e "/app/pipeline[service]"

EXPOSE 8129
CMD ["python3", "-m", "uvicorn", "llm4mtl.stage_service.app:app", "--host", "0.0.0.0", "--port", "8129"]
