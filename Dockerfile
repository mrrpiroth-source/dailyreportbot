FROM python:3.11-slim

# Set timezone to Asia/Phnom_Penh
ENV TZ=Asia/Phnom_Penh
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose HTTP port for health check
EXPOSE 8080

CMD ["python", "main.py"]
