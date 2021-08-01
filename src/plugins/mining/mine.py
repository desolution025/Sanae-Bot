from random import random, randint, choice, choices, gauss
from datetime import datetime
from typing import Tuple, Optional, Union, Sequence
from collections import defaultdict

from nonebot.exception import FinishedException

from src.common import logger
from src.common.levelsystem import UserLevel
from src.utils import cgauss, map_rate
from .orb import *


CARD_LIST = []  # 符卡列表
ITEM_LIST = []  # 物品列表

miner = {
    'uid': {
        'time': datetime,  # 最后一次入场时间
        'cooling': int,  # 最后一次入场时开始的冷却时间，以分钟为单位
        'status': []  # 状态列表
    }
}

record = {
    'uid': int,  # 用户id
    'admission': datetime,  # 入场时间
    'cooling': int,  # 最后一次入场时开始的冷却时间，以分钟为单位
    'toll': int,  # 交付的费用
    'items': [],  # 使用的符卡
    'income': int,  # 获得的收入（金币）
    'reward': [str],  # 获得的奖励（道具之类）
}

distributions = {
    'name': float  # 道具名称及产出概率
}

reward = {
    'cards': {'name': int},
    'items': [{}]
}


Mines_Collection = {}  # 所有当前可以开采的矿洞


class Mine:
    """矿洞类

    Attributes:
        number (int): 矿场编号
        owner (int): 矿场主
        location (int): 开矿地点，用于交互报告时通知矿场主的位置，群号，私聊开矿的则为0
        start_up_captital (int): 启动资金
        stability (int): 结构稳定性
        breadth (int): 空间宽广度，代表单次符卡使用次数限制
        oof_prob (int): 金矿出产率，钱
        card_prob (int): 卡片出产率，符卡
        item_prob (int): 物品出产率，卡片之类的
        fee (int): 当前入场费
        depth (int): 当前深度
        coll_prob (float): 当前坍塌率，随着深度加高
        income (int): 当前获得的收入
        distributions (Dict): 矿产分布，这个矿洞能产出的道具以及比率，比率应该会随着深度而成连续噪波变化
        status (list): 状态，如加固、脆弱、矿产率上升下降之类的为key，状态内也为dict，记录剩余持续时间、剩余持续深度、
        miners (Dict): 玩家列表，记录玩家冷却
        sheet (list): 行动表，记录每次挖矿的玩家及其使用的符卡与获得的道具等信息
    """
    def __init__(self, owner: int,  # 矿场主
                location: int, # 开矿地点，用于交互报告时通知矿场主的位置，群号，私聊开矿的则为0
                start_up_capital: int, # 启动资金
                **kw) -> None:
        """开发一个新的矿洞，随机生成稳定性，各种矿产出现率以及矿产分布

        Args:
            owner (int): 矿场主id
            location (int): 开矿地点，用于交互报告时通知矿场主的位置，群号，私聊开矿的则为0
            start_up_capital (int): 启动资金，越高越容易开发到结构稳定性高的矿洞，出产的金矿越多，产出的卡片道具概率越高，某些稀有卡片一定要有一定的资产
            **kw: 其它矿洞参数，一并传入所有参数则不会初始化矿洞数据而是从数据库中获得矿洞实例
        """
        self.owner, self.location, self.start_up_capital = owner, location, start_up_capital

        if kw:
            for k, v in kw.items():
                setattr(self, k, v)
        else:
            self.stability = cgauss(map_rate(self.start_up_capital, 200, 1000, 20, 50), 5, 5, 95)  # 根据初始资金随机一个初始稳定度
            self.oof_prob  = cgauss(map_rate(self.start_up_capital, 200, 1000, 5, 20), 1.8, 0, 100)  # 金矿出产率，钱
            self.card_prob = cgauss(map_rate(self.start_up_capital, 200, 1000, 5, 20), 1.8, 0, 100)  # 卡片出产率，符卡
            self.item_prob = cgauss(map_rate(self.start_up_capital, 200, 1000, 5, 20), 1.8, 0, 100)  # 物品出产率，卡片之类的
            self.breadth = 1  # 空间宽广度初始一定是1
            self.fee = round(self.start_up_capital / 20)  # 当前入场费，随回合数上涨
            self.depth = 0  # 当前深度，随回合数上涨
            self.coll_prob = self.gen_base_coll_prob()  # 初始坍塌率
            self.income = 0  # 当前获得的收入
            self.distributions = {}  # 矿产分布，这个矿洞能产出的道具以及比率，比率应该会随着深度而成连续噪波变化
            self.status = []  # 状态，如加固、脆弱、矿产率上升下降之类的为key，状态内也为dict，记录剩余持续时间、剩余持续深度、
            # self.miners = {}  # 玩家列表，记录玩家冷却，数据库中单独在一个表里
            self.sheet = []  # 行动表，记录每次挖矿的玩家及其使用的符卡与获得的道具等信息，数据库中单独在一个表里

            while True:
                self.number = randint(1, 1000)
                if self.number not in Mines_Collection:
                    break

        Mines_Collection[self.number] = self  # 存入全局矿洞列表中

    @staticmethod
    def get_mine(mid: int):
        """如果有矿洞可开发返回矿洞实例，否则返回None"""
        if mid in Mines_Collection:
            return Mines_Collection[mid]
        else:
            return None

    @staticmethod
    def get_all_mines():
        """返回当前正在开发的所有矿洞列表"""
        return Mines_Collection

    async def store_mine(self):
        """将自己存入数据库进行持久化"""
        await regist_miner(self.owner)
        await dev_mine(self)

    def gen_base_coll_prob(self):
        """生成一个适合用于初始坍塌率的float，概率以0.005为轴成高斯分布"""
        prob = gauss(0.00001, 0.000001)
        if prob < 0 or prob > 1:  # 防止撞大运生成0-1范围外的几率
            return self.gen_base_coll_prob()
        else:
            return prob

    def coll_prob_up(self):
        """坍塌率上升 上涨幅度与结构稳定性和深度相关，其中有影响不是很大的随机因子"""
        coll_up = 0.00001 / self.stability ** 1.1 + self.depth ** 1.5 * 0.0000001 / self.stability + (random() - 0.5) * 0.000002
        self.coll_prob += coll_up
        return coll_up
    
    def deepen(self, tool, cards, cru_op):
        """迭代计算掘进，数据存入当前采掘记录中

        Args:
            tool (str): 使用的采掘工具
            cards (List): 使用的符卡
            cru_op (Dict): 当前采掘记录
        Returns:
            tuple: 是否坍塌
        """
        depth = round(tool.speed * tool.strength / (self.depth + tool.strength))  # 预计掘进深度
        # 计算掘进是否坍塌
        start_depth = self.depth
        for i in range(depth):
            if random() > self.coll_prob:
                self.coll_prob_up()
                self.depth += 1
                cru_op['income'] += self.get_oof(cards)  # 增加金币产出
                for c in self.get_card(cards):
                    cru_op['reward']['cards'][c] += 1  # 增加符卡产出
                cru_op['reward']['item'].extend(self.get_item(cards))  # 增加道具产出
            else:
                # 坍塌，直接计算到达坍塌点的冷却，但暂时还不能使用这种模式
                # cooling = round(self.depth + depth)
                if 'escape' not in cards:  # 逃脱符依然能获得奖励
                    cru_op['income'] = 0
                    cru_op['reward'] = {
                                        'cards': {},
                                        'items': []
                                        } # 坍塌的话奖励清除
                collpase = True
                break
        else:
            # 未坍塌，计算到达最新掘进深度
            collpase = False
            cru_op['cooling'] = round(2 * self.depth + depth)
        cru_op['depth'] = self.depth - start_depth
        return collpase

    def price_increase(self, tool):
        """入场费算法，与使用的工具、当前层数与矿场主初始投入资金相关 TODO：还是不太科学"""
        self.fee = round(self.start_up_capital * (self.depth ** 0.7 + 10) ** 0.5 * 0.0004 * tool['speed'])

    def breadth_change(self):
        """随机改变宽度  TODO: 优化更新宽度算法"""
        up_prob = 0.3 ** self.breadth  # 上升概率，当前宽度越高越难升
        down_prob = 0.25  # 下降概率，暂定常数
        dice = random()  # 获取一个随机数
        if dice < up_prob:
            self.breadth += 1
            return 1
        elif self.breadth > 1 and dice < down_prob:
            self.breadth -= 1
            return -1
        return 0

    def get_oof(self, cards: Sequence[str]):
        """产出金币

        产出的概率与数额应该随depth加大而加大
        TODO: 设计概率与数额算法
        """
        randint(round(self.depth / 50), round(self.depth / 8))
        if self.oof_prob * self.depth > random():
            return self.depth * self.fee
        else:
            return None

    def get_card(self, cards: Sequence[str]):
        """产出符卡

        对可能产出的每个符卡进行概率计算，概率与depth和矿洞的符卡产出率应成正相关
        TODO: 设计符卡产出概率
        """
        prob = (((1 + 0.00004 * self.depth) / (0.00004 * self.depth)) ** (0.00004 * self.depth) - 1 + self.card_prob * 0.0001) * 55
        logger.debug(f'当前第{self.depth}层随机到出产符卡概率: {prob}')
        if random() < prob:
            cardls = [card for card in self.distributions if card in CARD_LIST]
            probls = [self.distributions[c] for c in cardls]
            card = choices(population=cardls, weights=probls)
            return card[0]
        else:
            return None
            
    def get_item(self, cards: Sequence[str]):
        """产出道具
        
        计算方式与符卡类似，TODO: 考虑是否要分开计算，还是合并计算
        """
        prob = (((1 + 0.00004 * self.depth) / (0.00004 * self.depth)) ** (0.00004 * self.depth) - 1 + self.item_prob * 0.0001) * 55
        logger.debug(f'当前第{self.depth}层随机到出产道具概率: {prob}')
        if random() < prob:
            itemls = [item for item in self.distributions if item in ITEM_LIST]  # 物体列表
            probls = [self.distributions[p] for p in itemls]  # 概率列表
            item = choices(itemls, probls)
            return item[0]
        else:
            return None

    async def dig(self, uid: int, cards: Sequence[str]):
        """执行开采

        Args:
            uid (int): 开采者ID

        Returns:
            Tuple[Bool, Optional[Tuple]]: 返回是否坍塌以及开采者获得的奖励，True为未坍塌，可继续开采
        """
        await regist_miner(uid)
        toll = self.fee  # 收取的费用
        if toll:
            self.income += self.fee
            async with UserLevel(uid) as miner:
                await miner.turnover(-toll)
        
        # 增加一条新的挖矿记录
        cru_op = {
                    'uid': uid,  # 用户id
                    'time': datetime.now(),  # 入场时间
                    'cooling': 0,  # 再次进入此矿洞的冷却
                    'toll': toll,  # 交付的费用
                    'items': cards,  # 使用的符卡
                    'depth': 0, # 掘进的深度
                    'income': 0,  # 获得的收入（金币）
                    'reward': {
                            'cards': defaultdict(int),
                            'items': []
                            },  # 获得的奖励（道具之类）
                    'influence': {'collapse': False}  # 对矿洞造成的影响，用于上报信息
                }
        self.sheet.append(cru_op)

        collapse = self.deepen('', cards, cru_op) 
        if not collapse:
            self.price_increase()
            breadth_change = self.breadth_change()

            # 更新矿洞和矿工记录 TODO：根据status变化有不同的传入数据
            if breadth_change:
                cru_op['influence']['breadth'] = breadth_change
            await update_mine(self)

        else:  # 触发坍塌
            cru_op['influence']['collpase'] = True
            await self.collapse(uid)
        return cru_op

    async def collapse(self, vimtim: int):
        # self.status.append('collapse')
        del Mines_Collection[self.number]
        await mine_collapse(self, vimtim)


def mining_count(uid: int) -> int:
    """查询用户当前正在开发的矿场数量"""
    count = 0
    for i, mine in Mines_Collection.items():
        if mine.owner == uid:
            count += 1
    return count


def upper_limit(level: int) -> int:
    """当前等级可以同时开启的矿场上限

    暂定为从3级开始每两级可以开一个
    """
    if not level:
        return 0
    return (level - 1) // 2


def mining_list():
    unit_info = []
    for i in Mines_Collection:
        mine : Mine = Mines_Collection[i]
        info = f"""
编号：{mine.number}
当前深度：{mine.depth}
本次入场费：{mine.fee}
结构稳定性：{mine.stability}
金矿出产系数：{mine.oof_prob}
符卡出产系数：{mine.card_prob}
物品出产系数：{mine.item_prob}
当前坍塌率：{round(mine.coll_prob, 4) * 100}%
已知发掘物：{'、'.join([item for item in mine.distributions])}
当前附加状态：{'、'.join([buff['name'] for buff in mine.status])}
""".strip()
        unit_info.append(info)
    
    return '\n——————————\n'.join(unit_info)