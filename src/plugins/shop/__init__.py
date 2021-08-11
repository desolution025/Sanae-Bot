from pathlib import Path
from datetime import datetime, timedelta

from nonebot import get_driver
from nonebot import MatcherGroup
from nonebot.rule import to_me

from src.common import Bot, MessageEvent, T_State, MessageSegment, CANCEL_EXPRESSION
from src.common.rules import full_match
from src.common.itemsystem import BaseTool, CollectionItem, cls_map
from src.utils import async_exec, get_name, reply_header
from .shelf import Shelf
from .ui import shop_interface, UserLevel


driver = get_driver()

@driver.on_startup()
async def load_shelf_from_db():
    Shelf.load_all_shelf_data()


shop = MatcherGroup(type='message', priority=2)


shopping = shop.on_message(rule=to_me()&full_match('商店'))


@shopping.handle()
async def open_store(bot: Bot, event: MessageEvent, state: T_State):
    async with UserLevel(event.user_id) as user:
        async with Shelf() as shelf:
            # 检测时间看是否刷新商店
            cru_time = datetime.now()
            if cru_time.hour >= 12:
                last_refresh_time = datetime(cru_time.year, cru_time.month, cru_time.day, hour=12)
            else:
                last_refresh_time = datetime(cru_time.year, cru_time.month, cru_time.day, hour=0)
            if shelf.time < last_refresh_time:
                await shelf.refresh()
            # 计算下一次刷新时间，如果在刷新时间点进行操作会提示重新开启商店
            state['next_refresh_time'] = last_refresh_time + timedelta(hours=12)
            # 生成并发送商店界面
            display = await async_exec(shop_interface, shelf.goods, user=user, name=get_name(event))
            state['shelf'] = shelf.goods
            await shopping.send(MessageSegment.image(display))
        state['user'] = user
    state['open_time'] = datetime.now()


@shopping.receive()
async def buy(bot: Bot, event: MessageEvent, state: T_State):
    # 5分钟自动退出商店
    if datetime.now()- state['open_time'] > timedelta(seconds=5):
        await shopping.finish()
    cmd = event.message.extract_plain_text().strip()
    if cmd in CANCEL_EXPRESSION:
        await shopping.finish('已退出商店，如需购买商品请重新开启商店')
    # 中途遇到刷新时间点强行结束命令，需要用户重新开启以刷新
    if datetime.now() > state['next_refresh_time']:
        await shopping.finish(reply_header(event, '当前商店信息已过期，请重新开启商店！'))

    if cmd.startswith('购买'):
        reply = lambda x: reply_header(event, x)
        args = [a for a in cmd.lstrip('购买').split(' ') if bool(a)]
        if not args:
            await shopping.reject(reply('未指定要购买的道具编号'))
        if len(args) > 2:
            await shopping.reject(reply('参数不符合要求，仅能接收商品编号和数量两个参数，使用空格分隔'))
        if not all(map(lambda x: x.isdigit(), str)):
            await shopping.reject(reply('只能使用数字参数'))
        index = int(args[0])
        if index < 0 or index > len(state['shelf'].goods) + 1:
            await shopping.reject(reply(f'道具编号 {index} 不在当前可售卖范围内'))
        num = 1 if len(args) == 1 else int(args[1])
        commodity = state['shelf'].goods[index]
        if num > commodity['num']:
            await shopping.reject(reply('指定商品剩余数量不足'))
        user : UserLevel = state['user']
        if cost:= commodity['price'] * num > user.fund:
            await shopping.reject(reply(f'需 {cost} 金币购买 {num} 个 {commodity["name"]}，资金不足'))
        state['index'] = index
        state['num'] = num
        await shopping.send(reply(f'花费 {cost} 金币购买 {num} 个 {commodity["name"]}\n如无误请输入"确认"完成购买，输入其它信息将取消操作'))
    else:
        await shopping.reject()

@shopping.receive()
async def buy(bot: Bot, event: MessageEvent, state: T_State):
    if event.message.extract_plain_text().strip() == '确认':
        index = state['index']
        num = state['num']
        user :UserLevel = state['user']
        commodity = state['shelf'].goods[index]
        cost = commodity['price'] * num
        shelf_ :Shelf = state['shelf']
        await user.turnover(-cost)
        await shelf_.sold(index, num)
        item_class = cls_map(commodity['type'])
        if issubclass(item_class, BaseTool):
            # TODO: 修改物品类中的decription属性的位置
            tool = item_class(event.user_id, commodity['name'])