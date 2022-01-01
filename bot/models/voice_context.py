import asyncio
import logging
import requests
import os
import json
import functools
from datetime import datetime

from async_timeout import timeout
from discord.ext import commands
from bot.models.queue import TrackQueue
from bot.util.color import ICE_BLUE
from bot.models.track import AsyncAudioSource

LOG = logging.getLogger('simple')
TRACK_EVENTS_ENDPOINT = os.environ.get("TRACK_EVENTS_ENDPOINT")

class VoiceContext:

    def __init__(self, bot: commands.Bot, ctx: commands.Context):
        self.bot = bot
        self._ctx = ctx

        self.tracks = TrackQueue()
        self.next_track = asyncio.Event()
        self.current_track = None

        self._volume = 0.5
        self.voice = None

        self.player = bot.loop.create_task(self.play_audio())

    def __del__(self):
        self.player.cancel()

    @property
    def is_playing(self):
        return self.voice and self.current_track

    async def play_audio(self):
        LOG.info("Initializing audio loop")
        while True:
            self.next_track.clear()

            try:
                async with timeout(900): # If nothing new in 15 minutes, quit
                    self.current_track = await self.tracks.get()
            except asyncio.TimeoutError:
                LOG.info("Loop timed out, exiting")
                self.bot.loop.create_task(self.stop())
                return

            LOG.info(f"Pulled in new track! {self.current_track.source.title}")
            self.current_track.source.volume = self._volume
            self.voice.play(self.current_track.source, after=self.play_next)

            try:
                play_event = self._construct_play_event(self.current_track.source)
                tracks_future = functools.partial(requests.post, TRACK_EVENTS_ENDPOINT, data=json.dumps(play_event))
                resp = await self.bot.loop.run_in_executor(None, tracks_future)
            except Exception as e:
                LOG.error(e)
            finally:
                if resp.status_code != 200:
                    LOG.error(f"Error occurred with posting track event to Iduna with status code: {resp.status_code}")
                else:
                    LOG.info(f"Successful track event post to Iduna for track ID {self.current_track.source.id}")

            await self.current_track.source.channel.send(
                embed=self.current_track.embed(
                    title='Now Playing!',
                    color=ICE_BLUE
                )
            )
            await self.next_track.wait()

    def play_next(self, error=None):
        if error:
            LOG.error(f"Something went wrong in play next: {str(error)}")
            raise
        self.next_track.set()

    def skip(self):
        if self.is_playing:
            self.voice.stop()

    def _construct_play_event(self, source: AsyncAudioSource):
        return {
            'id': source.id,
            'requested_by': source.requested_by.name + "#" + source.requested_by.discriminator,
            'event_type': 'PLAY',
            'title': source.title,
            'description': source.description,
            'webpage_url': source.webpage_url,
            'duration': source.duration,
            'timestamp': datetime.now().isoformat(),
            'guild_id': self._ctx.guild.id
        }

    async def stop(self):
        self.tracks.clear()

        if self.voice:
            await self.voice.disconnect()
            self.voice = None
