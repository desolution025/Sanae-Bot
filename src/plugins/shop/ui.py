from datetime import datetime
from pathlib import Path
from typing import Dict

import numpy as np
import cv2
import imageio
from PIL import Image, ImageDraw, ImageFont

from src.common.log import logger
from src.common.levelsystem import UserLevel
from src.common.itemsystem import cls_map, uz_mapping, WearTool
from src.common.itemsystem.ui import *
from src.utils import draw_emoji_text, draw_text_shadow, text_box, image2b64


respath = Path(RESPATH)
font_folder = respath/'fonts'
shop_ui_folder = respath/'ui'/'shop'


# 用户信息头
header_user_base = Image.fromarray(imageio.imread(shop_ui_folder/'shop_header_user.png'))

# 日期头，日期信息不在此ui上覆盖，在下面附加
header_date = Image.fromarray(imageio.imread(shop_ui_folder/'shop_header_date.png'))

# 单列底部命令文字
shelf_buttom = Image.fromarray(imageio.imread(shop_ui_folder/'shop_bottom.png'))

# 双列顶部命令文字
shelf_top_command = Image.fromarray(imageio.imread(shop_ui_folder/'shop_command_text.png'))

# 工具类信息底板
shelf_tool_base = Image.fromarray(imageio.imread(shop_ui_folder/'shelf_tool.png'))

# 符卡类信息底板
shelf_sc_base = Image.fromarray(imageio.imread(shop_ui_folder/'shelf_sc.png'))

# 其它收藏品底板
shelf_other_base = Image.fromarray(imageio.imread(shop_ui_folder/'shelf_other.png'))


name_fnt = ImageFont.truetype(str(font_folder/'腾祥沁圆简w5.ttf'), 20)  # 用户名称、商品名称字体
level_fnt = ImageFont.truetype(str(font_folder/'MSYHBD.TTC'), 24)  # 用户等级字体
fund_fnt = ImageFont.truetype(str(font_folder/'GenJyuuGothic-Bold.ttf'), 17)  # 用户资金字体
date_fnt = ImageFont.truetype(str(font_folder/'GenJyuuGothic-Heavy.ttf'), 20)  # 日期字体
index_fnt = ImageFont.truetype(str(font_folder/'UDDigiKyokashoN-B.ttc'), 24)  # 商品索引字体
flag_fnt = ImageFont.truetype(str(font_folder/'腾祥沁圆简-w4.ttf'), 21)  # 商品标签字体，商品类型、商品售价的标签
type_fnt = ImageFont.truetype(str(font_folder/'腾祥沁圆简-w3.ttf'), 20)  # 商品类型字体
ppt_flag_fnt = ImageFont.truetype(str(font_folder/'腾祥沁圆简-w4.ttf'), 15)  # 商品属性标签字体，属性、附魔、说明的标签
price_fnt = ImageFont.truetype(str(font_folder/'Helvetica-Neue-2.ttf'), 21)  # 商品售价数字字体
property_fnt = ImageFont.truetype(str(font_folder/'腾祥沁圆简-w3.ttf'), 16)  # 商品属性字体，属性、附魔
value_fnt = ImageFont.truetype(str(font_folder/'Helvetica-Neue-2.ttf'), 16)  # 商品属性值字体
description_fnt = ImageFont.truetype(str(font_folder/'腾祥沁圆简-w3.ttf'), 13)  # 商品描述正文字体


def shop_interface(*items: Dict, user: UserLevel, name: str):
    """商店货架界面

    Args:
        *itmes (Dict): 所有商品
        user (UserLevel): 用户
        name (str): 用户昵称

    Returns:
        str: base64图片
    """
    # 根据商品数量确定页面大小
    count = len(items)
    if count < 8:
        resolution = (150 + count * 230, 640, 3)
        user_coord = (14, 16)
        date_coord = (435, 22)
        items_coord = [(28, 85 + i * 227) for i in range(len(items))]  # 单列
        command = shelf_buttom
        command_coord = (0, resolution[0] - 60)
    else:
        resolution = (100 + count // 2 * 230, 1200, 3)
        user_coord = (28, 16)
        date_coord = (992, 22)
        items_coord = [(308 - 294 * (-1) ** i, 85 + i // 2 * 227) for i in range(len(items))]  # 双列左右交替
        command = shelf_top_command
        command_coord = (618, 23)

    bg = np.zeros(resolution, dtype=np.uint8)  # 临时BG
    bg[:] = (150, 100, 90)
    bg = Image.fromarray(cv2.cvtColor(bg, cv2.COLOR_BGR2RGBA), mode='RGBA')

    # header-userinfo
    name_fnt_params = {
        'font': name_fnt,
        'fill': '#FFFFFF',
        'stroke_width': 1,
        'stroke_fill': '#111111'
    }
    header_user = header_user_base.copy()
    user_draw = ImageDraw.Draw(header_user)
    user_draw.text((33, 46), text=str(user.level), fill='#1E3643', font=level_fnt, anchor='ms', align='center')
    fund_text_params = {
        'xy': (120, 56),
        'text': str(user.fund),
        'font': fund_fnt,
        'fill': '#FFFFFF',
        'anchor': 'ms',
        'stroke_width': 1,
        'stroke_fill': '#111111'
    }
    draw_text_shadow(header_user, opacity=0.3, **fund_text_params)
    user_draw.text(**fund_text_params)
    
    # header-date
    now = datetime.now()
    meridiem = 'AM' if now.hour < 12 else 'PM'
    timestr = now.strftime('%Y-%m-%d ') + meridiem
    logger.debug(f'current store time: {timestr}')

    # commodities
    item_cards = [commodity_card(index, item) for index, item in enumerate(items)]

    # main composition
    bg.alpha_composite(header_user, user_coord)
    bg.alpha_composite(header_date, date_coord)
    bgdraw = ImageDraw.Draw(bg)
    date_text_params = {
        'xy': (date_coord[0] + 101, date_coord[1] + 58),
        'text': timestr,
        'font': date_fnt,
        'fill': '#3C415C',
        'anchor': 'ms',
        'align': 'center',
        'stroke_width': 1,
        'stroke_fill': '#FFFFFF'
    }
    draw_emoji_text(bg, name, emoji_size=22, positon=(user_coord[0] + 72, user_coord[1] + 23),
                    text_shadow=True, opacity=0.3, gen_new_img=False, **name_fnt_params)
    draw_text_shadow(bg, distance=4, **date_text_params)
    bgdraw.text(**date_text_params)
    
    for card, coord in zip(item_cards, items_coord):  # 商品卡片
        bg.alpha_composite(card, coord)

    bg.alpha_composite(command, command_coord)  # 命令文本

    return image2b64(bg)


def commodity_card(index: int, commodity: Dict):
    """生成商品卡片信息

    Args:
        index (int): 商品在当前货架的编号
        commodity (Dict): 商品属性列表

    Returns:
        Image.Image: 商品卡片图片
    """
    item_type = cls_map[commodity['type']]
    if issubclass(item_type, WearTool):
        card = shelf_tool_base.copy()
        draw = ImageDraw.Draw(card)
        # index
        draw.text(xy=(69, 52), text=str(index + 1).zfill(2), fill='#FFFFFF', font=index_fnt, anchor='ms', align='center', stroke_width=1, stroke_fill='#111111')
        # name
        draw.text(xy=(294, 49), text=commodity['name'], fill='#EFEFEF', font=name_fnt, anchor='ms', align='center', stroke_width=1, stroke_fill='#111111')
        # type
        draw.text(xy=(137, 90), text=uz_mapping['type'][commodity['type']], fill='#2E4351', font=type_fnt, anchor='ms', align='center')
        # price
        draw.text(xy=(282, 92), text=str(commodity['price']), fill='#2A3335', font=price_fnt, anchor='ms', align='center')
        # rest
        draw.text(xy=(427, 92), text=str(commodity['num']), fill='#2A3335', font=price_fnt, anchor='ms', align='center')
        # properties
        item_type : WearTool = cls_map[commodity['type']]
        ppt_ls = list(item_type._charcteristic) # 属性英文名列表
        ppt_ls.remove('max_drb')  # 去掉最大耐久度属性
        del ppt_ls[0]
        ppt_ls.append('durability')  # 把耐久度放到最后
        ppt_zh_ls = [uz_mapping['property'][p] for p in ppt_ls]  # 属性中文名列表
        ppt_name = '\n'.join(ppt_zh_ls)
        draw.multiline_text(xy=(44, 165), text=ppt_name, fill='#1F1F1F', font=property_fnt, anchor='lm', align='left')
        values = '\n'.join([str(commodity[p]) for p in ppt_ls])
        draw.multiline_text(xy=(120, 165), text=values, fill='#1F1F1F', font=value_fnt, anchor='rm', align='right', spacing=5)
        # status
        status = commodity['status']
        if status is None:
            draw.text(xy=(216, 168), text='无', fill='#1F1F1F', font=property_fnt, anchor='ms', align='center')
        else:
            status_name = '\n'.join([uz_mapping['status'][p] for p in status])
            draw.multiline_text(xy=(157, 166), text=status_name, fill='#1F1F1F', font=property_fnt, anchor='lm', align='left')
            values = '\n'.join([str(status[k]) for k in status])
            draw.multiline_text(xy=(270, 166), text=values, fill='#2E3941', font=value_fnt, anchor='rm', align='right')
        # description
        description = commodity['description'] or ''
        draw.multiline_text((306, 136), text=text_box(description, 233, description_fnt), fill='#1A1A1A', font=description_fnt, spacing=5)
        # icon
        icon_coord = (476, 27)
        if commodity['type'] == 'fishing-rod':
            card.alpha_composite(Image.alpha_composite(icon_frame_n, icon_fishing_rod), icon_coord)
        else:
            card.alpha_composite(Image.alpha_composite(icon_frame_n, icon_missing), icon_coord)

    else:
        card = shelf_other_base.copy()
    if commodity['num'] == 0:
        """TODO: 把卡片转成灰度图"""
    return card