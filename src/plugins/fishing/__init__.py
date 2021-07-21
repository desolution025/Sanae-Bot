from datetime import datetime, timedelta
from random import random, randint
from typing import Union
from asyncio import sleep as asleep

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.job import Job
from nonebot import MatcherGroup, require
from nonebot.rule import Rule

from src.common import Bot, MessageEvent, T_State, logger
from src.common.rules import sv_sw
from src.utils import reply_header
from .angler import Angler


plugin_name = "钓鱼"
plugin_usage = ""


def get_name(event: MessageEvent) -> str:
    """获得sender的名称，昵称优先度为群昵称>qq昵称>qq号"""
    name = event.sender.card if event.message_type == 'group' else event.sender.nickname
    if not name.strip():
        name = event.get_user_id()
    return name


def randomfloat(min: Union[int, float], max: Union[int, float]) -> float:
    """随机返回一个两个值中间的浮点数

    Args:
        min (Union[int, float]): 最小能取到的范围
        max (Union[int, float]): 最大能取到的范围

    Returns:
        float: min与max之间的随机浮点数
    """
    return (max - min) * random() + min


async def bite(bot: Bot, event: MessageEvent, angler: Angler, could_bit: bool):
    logger.debug(f"获得钓者：{type(angler)}")
    if not could_bit:
        angler.fail()
        await bot.send(event, '过了好久，并没有鱼上钩...')
        return
    await bot.send(event, '有鱼咬钩啦！！')
    angler.bit_time = datetime.now()
    logger.debug(f'咬钩时间{angler.bit_time}')
    await asleep(3)
    logger.debug('已到超时时间！')
    await break_free(bot, event, angler)


async def break_free(bot: Bot, event: MessageEvent, angler: Angler):
    if angler.pull_up_time is None:
        angler.fail()
        await bot.send(event, '好可惜，鱼挣脱鱼钩跑掉了..')


fishing = MatcherGroup(type="message", priority=2)
scheduler : AsyncIOScheduler = require('nonebot_plugin_apscheduler').scheduler


#——————————————————抛竿——————————————————#


async def is_free(bot: Bot, event: MessageEvent, state: T_State):
    """用户是否可以钓鱼的规则"""
    cmd = event.message.extract_plain_text().strip()
    if cmd.startswith(('钓鱼', '抛竿', '甩竿', '出竿')):
        rod = cmd[2:].lstrip().split(' ')[0]
        if rod and not rod.isdigit():
            return False
        state['rod'] = int(rod) if rod else None
        logger.debug(f'{Angler.cluster}')
        al = Angler(event.user_id)
        logger.debug(f'用户 {event.user_id} 空闲状态：{al.free()}')
        if al.free():
            state['al'] = al
            al.cast()
            return True



cast = fishing.on_message(rule=is_free)


@cast.handle()
async def casting(bot: Bot, event: MessageEvent, state: T_State):
    logger.debug('开始钓鱼')
    al = state['al']
    rod = state['rod']
    msg = (f'> {get_name(event)}\n')  # 头部标记玩家昵称
    if rod is None:
        rod = 1
        msg += '未指定钓竿，使用默认钓竿 1 号\n'
    else:
        # if not arg.isdigit():
        #     al.fail()
        #     await cast.finish(reply_header(event, '钓竿编号为数字，请重新指定钓竿'))
        if rod != 1:
            al.fail()
            await cast.finish(reply_header(event, '没有从你的物品列表中找到2号钓竿~'))
        if rod == 1:
            msg += f'使用 {rod} 号钓竿钓鱼\n'
    
    if random() < 0.1:
        bit_time = datetime.now() + timedelta(seconds=12)
        could_bit = False
        logger.debug('此次钓鱼不会有鱼上钩')
    else:
        delay = randomfloat(5, 12)
        bit_time = datetime.now() + timedelta(seconds=delay)
        could_bit = True
        logger.debug(f'鱼会延迟 {round(delay, 2)} 秒上钩')

    msg += '钓竿品级：普通\n钓竿属性：无\n鱼儿可能在5-12秒内上钩，请注意收杆时间哦~'
    await cast.send(msg)
    scheduler.add_job(bite, trigger='date', run_date=bit_time, id=f'fishing_{event.get_user_id()}', args=[bot, event, al, could_bit], misfire_grace_time=10)


#——————————————————收杆——————————————————#


async def is_fishing(bot: Bot, event: MessageEvent, state: T_State):
    if event.message.extract_plain_text().strip() in ('收竿', '起竿'):  # TODO: 试着这样把命令集成在rule中来尽量减少时间差造成的影响
        al = Angler.get_angler(event.user_id)
        if al:
            al.pull_up_time = datetime.now()
            state['al'] = al
            if al.bit_time is None:
                job :Job = scheduler.get_job(f'fishing_{event.get_user_id()}')
                if job:
                    job.remove()
                state['early'] = True
            return True
        logger.debug('用户不在钓鱼中，没收竿')


pullup = fishing.on_message(rule=is_fishing)
 

@pullup.handle()
async def caught(bot: Bot, event: MessageEvent, state: T_State):
    logger.debug('开始收竿')
    al : Angler = state['al']
    reply = lambda m: reply_header(event=event, text=m)
    if 'early' in state:
        al.fail()
        await pullup.finish(reply('Wrong time，并没有鱼咬钩..'))
    reaction_time : timedelta = al.pull_up_time - al.bit_time
    logger.debug(f'此次钓鱼用了{reaction_time}反应时间')
    rt = reaction_time.total_seconds()
    oof = round((1 - rt / 3) * 15)  # TODO: 获得奖励应该以高斯分布计算
    fish = f'鱼类{randint(1, 24)}'  # TODO：物品奖励
    if rt < 0.3:
        speed = '快到极致的收竿速度！\n你一定是单身吧！！'
    elif rt < 0.6:
        speed = '好犀利的收竿！\n像你这样的钓者即使在NGA也少见呢！'
    elif rt < 1:
        speed = '精准而优雅的收竿！\n每天要上网多少小时才能练就这样的钓鱼技术呢？'
    elif rt < 1.5:
        speed = '从容不迫的收竿。\n大部分鱼的智商都不足与你抗衡呢~'
    else:
        speed = '收竿的节奏还需磨练。\n不过所谓运气也是实力的一部分嘛~'
    al.pull_up()
    await pullup.finish(reply(f'钓到鱼啦！用了{round(rt, 3)}秒反应！\n{speed}\n钓到的是{fish}，并且收到{oof}金币作为额外奖励'))