"""The endpoint the evaluation service calls, once per game tick.

You should not need to change much in here. Put your agent in ``example.py``
and leave the transport alone.

The URL you submit is used exactly as you give it, path included, so if you
keep the ``/predict`` route below then submit ``http://<your-host>:9055/predict``
rather than just the host.
"""

import datetime
import logging
import time

import uvicorn
from fastapi import FastAPI

from dtos import RobotRobbersPredictRequestDto, RobotRobbersPredictResponseDto
from example import predict
from utils import validate_moves

HOST = '0.0.0.0'
PORT = 9055

# Log every this many ticks. A line per tick is 3000 lines a game, and
# printing them costs time you are being timed on.
LOG_EVERY_N_TICKS = 100

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
start_time = time.time()


# A plain `def`, not `async def`: FastAPI runs it in a thread pool, so a slow
# agent does not block the server. Make it `async` only if your agent is.
@app.post('/predict', response_model=RobotRobbersPredictResponseDto)
def predict_endpoint(request: RobotRobbersPredictRequestDto):
    """Answer one tick."""
    response = predict(request)

    # Fail here, loudly, rather than having the service quietly play the tick
    # with no moves. Every rule this checks is one the service enforces.
    validate_moves(response.moves)

    if request.game_ticks % LOG_EVERY_N_TICKS == 0 or request.is_terminal:
        logger.info(
            'tick %s: total reward %s%s',
            request.game_ticks,
            request.total_reward,
            ' (last tick)' if request.is_terminal else '',
        )
    return response


@app.get('/api')
def hello():
    return {
        'service': 'robot-robbers-usecase',
        'uptime': '{}'.format(datetime.timedelta(seconds=time.time() - start_time)),
    }


@app.get('/')
def index():
    return "Your endpoint is running!"


if __name__ == '__main__':
    # No access log: it would print one line per tick.
    uvicorn.run('api:app', host=HOST, port=PORT, access_log=False)
