"""
License: GPL-3

Maintainer: Shadofer#0001

Contributors: 

File description:
    The test regarding the changeGuildVisibility response.

Extra info:
    None
"""

""" BUILT-IN MODULES """
from json import dumps, loads

""" 3RD-PARTY MODULES """

""" The main way of communicating. """
from websockets.client import connect

""" Ordering and running asynchronous tests. """
import pytest


@pytest.mark.asyncio
@pytest.mark.run(order=23)
async def test_change_guild_visibility_response():
    async with connect('ws://localhost:5000') as wss:

        await wss.send(dumps({'event': 'changeGuildVisibility', 'newGuildVisibility': 'public'}))

        response = loads(await wss.recv())

        assert isinstance(response, dict) and response['event'] == 'changeGuildVisibilityReply'
