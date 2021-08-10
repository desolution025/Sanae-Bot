from pathlib import Path

from nonebot import MatcherGroup
from nonebot.rule import to_me

from src.common import Bot, MessageEvent, T_State, MessageSegment
from src.common.itemsystem import FishingRod, MiningTool, cls_map
from src.common.rules import full_match
from src.utils import async_exec, get_name
from .shelf import shop_interface, goods, UserLevel

shop = MatcherGroup(type='message', priority=2)


shopping = shop.on_message(rule=to_me()&full_match('商店'))


@shopping.handle()
async def open_store(bot: Bot, event: MessageEvent, state: T_State):
    async with UserLevel(event.user_id) as user:
        display = await async_exec(shop_interface, *goods['all'], user=user, name=get_name(event))
        await shopping.send(MessageSegment.image(display))
        state['goods'] = goods['all']