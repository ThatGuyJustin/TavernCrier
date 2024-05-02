import requests
import yaml
from disco.bot.plugin import Plugin

from TavernCrier.models.configs import GuildConfigs
from TavernCrier.redis import rdb
from TavernCrier.util.twitch import refresh_access_token


class CorePlugin(Plugin):
    def load(self, ctx):
        # Check for and validate twitch access token
        if rdb.get("twitch_access_token"):
            req = requests.get("https://id.twitch.tv/oauth/validate",
                               headers={'Authorization': f"OAuth {rdb.get('twitch_access_token')}"})
            if req.status_code == 401:
                success, expire = refresh_access_token()
                if not success:
                    self.log.error("BOIS, SOMETHING IS ON FIRE 🔥 SEND HELP!")
        else:
            self.log.info("Token not found in redis, attempting to refresh")
            success, expire = refresh_access_token()

        super(CorePlugin, self).load(ctx)

    @Plugin.listen("Ready")
    def on_ready(self, event):
        self.log.info(f"Logged into discord as {event.user}")
        self.log.info("Updating registered commands...")
        with open("./data/commands.yaml", "r") as raw_commands:
            commands = yaml.safe_load(raw_commands)

        if commands['commands'].get('global'):
            new_commands = self.client.api.applications_global_commands_bulk_overwrite(commands['commands']['global'])
            self.log.info(f"Updated {len(new_commands)} global commands")

        if commands['commands'].get('guild'):
            self.log.info("NYI.")
