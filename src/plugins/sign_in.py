from typing import Optional
from datetime import datetime, date

from nonebot import MatcherGroup, get_driver

from src.common import Bot, MessageEvent, T_State
from src.utils import reply_header, cgauss
from src.common.levelsystem import UserLevel, exp_step
from src.common.dbpool import QbotDB


driver = get_driver()

@driver.on_startup
async def read_users_data():
    await UserLevel.load_users_data()


# 一个进度条用来显示经验值进度
def progress_bar(value: int, max: int) -> str:
    """进度条样式 ┃██████░░░░┃

    Args:
        value (int): 当前值
        max (int): 最大值

    Raises:
        ValueError: value can't larger than max

    Returns:
        str: 进度条样式
    """
    if value > max:
        raise ValueError("value can't larger than max")

    if max == 0:
        return '┃██████████┃'

    pct = value / max

    # 在很小或者很大的两个特殊区间会加入半个方块的字符，但无法在中间添加不然造成字符不连续
    if pct >= 0.025 and pct < 0.05:
        fill = '▐'
        empty = '░' * 9
    elif pct > 0.95 and pct <= 0.975:
        fill = '█' * 9 + '▌'
        empty = ''
    elif pct < 0:
        fill = ''
        empty = '░' * 10
    else:
        bk_amt = round(pct * 10)
        fill = '█' * round(bk_amt)
        empty = '░' * (10 - bk_amt)
    
    return '┃%s┃'%(fill + empty)


level_sys = MatcherGroup(type="message")


def sign_rule(bot: Bot, event: MessageEvent, state: T_State):
    if len(event.message.extract_plain_text().strip()) < 2:
        return True
    # TODO:看看comand里的rule中message是不是去除命令和昵称了

sign = level_sys.on_command("签到")

@sign.handle()
async def sign_(bot: Bot, event: MessageEvent):
    uid = event.user_id
    async with UserLevel(uid) as user:

        # 是否可以签到
        today = date.today()
        last_sign_day = user.last_sign.date()

        if today > last_sign_day:
            async with QbotDB() as botdb:
                await botdb.update('update userinfo set `last_sign`=NOW(), total_sign=total_sign+1 where qq_number=%s;', (uid,))
            
            gndexp = cgauss(8, 2, 0)
            gndfund = cgauss(25, 3, 0)

            await user.expup(gndexp, bot, event)
            await user.turnover(gndfund)
            await sign.send(reply_header(event, f'感谢签到，经验值+{gndexp}，资金+{gndfund}!'))
        
        else:
            await sign.finish(reply_header(event, '今天你已经签到过了哦~'))


query_level = level_sys.on_command('查询等级', aliases={'等级查询'})

@query_level.handle()
async def querylevel(bot: Bot, event: MessageEvent):
    uid = event.user_id
    async with UserLevel(uid) as user:
        if event.message_type == 'group':
            name = event.sender.card or event.sender.nickname
        else:
            name = event.sender.nickname
        msg = ' {name}\n 等级：Lv.{level}\n{pg_bar}\n EXP:{exp}/{max}\n 金币:{fund}\n 共签到：{total_sign}次\n 最后一次签到：\n {last_sign}'.format(
            name = name,
            level = user.level,
            pg_bar = progress_bar(user.exp, exp_step(user.level)),
            exp = user.exp,
            max = exp_step(user.level),
            fund = user.fund,
            total_sign = user.total_sign,
            last_sign = user.last_sign if user.last_sign > datetime(2020, 11, 27) else '还未签到过'
            )
        await query_level.finish(msg)

# TODO: 连续签到天数