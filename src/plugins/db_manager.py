from nonebot import get_driver
from src.common.dbpool import QbotDB
from src.common.levelsystem import UserLevel
from src.common.itemsystem import refresh_characters_ls, refresh_items_list


driver = get_driver()


@driver.on_shutdown
async def close_pool():
    await QbotDB.close_pool()


@driver.on_startup
async def read_users_data():
    await UserLevel.load_users_data()


@driver.on_startup
async def load_items_data():
    await refresh_characters_ls()
    await refresh_items_list()