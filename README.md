# TavernCrier

## Features
* Twitch Live Stream Notifications
  * Configurable with setup command
    * Components can be disabled/enabled at will.
  * Messages can live update

## Requirements Before Starting
1) [Discord Bot Created](https://discord.com/developers/applications)
2) [Twitch Application Created](https://dev.twitch.tv/console)
3) Twitch Credentials for config
4) Python 3.11
5) [Poetry](https://python-poetry.org/)
6) A RedisDB *(I used docker)*
7) A Postgresql DB *(Also used docker)*

## How do Setup?
1) `git clone https://github.com/ThatGuyJustin/TavernCrier.git`
2) Modify `config.example.yaml` then rename/copy to `config.yaml`
3) `poetry update`
4) `poetry run python -m disco.cli` 
   * Optionally, you can move the config file elsewhere and add on `--config CONFIG_LOCATION` to specify an alternate config directory.

## HOW DO TWITCH NOTIFY?
`/configure-streams [streamer]` Like so:

![Example Gif](https://i.imgur.com/IyScFUf.mp4)

Alternately

![Example2 Gif](https://i.imgur.com/ON7BQcd.mp4)

## FAQ
`Q: Will I add *Insert Feature Here*`

Maybe? If there's a good reason!

`Q: If you used Docker for your DB, why doesn't this have a docker file/image?`

WELL YOU KNOW WHAT, MAYBE I WILL!

## TODO/WIP:
* Add Gamba
* Resort subconfig
* Clean up Announcement garbage/debug lines
* Add Announcement Multi-Message support
* Add Other end stream actions (Message deletion/Link to VOD)
* YouTube support (Video + Live)
* Docker stuff maybe :sipglare: