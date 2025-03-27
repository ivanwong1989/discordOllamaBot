# Deriving the latest base image
FROM python:latest

# Setting working directory
WORKDIR /usr/src/app

# Copying the test.py file to the container's working directory
COPY . /usr/src/app

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Running the Python script
CMD ["sh", "-c", "python runOllamaPython.py & python runFluxPython.py && wait"]