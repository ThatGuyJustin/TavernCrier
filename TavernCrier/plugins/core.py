import gevent
import requests
import yaml
from disco.bot.plugin import Plugin
from disco.types.message import MessageEmbed
from disco.util.emitter import Priority

from TavernCrier import config
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

    # TODO: Bot startup log
    @Plugin.listen("Ready")
    def on_ready(self, event):
        if self.bot.client.gw.reconnects:
            self.log.info("[Bot GW Reconnect] Restarting live schedule.")
            active_greenlet = self.bot.plugins["AnnouncementPlugin"].schedules['stream_grab_schedule']
            del self.bot.plugins["AnnouncementPlugin"].schedules['stream_grab_schedule']
            gevent.sleep(10)
            self.bot.plugins["AnnouncementPlugin"].register_schedule(self.bot.plugins["AnnouncementPlugin"].stream_grab_schedule, config.check_interval, init=True)
            self.log.info("[Bot GW Reconnect] Live schedule restarted.")
            active_greenlet.kill()
        else:
            self.log.info(f"Logged into discord as {event.user}")
            self.log.info("Updating registered commands...")
            with open("./data/commands.yaml", "r") as raw_commands:
                commands = yaml.safe_load(raw_commands)

            if commands['commands'].get('global'):
                new_commands = self.client.api.applications_global_commands_bulk_overwrite(
                    commands['commands']['global'])
                self.log.info(f"Updated {len(new_commands)} global commands")

            if commands['commands'].get('guild'):
                self.log.info("NYI.")

    @Plugin.listen("GuildCreate", priority=Priority.BEFORE)
    def guild_whitelist(self, event):

        if not config.enforce_whitelist:
            return

        if rdb.exists("guild_whitelist"):
            redis_whitelist = rdb.lrange("guild_whitelist", 0, -1)
            if str(event.guild.id) not in redis_whitelist:
                me = MessageEmbed()
                me.color = 0xefb435
                me.title = "🚨 Whitelist Violation 🚨"
                me.add_field(name="Server Name", value=f"{event.guild.name}\n(`{event.guild.id}`)", inline=True)
                me.add_field(name="Server Owner", value=f"`{event.guild.owner.user.username}`\n(`{event.guild.owner.id}`)", inline=True)
                me.add_field(name="Member Count", value=f"`{event.member_count}`", inline=False)
                if event.guild.description:
                    me.add_field(name="Description", value=f"```{event.guild.description}```")
                me.set_thumbnail(url=event.guild.get_icon_url())
                if event.guild.banner:
                    me.set_image(url=event.guild.get_banner_url())
                me.set_footer(text="Joined At")
                me.timestamp = event.joined_at
                self.client.api.channels_messages_create(channel=config.logging_channel, embeds=[me])

                event.guild.leave()
