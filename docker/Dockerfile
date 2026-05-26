FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -e ".[all]"
COPY . .

EXPOSE 8000
CMD ["python", "-m", "emerald_exchange"]
