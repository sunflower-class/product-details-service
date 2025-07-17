FROM python:3.10.12-slim
ENV MODE=docker
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5001
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "5001"]
