from disco.types.base import SlottedModel, Field, snowflake, ListField, text
from disco.util.config import Config

config = Config.from_file("./config.yaml")


class StreamEndedAction(object):
    DELETE_MESSAGE = 1
    EDIT_MESSAGE = 2
    LINK_TO_VOD = 3


class StreamNotificationsConfig(SlottedModel):
    username = Field(bool, default=True)
    title = Field(bool, default=True)
    category = Field(bool, default=True)
    viewers = Field(bool, default=True)
    live_since = Field(bool, default=True)
    tags = Field(bool, default=False)
    preview_image = Field(bool, default=True)
    button = Field(bool, default=True)
    mature_badge = Field(bool, default=False)
    live_update = Field(bool, default=True)
    stream_end_action = Field(int, default=StreamEndedAction.EDIT_MESSAGE)


class StreamPromotionalSettings(SlottedModel):
    enabled = Field(bool, default=False)
    promo_channel = Field(snowflake, default=None)
    promo_config = Field(StreamNotificationsConfig, default=StreamNotificationsConfig())


class StreamConfig(SlottedModel):
    defaults = Field(StreamNotificationsConfig, default=StreamNotificationsConfig())


class GambaConfig(SlottedModel):
    starting_balance = Field(int, default=1000)


class GuildConfig(SlottedModel):
    gamba = Field(GambaConfig, default=GambaConfig())
    stream_notifications = Field(StreamConfig, default=StreamConfig())
    promotional_settings = Field(StreamPromotionalSettings, default=StreamPromotionalSettings())
