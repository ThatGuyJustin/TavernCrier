import yaml
from peewee import Model, OP
from playhouse.postgres_ext import PostgresqlExtDatabase

with open('./config.yaml', 'r') as config:
    raw_config = yaml.load(config.read(), Loader=yaml.FullLoader)

postgres_db = PostgresqlExtDatabase(
    raw_config['database_info']['postgres']['database'],
    host=raw_config['database_info']['postgres']['host'],
    user=raw_config['database_info']['postgres']['username'],
    password=raw_config['database_info']['postgres']['password']
)

REGISTERED_MODELS = []


class PostgresBase(Model):
    class Meta:
        database = postgres_db

    @staticmethod
    def register(cls):
        cls.create_table(True)
        if hasattr(cls, 'SQL'):
            postgres_db.execute_sql(cls.SQL)

        REGISTERED_MODELS.append(cls)
        return cls


def init_db(env):
    # TODO: Setup later!
    pass
