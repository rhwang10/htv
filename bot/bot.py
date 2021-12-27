import discord
import os
import asyncio
import time
import requests
import psycopg2
import urllib.parse as urlparse

CACHED_USER_ENDPOINT = os.environ['CACHED_USER_ENDPOINT']
USER_MSG_ENDPOINT = os.environ['USER_MSG_ENDPOINT']

client = discord.Client(intents=discord.Intents.all())

# Called when the client is done preparing the data received
# from Discord. Usually after login is successful and the
# Client.guilds and co. are filled up.
@client.event
async def on_ready():
    print("Connected")

# Called when the client has disconnected from Discord.
# This could happen either through the internet being disconnected,
# explicit calls to logout, or Discord terminating
# the connection one way or the other.
# This function can be called many times.
@client.event
async def on_disconnect():
    print("Disconnected")

# Called when a member updates their profile
# This is called when one or more of the following things change
# status, activity, nickname, roles, pending
@client.event
async def on_member_update(previous_member_state, current_member_state):
    pass

@client.event
async def on_message(message):

    if message.author == client.user:
        return

    params = {
        'name': message.author.name,
        'id': message.author.discriminator
    }

    user_response = get(CACHED_USER_ENDPOINT, params=params)

    target_user_id = user_response["id"]
    message_response = get(USER_MSG_ENDPOINT + str(target_user_id))

    if message_response:
        await _type(message.channel, message_response['message'])

async def _type(channel, msg):
    await channel.trigger_typing()
    await asyncio.sleep(2)
    await channel.send(msg)

def get(req, params=None):
    try:
        resp = requests.get(req, params=params)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as err:
        print(err)

client.run(os.environ.get("BOT_TOKEN"))
