# Written by @nadie [Nadle]

import os
import signal

from gevent.exceptions import BlockingSwitchOutError

from disco.bot.plugin import Plugin

from TavernCrier.db import postgres_db
from TavernCrier.redis import rdb

PY_CODE_BLOCK = u'```py\n{}\n```'


class ControlPlugin(Plugin):
    def load(self, ctx):
        super(ControlPlugin, self).load(ctx)
        # register Process listeners
        signal.signal(signal.SIGINT, self.process_control)
        signal.signal(signal.SIGTERM, self.process_control)
        # signal.signal(signal.SIGUSR1, self.ProcessControl)

    def process_control(self, signal_number=None, frame=None):
        if signal_number in [2, 15]:
            self.log.warning("Graceful shutdown initiated")
            self.client.gw.shutting_down = True
            self.client.gw.ws.close(status=4000)
            self.client.gw.ws_event.set()

            self.log.info("Closing connection to database")
            try:
                # TODO: DATABASE STUFF!
                postgres_db.close()
                self.log.info("Postgres Database connection closed!")
                rdb.close()
                self.log.info("Redis Database connection closed!")
            except Exception:
                self.log.exception("Failed to close Database connections.")
            # unload plugins
            for x in list(self.bot.plugins):
                if x == 'CorePlugin' or x == 'ControlPlugin':
                    self.log.info('Skiping plugin: {}'.format(x))
                    continue
                plugin = next((v for k, v in self.bot.plugins.items() if k.lower() == x.lower()), None)
                if plugin:
                    self.log.info('Unloading plugin: {}'.format(x))
                    try:
                        self.bot.rmv_plugin(plugin)
                    except BlockingSwitchOutError:
                        self.log.warning("Plugin {} Has a active greenlet/schedule, Bruteforce".format(x))
                        # Due to the never ending disco bugs, Just remove the listeners to stop plugin execution after unload
                        plugin.greenlet = []
                        plugin.schedule = []
                        for listener in plugin.listeners:
                            listener.remove()
                        pass
                    except Exception:
                        self.log.exception("Failed to unload: {}".format(x))

        elif signal_number == 10:  # sysuser1
            self.log.warning("Reseting shard connection to Discord")
            self.client.gw.ws.close(status=4000)
        else:
            self.log.warning("Force Shutdown initiated")
            os.kill(os.getpid(), signal.SIGKILL)
