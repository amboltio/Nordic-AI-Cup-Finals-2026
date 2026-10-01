FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Your agent and the server. The game itself is not needed to serve: the
# evaluation service runs the game and only asks you for moves.
COPY dtos.py utils.py example.py api.py ./

EXPOSE 9055

CMD ["python", "api.py"]
