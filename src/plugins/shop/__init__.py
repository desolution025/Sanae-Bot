from pathlib import Path

from nonebot import MatcherGroup
from nonebot.rule import to_me

from src.common import Bot, MessageEvent, T_State
from src.common.itemsystem import FishingRod, MiningTool, cls_map
from src.common.rules import full_match


shop = MatcherGroup(type='message', priority=2)


shopping = shop.on_message(rule=to_me()&full_match('商店'))


@shopping.handle()
async def open_store(bot: Bot, event: MessageEvent, state: T_State):
    pass