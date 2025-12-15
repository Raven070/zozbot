# FILE: redis_client.py
import redis
from config import REDIS_HOST, REDIS_PORT, REDIS_DB

# Create a reusable connection pool
pool = redis.ConnectionPool(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

# The client instance that the rest of our app will use
redis_conn = redis.Redis(connection_pool=pool)

# A key name we will use to store the bot's state
BOT_STATE_KEY = "telegram_bot_enabled"