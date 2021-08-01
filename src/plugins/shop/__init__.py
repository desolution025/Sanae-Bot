from pathlib import Path
import yaml

from nonebot import MatcherGroup
from nonebot.rule import to_me

from src.common import Bot, MessageEvent, T_State
from src.common.itemsystem import FishingRod, MiningTool, cls_map
from src.common.rules import full_match


goods_file = Path(__file__).parent/'goods.yml'
with goods_file.open(encoding='utf-8') as f:
    goods = yaml.load(f)


shop = MatcherGroup(type='message', priority=2)


# shopping = shop.