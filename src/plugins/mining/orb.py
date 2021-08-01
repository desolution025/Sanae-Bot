from typing import List, Dict, Optional
from datetime import datetime
import ujson as json
from src.common import logger
from src.common.dbpool import QbotDB, AttrDict


async def refresh_mining():
    """刷新正在开发的矿洞数据"""
    async with QbotDB() as qb:
        result : Dict[AttrDict]= await qb.queryall("SELECT `mid`, `owner`, location, start_up_capital, stability, breadth, oof_prob, card_prob, item_prob, fee, depth, coll_prob, income, distributions, `status` FROM mine;")
        from .mine import Mine
        for r in result:
            params = {}
            for k, v in r.items():
                k = 'number' if k == 'mid' else k  # 矿洞的编号在数据库里是mid，类属性是number
                v = json.loads(v) if k in ('distributions', 'status') else v
                params[k] = v
            Mine(**params)
        logger.success(f'连接数据库，读取到 {len(result)} 条矿洞记录')


Miners_List = set()

async def refresh_miners_list() -> Optional[int]:
    """刷新矿工数据列表 """
    async with QbotDB() as qb:
        result = await qb.queryall("SELECT `uid`, achievement, `status` FROM miners")
    global Miners_List
    Miners_List = set([r.uid for r in result])
    logger.success(f'连接数据库，读取到 {len(result)} 条矿工')
    if len(result) != len(Miners_List):
        dp_count = len(result) - len(Miners_List)
        logger.warning(f'There is {dp_count} duplicate data(s) in miners!!')


async def regist_miner(uid: int):
    """注册矿工到数据库"""
    global Miners_List
    if uid not in Miners_List:
        async with QbotDB() as qb:
            await qb.insert("""INSERT INTO miners
                            (uid, mine_number, deepest_reach, shallowest_collapse, collapse_number, dev_number, deepest_keep, fastest_collapse, max_income, min_income, break_even, achievement, status)
                            VALUES (%s, 0, NULL, NULL, 0, 0, NULL, NULL, 0, 0, 0, '', '');""", (uid,))
            logger.info(f'Insert a new miner {uid} into database!')
        Miners_List.add(uid)

        
async def dev_mine(mine):
    """将新开发的矿洞存在数据库"""
    cmd = """INSERT INTO mine (
        `mid`,
        `owner`, location, start_up_capital, stability, breadth,
        oof_prob, card_prob, item_prob,
        fee, depth, coll_prob,
        income,
        distributions,
        `status`)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"""
    params = (mine.number, mine.owner, mine.location, mine.start_up_capital,
            mine.stability, mine.breadth, mine.oof_prob, mine.card_prob,
            mine.item_prob, mine.fee, mine.depth, mine.coll_prob, mine.income,
            json.dumps(mine.distributions),
            json.dumps(mine.status))

    async with QbotDB() as qb:
        await qb.insert(cmd, params)  # 直接创建矿场记录

        # 更新矿场主信息
        await qb.update("UPDATE miners SET dev_number=dev_number+1 WHERE uid=%s;", (mine.owner,))


async def update_mine(mine, op: Dict, *, stability=False, breadth=False, oof_prob=False, card_prob=False, item_prob=False,
                    fee=True, depth=True, coll_prob=True, income=True, distributions=True, status=False):
    """更新矿洞数据库信息，进行普通挖矿作业时调用

    命名关键字参数传入True的会更新
    Args:
        mine (Mine): 矿洞实例
        stability (bool, optional): 稳定度. Defaults to False.
        breadth (bool, optional): 矿洞宽度. Defaults to False.
        oof_prob (bool, optional): 金币出产率. Defaults to False.
        card_prob (bool, optional): 符卡出产率. Defaults to False.
        item_prob (bool, optional): 道具出产率. Defaults to False.
        fee (bool, optional): 当前入场费. Defaults to True.
        depth (bool, optional): 当前深度. Defaults to True.
        coll_prob (bool, optional): 当前坍塌概率. Defaults to True.
        income (bool, optional): 当前总共收入. Defaults to True.
        distributions (bool, optional): 当前矿产分布. Defaults to True.
        status (bool, optional): 矿洞当前状态. Defaults to False.
    """
    async with QbotDB() as qb:
        # 更新矿洞信息
        updable = ['stability', 'breadth', 'oof_prob', 'card_prob', 'item_prob', 'fee', 'depth', 'coll_prob', 'income', 'distributions', 'status']
        to_up = []
        params = []
        for i, p in enumerate([stability, breadth, oof_prob, card_prob, item_prob, fee, depth, coll_prob, income, distributions, status]):
            if p:
                to_up.append(f'{updable[i]}=%s')
                pram = getattr(mine, updable[i]) if i < 9 else json.dumps(getattr(mine, updable[i]))
                params.append(pram)
        params.append(mine.number)
        logger.debug(f'update mine attrs: {to_up}')
        if to_up:
            await qb.update("UPDATE mine SET {} WHERE `mid`=%s".format(', '.join(to_up)), tuple(params))
        
        # 更新执行此次采掘的矿工数据
        await qb.update("UPDATE miners SET mine_number=mine_number+1, deepest_reach=GREATEST(IFNULL(deepest_reach, 0), %s) WHERE uid=%s",
                        (mine.depth, op['uid']))

        # 更新矿洞入场记录
        await qb.insert("INSERT INTO mining_sheet (`mid`, uid, admission, cooling, toll, items, income, reward, influence) VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s)",
                        (mine.number, op['uid'], op['cooling'], op['toll'], json.dumps(op['items']), op['income'], json.dumps(['reward']), json.dumps(['influence'])))


async def mine_collapse(mine, vimtim: int):
    """
    矿洞坍塌数据库更新

    Args:
        mine (Mine): 坍塌的矿洞实例
        vimtim (int): 挖塌此矿洞的矿工
    """
    async with QbotDB() as qb:
        await qb.begin()

        # 更新执行本次开采的矿工的记录
        await qb.update("UPDATE miners SET collapse_number=collapse_number+1, shallowest_collapse=LEAST(IFNULL(shallowest_collapse, 999), %s) WHERE uid=%s;", (mine.depth + 1, vimtim))

        # 更新矿场主的矿工记录
        ownerinfo = await qb.queryone("SELECT deepest_keep, fastest_collapse, max_income, min_income, break_even FROM miners WHERE uid=%s LIMIT 1;", (mine.owner,))
        to_update = {}
        if ownerinfo.deepest_keep is None or ownerinfo.deepest_keep < mine.depth:
            to_update['deepest_keep'] = mine.depth
        if ownerinfo.fastest_collapse is None or ownerinfo.fastest_collapse > mine.depth:
            to_update['fastest_collapse'] = mine.depth
        if ownerinfo.max_income < mine.income:
            to_update['max_income'] = mine.income
        if ownerinfo.min_income > mine.income:
            to_update['min_income'] = mine.income
        if mine.income == 0:
            to_update['break_even'] = ownerinfo.break_even + 1

        if to_update:
            upset = ', '.join([f'{k}={v}' for k, v in to_update.items()])
            await qb.update("UPDATE miners SET {} WHERE uid=%s;".format(upset), (mine.owner,))

        # 记录坍塌的矿洞信息
        await qb.insert("INSERT INTO mine_collapsed (`owner`, depth, victim, start_up_capital, income) SELECT `owner`, depth, %s, start_up_capital, income FROM mine WHERE `mid`=%s;",
        (vimtim, mine.number))

        # 从正在开发的矿洞列表中移除
        await qb.delete("DELETE FROM mine WHERE `mid`=%s;", (mine.number,))  # 删除当前的矿洞
        await qb.delete("DELETE FROM mining_sheet WHERE `mid`=%s;", (mine.number,))  # 删除此矿洞的行动表


__all__ = ("regist_miner", "dev_mine", "update_mine", "mine_collapse")