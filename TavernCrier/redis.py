import redis

from TavernCrier import config

rdb = redis.Redis(host=config.database_info['redis']['host'], port=config.database_info['redis']['port'],
                  db=config.database_info['redis']['db'], decode_responses=True)
