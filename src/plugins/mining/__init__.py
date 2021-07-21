from functools import partial
from random import choice
from typing import Union
from asyncio import sleep as asleep

from nonebot import MatcherGroup, get_driver
from nonebot_adapter_gocq.exception import ActionFailed

from src.common import Bot, MessageEvent, MessageSegment, T_State, CANCEL_EXPRESSION, inputting_interaction
from src.common.log import logger
from src.common.rules import full_match, sv_sw
from src.common.levelsystem import UserLevel
from .mine import *
from .orb import refresh_miners_list
from src.utils import reply_header


plugin_name = '挖矿'
plugin_usage = ''


#——————————————————读取数据库——————————————————#

driver=get_driver()

@driver.on_startup
async def read_mine_db():
    await refresh_miners_list()

#—————————————————————————————————————————————#


mining = MatcherGroup(type='message', rule=sv_sw(plugin_name, plugin_usage), priority=2)


#——————————————————开矿——————————————————#


open_mine = mining.on_message(rule=full_match(('开矿场', '开矿洞'))&sv_sw(plugin_name, plugin_usage))


@open_mine.handle()
async def can_start(bot: Bot, event: MessageEvent, state: T_State):
    uid = event.user_id
    user = UserLevel(uid)
    reply = lambda m: reply_header(event=event, text=m)
    
    # 小于三级或者资金不足200的用户不能开启矿场
    if user.level < 3:
        await open_mine.finish(reply('开发矿场最小需要3级，先作为开采者开采其它矿场主的矿洞吧~'))
    if user.fund < 200:
        await open_mine.finish(reply('开发矿场最少需要200的启动资金，金额充足时再成为矿场主吧~'))
    # 开发矿场数量超出限制
    if mc := mining_count(uid) >= upper_limit(user.fund):
        await open_mine.finish(reply(f'您当前已同时运作{mc}个矿场，提升等级可以增加同时运作矿场的数量哟~'))
    
    # 条件满足，询问投资数据
    state['user'] = user
    await open_mine.send(f'您当前资金为 {user.fund}，请输入需要为该矿场投入的资金\n(投入资金与该矿场产出率成正比，范围200-1000)\n输入"取消"退出本操作', at_sender=True)


def verify_investment(bot: Bot, event: MessageEvent, state: T_State):
    """投资验证，需输入200-1000以内的数字"""
    arg = event.message.extract_plain_text().strip()
    if not arg.isdigit():
        return False
    arg = int(arg)
    if arg < 200 or arg > 1000:
        return False
    state['capital'] = arg
    return True


@open_mine.receive()
@inputting_interaction(cancel_expression=CANCEL_EXPRESSION,
                        cancel_prompt='已退出开辟矿场操作',
                        verify_expression=verify_investment,
                        verify_prompt='请输入200-1000以内的数字参数，输入"取消"退出当前操作',
                        verify_addition='reply',
                        verify_cancel_prompt='连续输入三次错误，已自动为您退出当前操作',
                        verify_cancel_addition='reply')
async def invest(bot: Bot, event: MessageEvent, state: T_State):
    # 这里要读取用户符卡列表
    if True:
        state['cards'] = None
    else:
        await open_mine.pause('请选择要为此矿洞附加的符卡:\n\n输入"取消"退出当前操作', at_sender=True)

@open_mine.handle()
async def attach_card(bot: Bot, event: MessageEvent, state: T_State):
    if state['cards'] == None:
        return
    else:
        # 这里让用户输入符卡
        state['cards'] = 0

@open_mine.handle()
async def use_item(bot: Bot, event: MessageEvent, state: T_State):
    location = 0 if event.message_type == 'private' else event.group_id
    new_mine = Mine(owner=event.user_id, location=location, start_up_capital=state['capital'])
    UserLevel(event.user_id).turnover(-state['capital'])

    await new_mine.store_mine()

    name = event.sender.card if event.message_type == 'group' else event.sender.nickname
    if not name.strip():
        name = str(event.sender.user_id)

    msg = f"""您成功开发了一个新矿洞
——————————
矿场主：{get_name(event)}
矿洞编号：{new_mine.number}
结构稳定性：{new_mine.stability}
金矿出产系数：{new_mine.oof_prob}
符卡出产系数：{new_mine.card_prob}
物品出产系数：{new_mine.item_prob}
当前入场费：{new_mine.fee}
——————————
招募优秀的矿工来挖掘宝藏吧~
"""
    await open_mine.finish(msg)


#——————————————————采矿——————————————————#


conduct_mining = mining.on_command('开采', aliases={'挖矿, 采矿'})


@conduct_mining.handle()
async def conduct_args(bot: Bot, event: MessageEvent, state: T_State):
    args = event.message.extract_plain_text().strip().split('符卡')
    reply = lambda m: reply_header(event=event, text=m)

    if len(args) > 2:
        await conduct_mining.finish(reply('请勿指定多个符卡参数，参照使用说明'))

    # 解析矿洞编号
    mine_number = args[0]
    if not mine_number:
        await conduct_mining.send(reply('请先选择开采的矿洞编号:\n——————————\n' + mining_list() + '\n——————————\n输入"取消"退出操作'))
        return
    if not mine_number.isdigit():
        await conduct_mining.finish(reply('矿洞编号为数字参数，参照使用说明'))
    mine_number = int(mine_number)
    Mine_Coll = all_mines()
    if mine_number not in Mine_Coll:
        await conduct_mining.finish(reply('选择的编号不在开采列表中或已坍塌，先请查询可进行开采的矿洞列表'))
    state['number'] = mine_number
    logger.debug(f'用户直接指定矿洞编号：{mine_number}')

    # 解析符卡
    if len(args) == 2:
        cards = [c for c in args[1].split(' ') if c]  # 去除多余空格，只提取参数
        if not all(map(lambda c: c.isdigit(), cards)):
            await conduct_mining.finish(reply('符卡序号应为数字参数，参照使用说明'))
        if len(cards) > Mine_Coll[mine_number].breadth:
            await conduct_mining.finish(reply(f'选择的矿洞当前最大支持单次使用{Mine_Coll[mine_number].breadth}张符卡，请重新操作'))
        # TODO: 还要判断用户是否有符卡以及符卡序号是不是有真实对应
        state['cards'] = cards
    else:
        if True:
            logger.debug('用户没有任何符卡，跳过')
            state['cards'] = None


@conduct_mining.got('number')
@inputting_interaction(cancel_expression=CANCEL_EXPRESSION, cancel_prompt='已退出操作')
async def confirm_number(bot: Bot, event: MessageEvent, state: T_State):
    logger.debug("提示用户选择矿洞编号")
    arg = event.message.extract_plain_text()
    reply = lambda m: reply_header(event=event, text=m)
    if not arg.isdigit():
        await conduct_mining.finish(reply('矿洞编号为数字参数，参照使用说明'))
    mine_number = int(arg)
    if mine_number not in all_mines():
        await conduct_mining.finish(reply('选择的编号不在开采列表中或已坍塌，先请查询可进行开采的矿洞列表'))
    state['number'] = mine_number
    logger.debug(f"选择矿洞编号为{state['number']}")


@conduct_mining.got('cards')
async def confirm_cards(bot: Bot, event: MessageEvent, state: T_State):
    # TODO: 读取用户可使用符卡列表进行操作
    logger.debug('读取用户符卡')
    if state['cards'] is None:
        logger.debug('用户无符卡，跳过')
        return


@conduct_mining.handle()
async def mining_work(bot: Bot, event: MessageEvent, state: T_State):
    # 确保刚刚操作的时候这个矿洞没有被其他人挖塌
    if state['number'] not in all_mines():
        await conduct_mining.finish('噫！就在刚才这个矿洞坍塌了，该说是运气好呢还是~')
    
    target : Mine = all_mines()[state['number']]
    use_cards = state['cards'] if 'cards' in state and state['cards'] is not None else []
    logger.debug(f'对{target.number}号矿洞使用符卡:{use_cards}')
    
    update, rewards = await target.mine(uid=event.user_id, cards=use_cards)
    name = get_name(event)
    if update is not None:
        oof, cards, items = rewards
        if all(map(lambda x: not bool(x), rewards)):
            msg = '很遗憾没有挖到任何物品~'
        else:
            msg = '啊，开采到了什么!'
            if oof:
                msg += f'\n获得{oof}金币'
            if cards:
                msg += f'\n获得符卡{"、".join(cards)}'
            if items:
                msg += f'\n获得物品{"、".join(items)}'
        await conduct_mining.send(msg)
        await asleep(2)

        # 报告矿洞状态更新 TODO: 重大事件报告矿场主
        msg = f'{target.number}号深度增加到{target.depth}，由于{name}的采掘，'

        coll_up, fee_up, breadth_change = update

        if coll_up:
            msg += f'矿洞的坍塌率上升{coll_up}，'
        if breadth_change:
            if breadth_change == 1:
                msg += '挖掘到了宽松地带，矿洞宽度+1'
            elif breadth_change == -1:
                msg += '挖掘到了狭窄地带，矿洞宽度-1'
        await conduct_mining.finish(msg)

    else:
        await conduct_mining.send(f'{name}挖塌了{target.number}号矿洞！')
        await asleep(1.5)
        msg = f'''你的{target.number}号矿洞在深度为{target.depth}处遭遇坍塌，已关闭该矿洞的运营！
至坍塌为止，该矿洞一共被{len(target.miners)}名矿工采掘过，共创造了{target.income}的收入\n'''
        profit = target.income - target.start_up_capital
        if profit > 0:
            msg += f'此次运营你的净利润为{profit}金币，赠送你一张#4c88fda2符卡作为盈利的贺礼'
        elif profit < 0:
            msg += f'很遗憾的说，这次你的运气不太好，亏损了{-profit}金币，不过赠送您一张#8e9ffae符卡，下次好运！'
        elif profit == 0:
            msg += '你此次营收惊人的刚好回本，一分不差，很难说这不是奇迹呐！这里有一张特别的符卡送给你做礼物，希望幻想乡能维持像这营收一样的平衡！'
        # 为每种情况分别发送专属符卡，刚刚回本那个应该送个超稀有的，然后看看道具能送啥

        try:
            if target.location == 0:
                await bot.send_private_msg(user_id=target.owner, message=msg)
            else:
                await bot.send_group_msg(group_id=target.location, message=MessageSegment.at(qq=target.owner) + MessageSegment.text(msg))

        except ActionFailed as err:
            logger.error(ActionFailed)
            await conduct_mining.finish(f'咦？找不到{target.number}的矿场主了！该怎么联系到他呢...')