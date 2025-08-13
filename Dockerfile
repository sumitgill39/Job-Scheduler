# Use Windows Server Core with Python
FROM python:3.10-windowsservercore-ltsc2022

WORKDIR /app

# Copy project files
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r "Job Scheduler/requirements.txt"

# Set default command
CMD ["python", "Job Scheduler/main.py"]
