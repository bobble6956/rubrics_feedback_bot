# Use an official lightweight Python image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED True

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the rest of your application code (app.py and templates folder)
COPY . .

# Expose the port Gunicorn will run on
EXPOSE 8080

# Command to run the application using Gunicorn
# This tells Gunicorn to run the 'app' variable (Flask app)
# inside the 'app' file (app.py)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "120", "app:app"]