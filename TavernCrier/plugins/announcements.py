import re
from datetime import datetime

import gevent
import requests.exceptions
from disco.api.http import APIException
from disco.bot import Plugin
from disco.types.application import InteractionType
from disco.types.message import MessageEmbed, ActionRow, ComponentTypes, ButtonStyles, MessageModal, \
    TextInputStyles, SelectOption, ButtonComponent, SelectMenuComponent, TextInputComponent, component
from pytz import timezone
from redis.commands.json.path import Path

from TavernCrier import StreamNotificationsConfig, config as bot_config, StreamEndedAction
from TavernCrier.db import postgres_db
from TavernCrier.models.configs import GuildConfigs, StreamConfigs
from TavernCrier.redis import rdb
from TavernCrier.util.template import get_embed_template, get_component_template
from TavernCrier.util.twitch import make_twitch_request

TWITCH_URL_RE = re.compile(r"(https://twitch\.tv/?[a-zA-Z0-9][\w]{2,24})")

def get_user_avatar(user_id):
    if rdb.get(f'avatar_cache:{user_id}'):
        return rdb.get(f'avatar_cache:{user_id}')
    else:
        resp_code, ujson = make_twitch_request("https://api.twitch.tv/helix/users", "GET",
                                               params={'id': user_id})

        rdb.set(f'avatar_cache:{user_id}', ujson['data'][0]['profile_image_url'], ex=259200)
        return ujson['data'][0]['profile_image_url']

CONFIGURABLE_COMPONENTS = [
    "username",
    "title",
    "category",
    "viewers",
    "live_since",
    "tags",
    "preview_image",
    "button",
    "mature_badge",
    "live_update",
    "channel_select",
    "save_config",
    # "edit_messages"
    "edit_message",
    # "add_message",
    # "message_select_menu",
    # "del_message",
    "previous_page",
    "next_page",
    "role_select",
    "delete_button",
    "delete_prank_button",
    "promo_enabled"
]


class AnnouncementPlugin(Plugin):
    def load(self, ctx):
        super(AnnouncementPlugin, self).load(ctx)

    def get_next_interaction_event(self, user=None, message_id=None, conditional=None, timeout=10):
        event = None
        try:
            if message_id:
                event = self.wait_for_event("InteractionCreate",
                                            conditional=lambda e: e.message.id == message_id).get(timeout=timeout)
            elif user:
                event = self.wait_for_event("InteractionCreate",
                                            conditional=lambda e: e.member.id == user).get(timeout=timeout)
            elif conditional:
                event = self.wait_for_event("InteractionCreate",
                                            conditional=conditional).get(timeout=timeout)
        except gevent.Timeout as e:
            return None
        if event:
            return event
        else:
            return None

    def build_message_embed(self, enabled_components, streamer, preview=False):
        base_embed = MessageEmbed()
        base_embed.color = 0x8503d1
        if preview:
            if 'username' in enabled_components:
                base_embed.set_author(name=f"{streamer['display_name']}", icon_url=f"{streamer['profile_image_url']}", url=f"https://twitch.tv/{streamer['login']}")

            if 'title' in enabled_components:
                base_embed.title = f"Example title for a poggers twitch stream | !gamba"
                base_embed.url = f"https://twitch.tv/{streamer['login']}"

            if 'category' in enabled_components:
                base_embed.add_field(name="Category", value="Just Chatting", inline=True)

            if 'viewers' in enabled_components:
                base_embed.add_field(name="Viewers", value="6969", inline=True)

            if 'live_since' in enabled_components:
                tmp_time = int(datetime.now().timestamp())
                base_embed.add_field(name="Live Since", value=f"<t:{tmp_time}:F> (<t:{tmp_time}:R>)", inline=False)

            if 'tags' in enabled_components:
                base_embed.add_field(name="Tags", value="`Gamba` `Yoshi` `Dragon`", inline=False)

            if 'preview_image' in enabled_components:
                base_embed.set_image(url=streamer["offline_image_url"] or "https://static-cdn.jtvnw.net/ttv-static/404_preview-1920x1080.jpg")
        else:
            if 'username' in enabled_components:
                profile_picture = get_user_avatar(streamer['user_id'])
                base_embed.set_author(name=f"{streamer['user_name']}", icon_url=profile_picture,
                                      url=f"https://twitch.tv/{streamer['user_login']}")

            if 'title' in enabled_components:
                base_embed.title = streamer["title"]
                base_embed.url = f"https://twitch.tv/{streamer['user_login']}"

            if 'category' in enabled_components:
                base_embed.add_field(name="Category", value=streamer['game_name'], inline=True)

            if 'viewers' in enabled_components:
                base_embed.add_field(name="Viewers", value=f"`{streamer['viewer_count']}`", inline=True)

            if 'live_since' in enabled_components:
                converted_timestamp = int(datetime.fromisoformat(streamer['started_at']).timestamp())
                base_embed.add_field(name="Live Since", value=f"<t:{converted_timestamp}:F> (<t:{converted_timestamp}:R>)", inline=False)

            if 'tags' in enabled_components:
                tags = "`None`"
                if streamer.get('tags') and len(streamer['tags']):
                    tags = f"`{'` `'.join(streamer['tags'])}`"
                base_embed.add_field(name="Tags", value=tags, inline=False)

            if 'preview_image' in enabled_components:
                base_embed.set_image(url=streamer['thumbnail_url'].format(width=1920, height=1080))

        return base_embed

    def get_settings_action_row(self, enabled_components, channel, page, stream_config=None, messages=None, message_selected=False, role_selected=None, dl_button_pressed=False, is_promo=False):
        max_page = 2

        to_return = []

        if page == 1:
            ar_1 = ActionRow()
            ar_2 = ActionRow()

            username_button = ButtonComponent(label="Username", custom_id="username", style=3 if 'username' in enabled_components else 4)
            ar_1.add_component(username_button)

            title_button = ButtonComponent(label="Title", custom_id="title", style=3 if 'title' in enabled_components else 4)
            ar_1.add_component(title_button)

            game_button = ButtonComponent(label="Category", custom_id="category", style=3 if 'category' in enabled_components else 4)
            ar_1.add_component(game_button)

            viewers_button = ButtonComponent(label="Viewers", custom_id="viewers", style=3 if 'viewers' in enabled_components else 4)
            ar_1.add_component(viewers_button)

            # live_since_button.disabled = is_promo
            live_since_button = ButtonComponent(label="Live Since", custom_id="live_since", style=3 if 'live_since' in enabled_components else 4, disabled=is_promo)
            ar_1.add_component(live_since_button)

            tags_button = ButtonComponent(label="Tags", custom_id="tags", style=3 if 'tags' in enabled_components else 4)
            ar_2.add_component(tags_button)

            preview_image_button = ButtonComponent(label="Preview Image", custom_id="preview_image", style=3 if 'preview_image' in enabled_components else 4)
            ar_2.add_component(preview_image_button)

            btn_button = ButtonComponent(label="Click to Watch Button", custom_id="button", style=3 if 'button' in enabled_components else 4)
            ar_2.add_component(btn_button)

            # mature_badge_button.disabled = is_promo
            mature_badge_button = ButtonComponent(label="Mature Emoji", custom_id="mature_badge", style=3 if 'mature_badge' in enabled_components else 4, disabled = is_promo)
            ar_2.add_component(mature_badge_button)

            # live_update_button.disabled = is_promo
            live_update_button = ButtonComponent(label="Live Update Message", custom_id="live_update", style=3 if 'live_update' in enabled_components else 4, disabled=True)
            ar_2.add_component(live_update_button)

            ar_3 = ActionRow()
            channel_select = SelectMenuComponent(type=ComponentTypes.CHANNEL_SELECT, custom_id="channel_select", channel_types=[0, 5], max_values=1, min_values=1,
                                                 placeholder="Select Notification Channel" if not is_promo else "Select Promotion Channels")
            if channel:
                channel_select.default_values = [{"id": channel, "type": "channel"}]
            ar_3.add_component(channel_select)

            to_return += [ar_1.to_dict(), ar_2.to_dict(), ar_3.to_dict()]

        if page == 2:
            ar_1 = ActionRow()
            role_ping_select = SelectMenuComponent(type=ComponentTypes.ROLE_SELECT, custom_id="role_select", max_values=1, min_values=0, placeholder="Select a role to ping.")

            if role_selected:
                role_ping_select.default_values = [{"id": role_selected, "type": "role"}]
            ar_1.add_component(role_ping_select)

            ar_2 = ActionRow()
            edit_message_button = ButtonComponent(style=ButtonStyles.SECONDARY, custom_id="edit_message", label="Edit Message", emoji={'name': "📝"})
            ar_2.add_component(edit_message_button)

            to_return += [ar_1.to_dict(), ar_2.to_dict()]

        # TODO: Multiple messages :(
        # if page == 2:
        #     ar_1 = ActionRow()
        #     messages_select = MessageComponent()
        #     messages_select.type = ComponentTypes.STRING_SELECT
        #     messages_select.custom_id = "message_select_menu"
        #     messages_select.emoji = None
        #     if not stream_config and messages is None:
        #         messages_select.disabled = True
        #         bs_option = SelectOption(label="Placeholder", value="placeholder")
        #         bs_option.emoji = None
        #         messages_select.options = [bs_option]
        #     ar_1.add_component(messages_select)
        #
        #     ar_2 = ActionRow()
        #
        #     add_message_button = MessageComponent(emoji=None)
        #     add_message_button.type = ComponentTypes.BUTTON
        #     add_message_button.style = ButtonStyles.SUCCESS
        #     add_message_button.custom_id = "add_message"
        #     add_message_button.label = "Add Message"
        #     add_message_button.disabled = message_selected
        #     add_message_button.emoji = None
        #     ar_2.add_component(add_message_button)
        #
        #     edit_message_button = MessageComponent(emoji=None)
        #     edit_message_button.type = ComponentTypes.BUTTON
        #     edit_message_button.style = ButtonStyles.SECONDARY
        #     edit_message_button.custom_id = "edit_message"
        #     edit_message_button.label = "Edit Message"
        #     edit_message_button.disabled = not message_selected
        #     edit_message_button.emoji = None
        #     ar_2.add_component(edit_message_button)
        #
        #     del_message_button = MessageComponent(emoji=None)
        #     del_message_button.type = ComponentTypes.BUTTON
        #     del_message_button.style = ButtonStyles.DANGER
        #     del_message_button.custom_id = "del_message"
        #     del_message_button.label = "Remove Message"
        #     del_message_button.disabled = not message_selected
        #     del_message_button.emoji = None
        #     ar_2.add_component(del_message_button)
        #
        #     to_return += [ar_1.to_dict(), ar_2.to_dict()]

        ar_4 = ActionRow()

        # previous_page_button.disabled = (page == 1) or is_promo
        previous_page_button = ButtonComponent(style = ButtonStyles.SECONDARY, custom_id = "previous_page", label = "⬅", disabled = (page == 1) or is_promo)
        ar_4.add_component(previous_page_button)

        save_button = ButtonComponent(style = ButtonStyles.PRIMARY, label="Save", custom_id="save_config")
        ar_4.add_component(save_button)

        if is_promo:
            promo_enabled_button = ButtonComponent(style = 3 if 'promo_enabled' in enabled_components else 4, custom_id = "promo_enabled", label = "Enabled")
            ar_4.add_component(promo_enabled_button)

        if not dl_button_pressed:
            delete_button = ButtonComponent(style=ButtonStyles.DANGER, label="Delete Button", custom_id="delete_prank_button")
            ar_4.add_component(delete_button)

        next_page_button = ButtonComponent(style = ButtonStyles.SECONDARY, custom_id = "next_page", label = "➡", disabled = (page == max_page) or is_promo)
        ar_4.add_component(next_page_button)

        if not is_promo:
            trash_button = ButtonComponent(style=ButtonStyles.SECONDARY, custom_id="delete_button", disabled = not dl_button_pressed, emoji = {'name': '❌'})
            ar_4.add_component(trash_button)

        to_return.append(ar_4.to_dict())

        return to_return

    @Plugin.schedule(bot_config.check_interval, init=False)
    def stream_grab_schedule(self):
        configs = postgres_db.execute_sql(
            """
                SELECT 
                streamer_id, 
                array_agg(json_build_object('id', id, 'channel', notification_channel, 'role', notification_role, 'config', config, 'messages', messages)) 
                FROM stream_configs GROUP BY streamer_name, streamer_id
            """)

        cfg_dict = {str(row[0]): row[1] for row in configs}

        to_check_live = "&user_id=".join(cfg_dict.keys())

        rjson = None
        code = None

        retry = 0
        while retry < 5:
            try:
                code, rjson = make_twitch_request("https://api.twitch.tv/helix/streams", "GET", params=f"type=live&first=100&user_id={to_check_live}")
                break
            except Exception as e:
                retry += 1
                self.log.error(f"Unable to connect to Twitch's API. Retrying... ({retry}) %s", e)
                gevent.sleep(5)

        # TODO: Bot Error Log
        if retry == 5:
            self.log.error("Max of 5 retries exceeded. Waiting 1 minute before restarting schedule.")
            active_greenlet = self.schedules['stream_grab_schedule']
            del self.schedules['stream_grab_schedule']
            gevent.sleep(60)
            self.register_schedule(self.stream_grab_schedule, bot_config.check_interval, init=True)
            self.log.info("Schedule restarted.")
            active_greenlet.kill()

        if code != 200:
            return

        live_users = {}

        if rjson.get('data') and len(rjson['data']):
            for stream in rjson['data']:
                live_users[stream['user_id']] = []
                cfgs = cfg_dict[stream['user_id']]
                for config in cfgs:
                    update = False
                    cid = None
                    mid = None
                    if rdb.exists(f"live_update:{stream['user_id']}:{config['id']}"):
                        data = rdb.json().get(f"live_update:{stream['user_id']}:{config['id']}")
                        live_users[stream['user_id']].append(
                            {'cid': data['cid'], 'mid': data['mid'], 'username': stream['user_name'],
                             'end_action': config['config']['stream_end_action']})
                        if datetime.now().timestamp() - data['last_updated'] < bot_config.live_update_interval:
                            continue
                        elif datetime.now().timestamp() - data['last_updated'] >= bot_config.rouge_key_removal_interval:
                            self.log.error(f"Rouge Live Key Found. Deleting and recreating. Key ID: live_update:{stream['user_id']}:{config['id']}")
                            rdb.json().delete(f"live_update:{stream['user_id']}:{config['id']}")
                        else:
                            update = True
                            cid = data['cid']
                            mid = data['mid']
                    enabled_components = [c for c, value in config['config'].items() if value == True]
                    embed = self.build_message_embed(enabled_components, stream)
                    components = None
                    if 'button' in enabled_components:
                        main_ar = ActionRow()
                        preview_btn = ButtonComponent(get_component_template("stream_notification_url_button"))
                        preview_btn.url = f"https://twitch.tv/{stream['user_login']}"
                        if 'mature_badge' in enabled_components:
                            preview_btn.label += "🔞"
                        main_ar.add_component(preview_btn)
                        components = [main_ar]

                    msg = config['messages'][0]
                    if '{role}' in msg and not config['role']:
                        msg = msg.replace("{role}", "")
                    elif '{role}' in msg:
                        msg = msg.format(role=f"<@&{config['role']}>")

                    if update:
                        now = datetime.now(tz=timezone("America/New_York"))
                        embed.set_footer(text="Last Updated")
                        embed.timestamp = now
                        try:
                            self.client.api.channels_messages_modify(channel=cid, message=mid,
                                                                     content=msg,
                                                                     embeds=[embed],
                                                                     components=components)

                            rdb.json().set(f"live_update:{stream['user_id']}:{config['id']}", Path.root_path(), {'mid': mid, 'cid': cid,'last_updated': now.timestamp()})
                        except APIException as e:
                            self.log.error(f"Unable to update message: Streamer: {stream['user_login']} Config ID: {config['id']}. Removing Live Update fromm Redis!")
                            rdb.json().delete(f"live_update:{stream['user_id']}:{config['id']}")
                            continue
                    else:
                        try:
                            if components:
                                components = [c.to_dict() for c in components]
                            created_msg = self.client.api.channels_messages_create(config['channel'],
                                                                                   content=msg,
                                                                                   embeds=[embed],
                                                                                   components=components,
                                                                                   allowed_mentions={'parse': ["roles", "users", "everyone"]})

                            live_users[stream['user_id']].append({'cid': config['channel'], 'mid': created_msg.id, 'username': stream['user_name'], 'end_action': config['config']['stream_end_action']})

                            if 'live_update' in enabled_components:
                                rdb.json().set(f"live_update:{stream['user_id']}:{config['id']}", Path.root_path(), {'mid': created_msg.id, 'cid': config['channel'],'last_updated': datetime.now().timestamp()})
                        except APIException as e:
                            self.log.error(f"Unable to send Message for Config ID {config['id']}: {e.msg}")

        currently_live = {}
        if rdb.exists("currently_live"):
            currently_live = rdb.json().get("currently_live", Path.root_path())

        prev_live_users = [user for user in currently_live.keys() if user not in live_users.keys()]

        for user in prev_live_users:
            keys = rdb.keys(f"live_update:{user}:*")
            for key in keys:
                rdb.json().delete(key)
            for notif in currently_live[user]:
                if notif['end_action'] == StreamEndedAction.EDIT_MESSAGE:
                    try:
                        msg = self.client.api.channels_messages_get(channel=notif['cid'], message=notif['mid'])
                        ar = ActionRow()
                        go_to_btn = component(get_component_template("stream_end_go_to_channel"))
                        go_to_btn.emoji = None
                        go_to_btn.url = f"https://twitch.tv/{notif['username']}"
                        ar.add_component(go_to_btn)
                        msg.edit(f"{notif['username']}'s stream has ended.", components=[ar])
                        # self.client.api.channels_messages_modify(channel=notif['cid'], message=notif['mid'],
                        #                                          content=f"{notif['username']}'s stream has ended.",
                        #                                          embeds=None,
                        #                                          components=None)
                    except APIException as e:
                        continue
                elif notif['end_action'] == StreamEndedAction.DELETE_MESSAGE:
                    try:
                        self.client.api.channels_messages_delete(channel=notif['cid'], message=notif['mid'])
                    except APIException as e:
                        continue

        rdb.json().delete("currently_live", Path.root_path())
        rdb.json().set("currently_live", Path.root_path(), live_users)

    def configure_stream(self, event, msg, streamer, initial_setup=False, stream_cfg=None, promo_setup=False):

        current_working_event = event
        dl_button_pressed = False
        gcfg, created = GuildConfigs.get_or_create(guild_id=event.guild.id)
        selected_channel = None
        enabled_components = []
        error = ""
        message = ""
        role = None
        page = 1
        if initial_setup:
            enabled_components = [key for key, value in gcfg.config.stream_notifications.defaults.to_dict().items() if
                                  value is True]
        if stream_cfg:
            enabled_components = [key for key, value in stream_cfg.config.to_dict().items() if
                                  value is True]
            selected_channel = stream_cfg.notification_channel
            message = stream_cfg.messages[0]
            role = stream_cfg.notification_role
        if promo_setup:
            enabled_components = [key for key, value in gcfg.config.promotional_settings.promo_config.to_dict().items() if
                                  value is True and key not in ["live_since", "mature_badge", "live_update"]]
            if gcfg.config.promotional_settings.enabled:
                enabled_components.append("promo_enabled")
            selected_channel = gcfg.config.promotional_settings.promo_channel
        while True:
            preview_embed = self.build_message_embed(enabled_components, streamer, preview=True)
            msg_components = []
            if 'button' in enabled_components:
                main_ar = ActionRow()
                preview_btn = component(get_component_template("stream_notification_url_button"))
                preview_btn.url = f"https://twitch.tv/{streamer['login']}"
                if 'mature_badge' in enabled_components:
                    preview_btn.label += "🔞"
                main_ar.add_component(preview_btn)
                msg_components.append(main_ar.to_dict())

            settings_ar = self.get_settings_action_row(enabled_components, selected_channel, page, role_selected=role, dl_button_pressed=dl_button_pressed, is_promo=promo_setup)
            msg_components += settings_ar
            if not msg:
                msg = event.reply(type=4, content=f"{error}{message.format(role=f'<@&{role}>')}", embeds=[preview_embed],
                                  components=msg_components, flags=(1 << 6))
            else:
                try:
                    msg.edit(content=f"{error}{message.format(role=f'<@&{role}>')}", embeds=[preview_embed],
                             components=msg_components)
                except APIException as e:
                    error = "`❌ ERROR ❌`: **Embed Can't Be Empty.**\n\n"
                    enabled_components.append("title")
                    continue
                error = ""
                current_working_event.reply(type=6)
            current_working_event = self.get_next_interaction_event(conditional=
                                                                    lambda e: e.type == InteractionType.MESSAGE_COMPONENT and e.data.custom_id in CONFIGURABLE_COMPONENTS,
                                                                    timeout=60)
            if not current_working_event:
                msg.edit("Timeout.").after(10)
                msg.delete()
                break
            else:
                match current_working_event.data.custom_id:
                    case "next_page":
                        page += 1
                    case "previous_page":
                        page -= 1
                    case "save_config":

                        if not selected_channel:
                            error = f"`❌ ERROR ❌`: **No Channel Selected**\n\n"
                            continue

                        config = StreamNotificationsConfig()
                        for key in config.to_dict().keys():
                            if key in enabled_components:
                                setattr(config, key, True)
                            elif type(config.to_dict()[key]) == bool:
                                setattr(config, key, False)
                        # "promo_channels": ["1", "2", "2", "9", "6", "2", "3", "6", "3", "6", "3", "5", "3", "0", "9", "3", "6", "8", "3"],
                        if promo_setup:
                            self.log.info(selected_channel)
                            gcfg.config.promotional_settings.enabled = "promo_enabled" in enabled_components
                            gcfg.config.promotional_settings.promo_channel = selected_channel
                            gcfg.config.promotional_settings.promo_config = config
                            gcfg.save()
                            msg.edit(
                                f"Promo Template Saved.").after(30)
                            msg.delete()
                            return

                        if stream_cfg:
                            StreamConfigs.update({
                                StreamConfigs.config: config,
                                StreamConfigs.messages: [message],
                                StreamConfigs.notification_channel: selected_channel,
                                StreamConfigs.notification_role: role
                            }).where(StreamConfigs.id == stream_cfg.id).execute()
                        else:
                            StreamConfigs.create(guild_id=current_working_event.guild.id,
                                                 notification_channel=selected_channel,
                                                 notification_role=role,
                                                 streamer_id=streamer['id'],
                                                 streamer_name=streamer['login'],
                                                 config=config.to_dict(),
                                                 messages=[message])

                        msg.edit(f"Config saved for streamer `{streamer['display_name']}` (<#{selected_channel}>)").after(30)
                        msg.delete()
                        return
                    case "channel_select":
                        selected_channel = current_working_event.data.values[0]
                    case "role_select":
                        if len(current_working_event.data.values):
                            role = current_working_event.data.values[0]
                        else:
                            role = None
                    case "delete_prank_button":
                        dl_button_pressed = True
                    case "delete_button":
                        if not stream_cfg:
                            continue

                        ar = ActionRow()

                        confirm_yes = component(get_component_template("confirm_yes"))
                        confirm_yes.custom_id = "delete_config_yes"

                        confirm_no = component(get_component_template("confirm_no"))
                        confirm_no.custom_id = "delete_config_no"

                        ar.add_component(confirm_yes)
                        ar.add_component(confirm_no)

                        msg.edit(f"Do you **Really** want to remove this config?\n* Streamer: `{streamer['display_name']}`\n* Channel: <#{selected_channel}>\n", components=[ar.to_dict()])

                        current_working_event = self.get_next_interaction_event(conditional=lambda e: e.type == InteractionType.MESSAGE_COMPONENT and e.data.custom_id in ["delete_config_yes", "delete_config_no"], timeout=10)

                        if not current_working_event:
                            msg.edit("Timeout.").after(10)
                            msg.delete()
                            return

                        if current_working_event.data.custom_id == "delete_config_no":
                            continue

                        StreamConfigs.delete().where(StreamConfigs.id == stream_cfg.id).execute()
                        msg.edit("💩 Config Deleted.").after(10)
                        msg.delete()
                        return
                    # case "add_message":
                        # current_working_event = add_message()
                        # modal = MessageModal()
                        # modal.custom_id = "new_message"
                        # modal.title = "New Message"
                        #
                        # new_message = MessageComponent()
                        # new_message.type = ComponentTypes.TEXT_INPUT
                        # new_message.style = TextInputStyles.PARAGRAPH
                        # new_message.label = "Message"
                        # new_message.placeholder = "# **Hilariously derailing one liner** {role}"
                        # new_message.required = True
                        # new_message.custom_id = "message"
                        #
                        # ar1 = ActionRow()
                        # ar1.add_component(new_message)
                        #
                        # current_working_event.reply(type=9, modal=modal)
                        # current_working_event = self.get_next_interaction_event(
                        #     conditional=lambda
                        #         e: e.type == InteractionType.MODAL_SUBMIT and e.data.custom_id == "new_message" and e.member.id == event.member.id,
                        #     timeout=60
                        # )
                        #
                        # if not current_working_event:
                        #     msg.edit("Timeout.").after(10)
                        #     msg.delete()
                        #     return
                        #
                        # current_working_event.reply(type=6)
                        # submitted = current_working_event.data.components[0].components[0].value
                    #
                    # case "del_message":
                    #     pass
                    case "edit_message":
                        modal = MessageModal()
                        modal.custom_id = "edit_message_modal"
                        modal.title = "Edit Message"

                        new_message = TextInputComponent(style = TextInputStyles.PARAGRAPH, label = "Message", placeholder = "# **Hilariously derailing one liner** {role}", required = True, custom_id = "message")
                        if message:
                            new_message.value = message

                        ar1 = ActionRow()
                        ar1.add_component(new_message)

                        modal.add_component(ar1)

                        current_working_event.reply(type=9, modal=modal)

                        current_working_event = self.get_next_interaction_event(
                            conditional=lambda
                                e: ((e.type == InteractionType.MODAL_SUBMIT and e.data.custom_id == "edit_message_modal") or (e.type == InteractionType.MESSAGE_COMPONENT and e.data.custom_id in CONFIGURABLE_COMPONENTS)) and e.member.id == event.member.id,
                            timeout=60
                        )

                        if not current_working_event:
                            msg.edit("Timeout.").after(10)
                            msg.delete()
                            return

                        if current_working_event.data.custom_id != "edit_message_modal":
                            continue

                        message = current_working_event.data.components[0].components[0].value
                    case "message_select_menu":
                        pass
                    case _:
                        if current_working_event.data.custom_id in enabled_components:
                            enabled_components.remove(current_working_event.data.custom_id)
                        else:
                            enabled_components.append(current_working_event.data.custom_id)

    @Plugin.listen("InteractionCreate", conditional=lambda e: e.type == InteractionType.APPLICATION_COMMAND and e.data.name == "configure-streams")
    def configuration_cmd(self, event):

        if len(event.data.options):
            if event.data.options[0].value.startswith("id-"):
                cfg_id = int(event.data.options[0].value[3:])
                scfg = StreamConfigs.select(StreamConfigs).where((StreamConfigs.guild_id == event.guild.id) & (StreamConfigs.id == cfg_id)).get()
                resp_code, ujson = make_twitch_request("https://api.twitch.tv/helix/users", "GET",
                                                                  params={'id': scfg.streamer_id})
                return self.configure_stream(event=event, msg=None, streamer=ujson['data'][0], stream_cfg=scfg)

            # TODO: go right to config setup!
            if event.data.options[0].value != "n-a":
                pass

        raw_configs = postgres_db.execute_sql(
            f"""
                SELECT 
                notification_channel, 
                array_agg(streamer_name) FROM stream_configs 
                WHERE guild_id = {event.guild.id} GROUP BY notification_channel
            """)

        active_configs = {str(row[0]): row[1] for row in raw_configs}

        embed = MessageEmbed(get_embed_template("stream_main_configuration"))
        tmp_desc = embed.description

        count = 0
        configured_streamers_template = []
        for channel, streams in active_configs.items():
            configured_streamers_template.append(f"### <#{channel}>")
            for streamer in streams:
                count += 1
                configured_streamers_template.append(f"* `{streamer}`")

        embed.description = tmp_desc.format(total_configured=str(count), streams_configured="\n".join(configured_streamers_template))
        ar = ActionRow()

        add_channel = component(get_component_template("stream_config_add_channel"))
        add_channel.custom_id = "stream_main_config_add_channel"

        modify_promo_settings = component(get_component_template("stream_config_promo_settings_edit"))
        modify_promo_settings.custom_id = "stream_config_promo_settings_edit"

        # modify_channel = MessageComponent(get_component_template("stream_config_modify_channel"))
        # modify_channel.custom_id = "stream_main_config_modify_channel"

        ar.add_component(add_channel)
        ar.add_component(modify_promo_settings)

        msg = event.reply(type=4, embeds=[embed], components=[ar.to_dict()], flags=(1 << 6))

        next_command = None

        next_command = self.get_next_interaction_event(
            conditional=lambda e: e.type == InteractionType.MESSAGE_COMPONENT and e.data.custom_id in ["stream_main_config_add_channel", "stream_config_promo_settings_edit"] and e.member.id == event.member.id,
            timeout=60
        )

        if next_command:
            if next_command.data.custom_id == "stream_main_config_add_channel":
                current_working_event = next_command
                while True:
                    ar1 = ActionRow()

                    twitch_name = TextInputComponent(style = TextInputStyles.SHORT, label = "Twitch Username", placeholder = "twitchdev", required = True, custom_id = "twitch_username")
                    ar1.add_component(twitch_name)

                    modal = MessageModal()
                    modal.title = "Add Streamer"
                    modal.custom_id = "streamer_add_channel"
                    modal.add_component(ar1)

                    current_working_event.reply(type=9, modal=modal)
                    username_validation = self.get_next_interaction_event(
                        conditional=lambda e: e.type == InteractionType.MODAL_SUBMIT and e.data.custom_id=="streamer_add_channel" and e.member.id == event.member.id,
                        timeout=60
                    )

                    if not username_validation:
                        msg.edit("Timed out.").after(10)
                        msg.delete()
                        break

                    username_validation.reply(type=6)
                    submitted = username_validation.data.components[0].components[0].value
                    resp_code, rjson = make_twitch_request("https://api.twitch.tv/helix/users", "GET",
                                                           params={'login': submitted})

                    ar = ActionRow()

                    confirm_yes = component(get_component_template("confirm_yes"))
                    confirm_yes.custom_id = "stream_add_channel_confirm_username_yes"

                    confirm_no = component(get_component_template("confirm_no"))
                    confirm_no.custom_id = "stream_add_channel_confirm_username_no"

                    ar.add_component(confirm_yes)
                    ar.add_component(confirm_no)

                    if rjson.get("data"):
                        if len(rjson["data"]) == 0:

                            msg.edit(f"**Error**: There is no twitch user with the username `{submitted}`. Would you like to retry?", components=[ar.to_dict()])
                            current_working_event = self.get_next_interaction_event(
                                conditional=lambda e: e.type == InteractionType.MESSAGE_COMPONENT and e.data.custom_id in ["stream_add_channel_confirm_username_yes", "stream_add_channel_confirm_username_no"] and e.member.id == event.member.id,
                                timeout=60
                            )

                            if not current_working_event:
                                msg.edit("Timed out.").after(10)
                                msg.delete()
                                break

                            if current_working_event.data.custom_id == "stream_add_channel_confirm_username_no":
                                msg.edit("\👌 Alright, feel free to try again later!").after(5)
                                msg.delete()
                                break
                            elif current_working_event.data.custom_id == "stream_add_channel_confirm_username_yes":
                                continue
                        else:
                            resp_code, sjson = make_twitch_request("https://api.twitch.tv/helix/channels/followers", "GET",
                                                                   params={'broadcaster_id': rjson["data"][0]["id"], 'first': 1})
                            embed = MessageEmbed(get_embed_template("stream_user_confirmation"))
                            tmp_desc = embed.description
                            tmp_desc = tmp_desc.replace("{display_name}", rjson["data"][0]["display_name"])
                            tmp_desc = tmp_desc.replace("{followers}", str(sjson["total"]))
                            # tmp_desc = tmp_desc.replace("{title}", f"*{rjson['data'][0]['type']}*")
                            embed.description = tmp_desc.replace("{description}", f"{rjson['data'][0]['description']}")
                            embed.set_thumbnail(url=rjson["data"][0]["profile_image_url"])
                            embed.set_image(url=rjson["data"][0]["offline_image_url"])
                            msg.edit(embeds=[embed], components=[ar.to_dict()])

                            current_working_event = self.get_next_interaction_event(
                                conditional=lambda
                                    e: e.type == InteractionType.MESSAGE_COMPONENT and e.data.custom_id in [
                                    "stream_add_channel_confirm_username_yes",
                                    "stream_add_channel_confirm_username_no"] and e.member.id == event.member.id,
                                timeout=60
                            )

                            if not current_working_event:
                                msg.edit("Timed out.").after(10)
                                msg.delete()
                                break

                            if current_working_event.data.custom_id == "stream_add_channel_confirm_username_no":
                                continue
                            elif current_working_event.data.custom_id == "stream_add_channel_confirm_username_yes":
                                return self.configure_stream(current_working_event, msg, rjson["data"][0], initial_setup=True)
                            break
                    else:
                        return msg.edit("`Internal Error: Please Try Again. If issue persist, Please reach out to @ThatRandoJustin`")
            elif next_command.data.custom_id == "stream_config_promo_settings_edit":
                status_code, rjson = make_twitch_request("https://api.twitch.tv/helix/users", "GET", params={"login": "twitchdev"})
                self.configure_stream(next_command, msg, rjson["data"][0], promo_setup=True)
        else:
            msg.edit("Timed out.").after(10)
            msg.delete()

    @Plugin.listen("InteractionCreate", conditional=lambda e: e.type == InteractionType.APPLICATION_COMMAND_AUTOCOMPLETE and e.data.name == "configure-streams")
    def streamer_autocomplete(self, event):
        choices = []

        streamers = []
        current_filter = event.data.options[0].value
        if not len(current_filter):
            streamers = list(StreamConfigs.select(StreamConfigs).where(
                (StreamConfigs.guild_id == event.guild.id)).limit(25))
        else:
            streamers = list(StreamConfigs.select(StreamConfigs).where((StreamConfigs.guild_id == event.guild.id) & (StreamConfigs.streamer_name.contains(current_filter.lower()))).limit(25))

        if len(streamers):
            for option in streamers:
                channel_obj = self.client.state.channels.get(option.notification_channel, None)
                channel = None
                if channel_obj:
                    channel = f"#{channel_obj.name}"
                else:
                    channel = "#Unknown-Channel"
                choices.append({'name': f'[{option.id}] {option.streamer_name} - {channel}', 'value': f'id-{option.id}'})
        else:
            choices.append({'name': "None Matching Your Input.", 'value': "n-a"})

        event.reply(type=8, choices=choices)

    @Plugin.listen("MessageCreate", conditional=lambda e: not e.author.bot and e.guild is not None)
    def promotional_messages(self, event):

        # Grab config for guild, if there is one. If not, ignore!
        guild_config = GuildConfigs.get(guild_id=event.guild.id)

        if not guild_config:
            return

        # Enable check
        if not guild_config.config.promotional_settings.enabled:
            return

        # Channel check
        if event.channel.id != guild_config.config.promotional_settings.promo_channel:
            return

        # # Test Case
        # if event.channel.id != 1229623636353093683:
        #     return

        # Check for a valid twitch link
        matches = TWITCH_URL_RE.findall(event.content)
        if len(matches) == 0:
            return

        # Only use first match, and replace it to not embed in content
        user_url_to_convert = matches[0]
        user = user_url_to_convert.replace("https://twitch.tv/", "")
        new_content = event.content.replace(user_url_to_convert, f"<{user_url_to_convert}>", -1)

        # Check if the user is actually live...and actually exists...!
        resp_code, rjson = make_twitch_request("https://api.twitch.tv/helix/streams", "GET",
                                               params={'user_login': user.lower(), 'type': "live"})

        if not rjson.get("data") or len(rjson['data']) == 0:
            return

        # Let's craft that message!
        enabled_components = [cp for cp, value in guild_config.config.promotional_settings.promo_config.to_dict().items() if value == True]
        embed = self.build_message_embed(enabled_components, rjson["data"][0])
        embed.set_footer(icon_url=event.author.avatar_url, text=f"Promoted by {event.author.username}")
        components = None
        if 'button' in enabled_components:
            main_ar = ActionRow()
            preview_btn = component(get_component_template("stream_notification_url_button"))
            preview_btn.url = user_url_to_convert
            if rjson['data'][0]['is_mature']:
                preview_btn.label += "🔞"
            main_ar.add_component(preview_btn)
            components = [main_ar]

        try:
            self.log.info(new_content)
            created_msg = self.client.api.channels_messages_create(event.channel.id,
                                                                   content=new_content,
                                                                   embeds=[embed],
                                                                   components=[c.to_dict() for c in
                                                                               components],
                                                                   allowed_mentions={})
        except APIException as e:
            if e.code == [50001]:
                return
            else:
                self.log.error(f"[Promotional Messages] Failed to send promo message: Channel: {event.channel.id} Author: {event.author} Guild: {event.guild.id} --")
                raise e

        try:
            event.delete()
        except APIException as e:
            if e.code == [50013]:
                self.log.error(
                    f"[Promotional Messages] Failed to delete original promo message: Channel: {event.channel.id} Author: {event.author} Guild: {event.guild.id} --")
                return