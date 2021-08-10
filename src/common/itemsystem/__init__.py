from typing import Dict, Optional
from pathlib import Path
import ujson as json

import yaml
from ..dbpool import QbotDB
from ..log import logger
from .status_list import *


CHARACTER_LIST = set()  # 符卡角色列表，抽取运势时根据这个列表随机选择


async def refresh_characters_ls():
    """刷新符卡角色列表"""
    global CHARACTER_LIST
    async with QbotDB() as qb:
        result = await qb.queryall("SELECT `character` from spell_cards;")
        CHARACTER_LIST = set([c.character for c in result])
    logger.success(f'读取到{len(CHARACTER_LIST)}个符卡角色')


Tools_Store = {}  # 存储所有工具列表，格式为{uid:[item, ...], ...}  存的是实例
Collections_Store = {}  # 存储所有收藏品列表，格式为{uid:{name: num, ...}, ...}  存的是数量，int


class BaseItem:
    """
    基本物品类，不应有物品直接通过此类实例化
    
    Attributs:
        id (int): 物品编号
        type (str): 物品类型
        owner (int): 物品所属者
        name (str): 物品名字
        description (Optional[str]): 物品描述
    """
    cls_type = 'baseitem'

    def __init__(self, owner: int, name: str, description: Optional[str]=None) -> None:
        """创建物品，创建完需要使用store方法来给用户绑定

        Args:
            owner (int): 物品所属者id
            name (str): 物品名字
            description (Optional[str]): 物品描述.Default is None.
        """
        self.owner = owner
        self.name = name
        self.description = description 


class BaseTool(BaseItem):
    """
    基本工具类，不应有工具直接通过此类实例化，使用此类的子类实例化

    工具类的实例为每个都是独立实例，每个实例有单独的状态，通常是附魔而来
    每个实例可以单独命名，以在使用时通过名字直接调用指定的实例
    Attributs:
        id (int): 物品编号
        type (str): 物品类型
        owner (int): 物品所属者
        name (str): 物品名字
        status (List[Dict]): 物品状态、buff
    """
    cls_type = 'basetool'
    _charcteristic = () # 特殊属性，对子类来说要定义特殊属性在序列化到数据库的时候将属性放到status中

    def __init__(self, owner: int, name: str) -> None:
        super().__init__(owner, name)
        self.id = None
        self.status = {}

    async def store(self):
        """持久化存储物品，存储方式为单个实例为一条记录"""
        global Tools_Store
        async with QbotDB() as qb:
            if self.owner in Tools_Store:
                Tools_Store[self.owner].append(self)
            else:
                Tools_Store[self.owner] = [self]
            await qb.insert('INSERT INTO items (`type`, `owner`, `name`) VALUES (%s, %s, %s)', 
                            (self.type, self.owner, self.name))
            last = await qb.queryone('SELECT LAST_INSERT_ID();')
            self.id = last['LAST_INSERT_ID()']
            logger.info(f'用户 {self.owner} 获得物品 {self.name}，编号 {self.id}')

    async def give_name(self, name: str):
        """给物品命名"""
        self.name = name
        async with QbotDB() as qb:
            await qb.update('UPDATE items SET `name`=%s WHERE `ID`=%s;', (name, self.id))
            logger.info(f'用户 {self.owner} 将物品 {self.id} 重命名为 {name}')
    
    async def add_descipition(self, description: str):
        """添加或修改物品的描述"""
        self.description = description
        async with QbotDB() as qb:
            await qb.update('UPDATE items SET `description`=%s WHERE `ID`=%s;', (description, self.id))
            logger.info(f'用户 {self.owner} 将物品 {self.id} 描述更改为 {description}')

    def _format_status(self):
        """子类物品的专属属性要单独处理到status中再序列化到数据库"""
        if self.__class__._charcteristic:
            status = self.status.copy()
            status['args'] = {}
            for arg in self.__class__._charcteristic:
                status['args'][arg] = getattr(self, arg)
            return status
        else:
            return self.status

    def _attrs_from_status(self):
        """读取数据库里的status属性，提取专属属性还原给实例，用于初始化时读取数据库记录"""
        assert bool(self.__class__._charcteristic) and 'args' in self.status, '不是将属性添加到status中的序列化的status，检查属性源'
        if self.__class__._charcteristic:
            for arg, value in self.status['args'].items():
                setattr(self, arg, value)
            del self.status['arg']

    async def _update_status(self, conn: Optional[QbotDB]=None):
        """
        状态更新时调用此方法传递给数据库
        
        Args:
            conn (Optional[QbotDB]): 数据库连接，上层函数中调用了链接池的话可以直接使用来节省开销.Default is None.
        """
        status = self._format_status()
        if conn is None:
            async with QbotDB() as qb:
                await qb.update('UPDATE items SET `status`=%s WHERE `ID`=%s;', (json.dumps(status), self.id))
        else:
            await conn.update('UPDATE items SET `status`=%s WHERE `ID`=%s;', (json.dumps(status), self.id))

    async def get_state(self, type: str, level: int=1):
        """获得状态"""
        self.status[type] = level
        await self._update_status()
        logger.debug(f'物品 {self.id} 获得状态 {type} {level}级')
        
    async def update_state(self, type: str, up: int=1):
        """升级状态"""
        self.status[type] += up
        await self._update_status()
        logger.debug(f'物品 {self.id} 的状态 {type} 升级到 {self.status[type]}级')

    async def clear_state(self, type: str):
        """清除状态"""
        del self.status[type]
        await self._update_status()
        logger.debug(f'物品 {self.id} 消除了状态 {type}')

    async def destroy(self):
        """销毁物品"""
        global Tools_Store
        async with QbotDB() as qb:
            Tools_Store[self.owner].remove(self)
            await qb.insert('DELETE FROM items where `ID`=%s;', (self.id,))
            logger.info(f'用户 {self.owner} 销毁了物品 {self.name}，编号 {self.id}')

    async def transfer(self, sendee: int):
        """转让物品"""
        global Tools_Store
        async with QbotDB() as qb:
            org_owner = self.owner
            self.owner = sendee
            Tools_Store[org_owner].remove(self)
            if sendee in Tools_Store:
                Tools_Store[sendee].append(self)
            else:
                Tools_Store[sendee] = [self]
            await qb.update('UPDATE items SET `owner`=%s WHERE `ID`=%s;', (sendee, self.id))
            logger.info(f'用户 {self.owner} 销毁了物品 {self.name}，编号 {self.id}')


class WearTool(BaseTool):
    """
    磨损型工具类，有耐久度的道具
    
    使用的时候会消耗耐久，可以使用修理增加耐久，但不会超过耐久最大值
    物品耐久耗尽将会变为损坏状态，不可使用
    无法修理已经损坏的工具，需要使用特殊方式来复原物品

    Attrs:
        durability (int): 耐久度
        max_drb (int): 最大耐久
    """
    cls_type = 'wear-tool'
    _charcteristic = BaseTool._charcteristic + ('durability', 'max_drb')

    def __init__(self, owner: int, name: str, durability: int) -> None:
        super().__init__(owner, name)
        self.durability = durability
        self.max_drb = durability

    async def use(self, wat :int=1):
        """
        使用物品，如果耐久度掉到0会使物品损坏，无法使用
        
        Args:
            wat (int): wear and tear，磨损度. Default is 1.

        Return:
            bool: 物品是否由于耐久耗尽而损坏
        """
        self.durability -= wat
        if self.durability <= 0:
            self.durability = 0
            broken = True
        else:
            broken = False
        await self._update_status()
        logger.debug(f'物品 {self.name} 被使用，耐久度降低{wat}')
        return broken

    async def maintain(self, degree: int):
        """修理物品，增加耐久度，但不会超过最大耐久上限"""
        self.durability = min(self.durability + degree, self.max_drb)
        await self._update_status()
        logger.debug(f'物品 {self.name} 被修理，耐久度变为{self.durability}')

    async def repair(self, degree: int=1):
        """复原物品，但耐久度可能不是满的"""
        self.durability += degree
        await self._update_status()
        logger.debug(f'物品 {self.name} 已复原，可以使用')


class NonWearTool(BaseTool):
    """
    非磨损型工具

    可以使用但无需调用使用方法，因为使用对工具本身没有影响
    """
    cls_type = 'non-wear-tool'

    def __init__(self, owner: int, name: str) -> None:
        super().__init__(owner, name)


class CollectionItem(BaseItem):
    """
    收藏品类

    此类及子类的实例化不作为个体存储，而是以数量计件，消耗时也是以数量方式直接消耗
    """
    cls_type = 'collection'

    def __init__(self, owner: int, name: str) -> None:
        super().__init__(owner, name)
        if self.ever_got():
            self.num = Collections_Store[owner][name]
        else:
            self.num = 0

    def ever_got(self):
        """是否之前已经获得过此收藏品"""
        global Collections_Store
        return self.owner in Collections_Store and self.name in Collections_Store[self.owner]

    async def new_coll(self):
        """首次获得收藏品，在got方法中自动调用"""
        async with QbotDB() as qb:
            await qb.insert('INSERT INTO collections (`type`, `owner`, `name`, `num`) VALUES (%s, %s, %s, %s)',
                            (self.type, self.owner, self.name, self.num))
            logger.debug(f'用户 {self.owner} 首次获得收藏品 {self.name}')

    async def got(self, num: int=1):
        """获得num个收藏品，如果是首次获得会调用new_coll方法自动插入一条记录"""
        self.num += num
        global Collections_Store
        if self.ever_got():
            Collections_Store[self.owner][self.name] += num
            async with QbotDB() as qb:
                await qb.update('UPDATE collections SET num=num+%s WHERE `owner`=%s and `name`=%s;',
                                (num, self.owner, self.name))
        else:
            if self.owner not in Collections_Store:
                Collections_Store[self.owner] = {}
            Collections_Store[self.owner][self.name] = num
            await self.new_coll()
        logger.debug(f'用户 {self.owner} 获得收藏品 {self.name} {self.num} 个')

    async def use(self, num: int=1):
        """使用num个收藏品"""
        self.num -= num
        Collections_Store[self.owner][self.name] -= num
        async with QbotDB() as qb:
            await qb.update('UPDATE collections SET num=num-%s WHERE `owner`=%s and `name`=%s;',
                                (num, self.owner, self.name))
        logger.debug(f'用户 {self.owner} 使用了 {self.num} 个收藏品 {self.name}')


#───────────────实际物体应基于以下子类创建───────────────#


class Hydrobios(CollectionItem):
    """
    水生生物类
    """
    cls_type = 'hydrobios'


class Fish(Hydrobios):
    """
    鱼类

    可能具有养殖方法
    """
    cls_type = 'fish'


class SpellCard(CollectionItem):
    """
    符卡类

    可能具有合成方法、附魔方法
    """
    cls_type = 'spell-card'


class FishingRod(WearTool):
    """
    鱼竿类
    
    Attributes:
        length (int): 鱼竿长度，影响最长能抛多远，长杆抛太近会降低上鱼概率
        hardness (int): 硬度，代替调性，决定最长的起竿时间，越硬越适合钓小鱼，应快速起竿，钓到大鱼起竿时间不对越容易断竿
        durability (int): 耐久度
        max_drb (int): 最大耐久
    """
    cls_type = 'fishing-rod'
    _charcteristic = WearTool._charcteristic + ('length', 'hardness')

    def __init__(self, owner: int, name: str, durability: int,
                length: int,
                hardness: int) -> None:
        """创建一个新鱼竿

        Args:
            owner (int): 鱼竿所属者id
            name (str): 鱼竿名字
            durability (int): 耐久度
            length (int): 鱼竿长度，影响最长能抛多远，长杆抛太近会降低上鱼概率
            hardness (int): 硬度，代替调性，决定最长的起竿时间，越硬越适合钓小鱼，应快速起竿，钓到大鱼起竿时间不对越容易断竿
        """
        super().__init__(owner, name, durability)
        self.length, self.hardness = length, hardness


class MiningTool(WearTool):
    """
    采矿工具类

    Attributes:
        strength (int): 强度，实际上决定掘进速度，强度越高一次能开采的层数越多
        durability (int): 耐久度
        max_drb (int): 最大耐久
    """
    cls_type = 'mining-tool'
    _charcteristic = WearTool._charcteristic + ('strength',)

    def __init__(self, owner: int, name: str, durability: int,
                strength: int) -> None:
        """创建一个新采矿工具

        Args:
            owner (int): 所属者id
            name (str): 工具名字
            durability (int): 耐久度
            strength (int): 强度，实际上决定掘进速度，强度越高一次能开采的层数越多
        """
        super().__init__(owner, name, durability)
        self.strength = strength


cls_map = {}  # cls_type与Class的映射，读取属性的时候用
for cls in (Hydrobios, Fish, SpellCard, FishingRod, MiningTool):
    cls_map[cls.cls_type] = cls


async def refresh_items_list():
    """读取数据库中道具记录，系统初始化时调用"""
    async with QbotDB() as qb:
        # 读取工具类
        global Tools_Store
        result = await qb.queryall('SELECT * FROM tools;')
        for r in result:
            if r.owner not in Tools_Store:
                Tools_Store[r.owner] = []
            item = Tools_Store[r.owner] = cls_map[r.type](r.owner, r.name)
            item.id = r.ID
            item.status = r.status
            item._attrs_from_status()
        logger.success(f'读取到{len(result)}条工具物品记录')

        # 读取收藏类
        global Collections_Store
        result = await qb.queryall('SELECT `type`, `owner`, `name`, `num` FROM collections;')
        for r in result:
            if r.owner not in Collections_Store:
                Collections_Store[r.owner] = {}
            Collections_Store[r.owner][r.name] = r.num
        logger.success(f'读取到{len(result)}条收藏类物品记录')


#───────────────物品中英文映射───────────────#


mapping_file = Path(__file__).parent/'uz_mapping.yml'

def load_uz_mapping():
    global uz_mapping
    with mapping_file.open(encoding='utf-8') as f:
        uz_mapping = yaml.load(f, Loader=yaml.SafeLoader)

load_uz_mapping()