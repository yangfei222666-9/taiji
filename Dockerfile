FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TAIJI_ENABLE_EXTERNAL_API=false

WORKDIR /app

RUN python -m pip install --upgrade pip

COPY . /app

RUN python -m pip install -e .

EXPOSE 8501

CMD ["python", "examples/demo_app.py"]
