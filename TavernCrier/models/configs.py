from peewee import AutoField, BigIntegerField, TextField
from playhouse.postgres_ext import JSONField, ArrayField

from TavernCrier import GuildConfig, StreamNotificationsConfig
from TavernCrier.db import PostgresBase


class StreamConfigField(JSONField):
    disco_model = None

    def db_value(self, value):
        if isinstance(value, StreamNotificationsConfig):
            return super(StreamConfigField, self).db_value(value.to_dict())
        if isinstance(value, dict):
            return super(StreamConfigField, self).db_value(value)
        if self.disco_model:
            return super(StreamConfigField, self).db_value(self.disco_model.inplace_update(value))
        else:
            return super(StreamConfigField, self).db_value(value)

    def python_value(self, value):
        if value is None:
            return super(StreamConfigField, self).python_value(value)
        if not self.disco_model:
            self.disco_model = StreamNotificationsConfig(value)
        return self.disco_model


class GuildConfigField(JSONField):
    disco_model = None

    def db_value(self, value):
        if isinstance(value, GuildConfig):
            return super(GuildConfigField, self).db_value(value.to_dict())
        if self.disco_model:
            return super(GuildConfigField, self).db_value(self.disco_model.to_dict())
        else:
            return super(GuildConfigField, self).db_value(value)

    def python_value(self, value):
        if not self.disco_model:
            self.disco_model = GuildConfig(value)
        return self.disco_model


@PostgresBase.register
class GuildConfigs(PostgresBase):
    class Meta:
        table_name = 'guild_configs'

    guild_id = BigIntegerField(primary_key=True)
    config = GuildConfigField(default=GuildConfig().to_dict())


@PostgresBase.register
class StreamConfigs(PostgresBase):
    class Meta:
        table_name = 'stream_configs'

    id = AutoField()
    guild_id = BigIntegerField()
    notification_channel = BigIntegerField()
    notification_role = BigIntegerField(null=True)
    streamer_id = BigIntegerField()
    streamer_name = TextField()
    config = StreamConfigField(default={})
    messages = ArrayField(TextField, default=[])
