from pathlib import Path
import yaml
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
try:
    from src.common.log import logger
    from src.common import RESPATH
except ImportError:
    from loguru import logger
    RESPATH = r"E:\Develop\QQbot\resource\ui"


font_folder = Path(RESPATH)/'fonts'
shop_ui_folder = Path(RESPATH)/'shop'

# 用户信息头
header_user_reader = cv2.imread(str(shop_ui_folder/'shop_header_user.png'))
header_user_base = Image.fromarray(cv2.cvtColor(header_user_reader, cv2.COLOR_BGRA2RGBA))
del header_user_reader

# 日期头，日期信息不在此ui上覆盖，在下面附加
header_date_reader = cv2.imread(str(shop_ui_folder/'shop_header_date.png'))
header_date = Image.fromarray(cv2.cvtColor(header_date_reader, cv2.COLOR_BGRA2RGBA))
del header_date_reader

# 工具类信息底板
shelf_tool_reader = cv2.imread(str(shop_ui_folder/'shelf_tool.png'))
shelf_tool_base = Image.fromarray(cv2.cvtColor(shelf_tool_reader, cv2.COLOR_BGRA2RGBA))
del shelf_tool_reader

# 符卡类信息底板
shelf_sc_reader = cv2.imread(str(shop_ui_folder/'shelf_sc.png'))
shelf_sc_base = Image.fromarray(cv2.cvtColor(shelf_sc_reader, cv2.COLOR_BGRA2RGBA))
del shelf_sc_reader

# 其它收藏品底板
shelf_other_reader = cv2.imread(str(shop_ui_folder/'shelf_other.png'))
shelf_other_base = Image.fromarray(cv2.cvtColor(shelf_other_reader, cv2.COLOR_BGRA2RGBA))
del shelf_other_reader


goods_file = Path(__file__).parent/'goods.yml'
with goods_file.open(encoding='utf-8') as f:
    goods = yaml.load(f)


def shop_interface(*items):
    index_fnt = ImageFont.truetype(r"E:\Develop\QQbot\resource\fonts\MSYH.TTC", 24)
    txt_fnt = ImageFont.truetype(r"E:\Develop\QQbot\resource\fonts\MSYH.TTC", 12)
    # display = shop_base.copy()
    # draw = ImageDraw.Draw(display)
    
    # draw.text((92, 159), '01', font=index_fnt, anchor='mm', fill=(28, 123, 177))
    # draw.text((239, 196), '超人「大追踪！Buddhist Rider」\n（大追踪！僧侣骑士）', font=txt_fnt, anchor='mm', align='center', fill=(10, 10, 10))


    # return display



if __name__ == "__main__":
    shop_interface().show()