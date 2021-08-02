from pathlib import Path
import yaml
import cv2
from PIL import Image, ImageDraw, ImageFont
try:
    from src.common.log import logger
except ImportError:
    from loguru import logger
from src.common import RESPATH


font_folder = Path(RESPATH)/'fonts'


goods_file = Path(__file__).parent/'goods.yml'
with goods_file.open(encoding='utf-8') as f:
    goods = yaml.load(f)


shop_ui = r"E:\Develop\QQbot\design\base\shop.jpg"
with Image.open(shop_ui) as im:
    shop_base = im.copy()


def shop_interface(*items):
    index_fnt = ImageFont.truetype(r"E:\Develop\QQbot\resource\fonts\MSYH.TTC", 24)
    txt_fnt = ImageFont.truetype(r"E:\Develop\QQbot\resource\fonts\MSYH.TTC", 12)
    display = shop_base.copy()
    draw = ImageDraw.Draw(display)
    
    draw.text((92, 159), '01', font=index_fnt, anchor='mm', fill=(28, 123, 177))
    draw.text((239, 196), '超人「大追踪！Buddhist Rider」\n（大追踪！僧侣骑士）', font=txt_fnt, anchor='mm', align='center', fill=(10, 10, 10))


    return display



if __name__ == "__main__":
    shop_interface().show()