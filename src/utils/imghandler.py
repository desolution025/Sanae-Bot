from pathlib import Path
from random import randint
from typing import Optional, Union, Tuple, Literal, Dict, List
from io import BytesIO
from base64 import b64encode, b64decode
from functools import partial
import ujson as json

import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from emoji import emoji_lis
from imghdr import what


__all__ = ('AntiShielding', 'draw_emoji_text')


# TODO: 换成cv2处理
class AntiShielding:
    """把图像内容进行反和谐处理，并且支持存为base64编码或直接存入磁盘

    """

    def __init__(self, content: Union[str, Path, BytesIO, bytes], max_len: int=2048) -> None:
        """
        Args:
            content (Union[str, Path, BytesIO, bytes]): 图像内容
            max_len (int, optional): 反和谐后的图像长与宽不会大于该值. Defaults to 2048.
        """
        if isinstance(content, bytes):
            content = BytesIO(content)
        with Image.open(content) as self.img:
            self.img.thumbnail((max_len, max_len))
            self.changPixel()

    @staticmethod
    def randomcolor(dimension: int=3, *, alpha: int=0):
        """Random generate a color value

        Args:
            dimension (int): 3 o r4 corresponds to rgb and rgba. Defaults to 3.
            alpha (int, optional): Alpha value only use when dimension is 4. Defaults to 0.

        Returns:
            tuple: Color value
        """
        assert dimension in (3, 4), 'Only support rgb or rgba mode'
        pixel = (randint(0, 255), randint(0, 255), randint(0, 255))
        if dimension == 4:
            pixel += (alpha,)
        if alpha < 0 or alpha > 255:
            raise ValueError('Alpha value must between in 0~255')
        return pixel

    def changPixel(self):
        """
        Antishielding, over four pixels
        """
        width = self.img.width - 1
        height = self.img.height - 1
        px = self.img.load()
        if self.img.mode == 'RGBA':
            self.randomcolor = partial(self.randomcolor, dimension=4)
        for w in [0, width]:
            for h in [0, height]:
                px[w, h] = self.randomcolor()

    def save2file(self, filepath: Union[str, Path]):
        """将反和谐后的图像存为磁盘文件

            存储时后缀可以随意设置，但会自动修正为真实的后缀，所以返回的文件名称并不一定就等于输入的名称

        Args:
            filepath (Union[str, Path]): 要存储的文件路径

        Returns:
            Path: 和谐后的存储的文件路径
        """
        if self.img.mode == 'RGBA':
            self.img.save(filepath, format='PNG')
        else:
            self.img.save(filepath, format='JPEG', quality=90)
        real_suffix = f".{what(filepath).replace('jpeg', 'jpg')}"
        if not isinstance(filepath, Path):
            filepath = Path(filepath)
        
        # 真实后缀不符合当前后缀时自动修复
        if real_suffix != filepath.suffix.lower():
            filepath.rename(filepath.with_suffix(real_suffix))
        return filepath

    def save2b64(self):
        """将反和谐后的图像存为Base64编码字符串

        Returns:
            str: Base64字符串，可以直接使用MessageSegment.image构建片段
        """
        buffer = BytesIO()
        if self.img.mode == 'RGBA':
            self.img.save(buffer, format='png')
        else:
            self.img.save(buffer, format='jpeg', quality=90)
        return 'base64://' + b64encode(buffer.getvalue()).decode('utf-8')


EMOJI_TYPE = 'apple'  # 采用哪种设备的emoji风格
emoji_list_file = Path(__file__).parent/'emoji_list.json'
# device: Literal['apple', 'google', 'facebook', 'wind', 'twitter', 'joy', 'sams', 'gmail', 'SB', 'DCM', 'KDDI']


emoji_dict = {}

def load_emoji_b64(device: Literal['apple', 'google', 'facebook', 'wind', 'twitter', 'joy', 'sams', 'gmail', 'SB', 'DCM', 'KDDI']='apple'):
    """设置当前emoji显示设备风格"""
    with emoji_list_file.open(encoding='utf-8') as j:
        global emoji_dict
        tmp_emjdict = json.load(j)
        for e in tmp_emjdict:
            if EMOJI_TYPE in tmp_emjdict[e]:
                emoji_dict[e] = tmp_emjdict[e][EMOJI_TYPE]
            else:
                emoji_dict[e] = None

load_emoji_b64()


def load_emoji(emoji: str, size: Optional[int]=None) -> np.ndarray:
    """读取emoji位图

    Args:
        emoji (str): 单个emoji字符
        size (Optional[int], optional): 缩放至此大小. Defaults to None.

    Returns:
        np.ndarray: ndarray图像
    """
    if emoji not in emoji_dict or emoji_dict[emoji] is None:  # 如果查找不到当前emoji可以使用的图像的话返回一个被设置大小的透明底
        size = size or 30
        return np.zeros((size, size, 4), dtype=np.uint8)

    nparray = np.frombuffer(b64decode(emoji_dict[emoji]), np.uint8)
    emoji_img = cv2.imdecode(nparray, cv2.IMREAD_UNCHANGED)
    if size:
        return cv2.resize(emoji_img, (size, size))
    else:
        return emoji_img


def split_emoji_text(text: str) -> List[Dict]:
    """分离字符串里的emoji用作图片中的emoji合成"""

    locations = [e['location'] for e in emoji_lis(text)]  # 所有emoji的索引

    if not locations:
        return [{'emoji': False, 'text': text}]

    structure = [{'emoji': False, 'text': text[:locations[0]]}] if locations[0] > 0 else []  # 判断字符串是否从emoji开始
    for i, loc in enumerate(locations[: -1]):  # 在中间按顺序穿插正常文字和emoji
        structure.append({'emoji': True, 'text': text[loc]})
        if locations[i + 1] > loc + 1:
            structure.append({'emoji': False, 'text': text[loc + 1: locations[i + 1]]})
    if locations[-1] < len(text) - 1:  # 判断字符串是否结束于emoji
        structure.append({'emoji': False, 'text': text[locations[-1] + 1:]})
    return structure


def draw_emoji_text(img: Image.Image, text: str, emoji_size: int, positon: Tuple[int, int], align: Literal['left', 'middle', 'right']='left',
                    text_shadow: bool=False, shadow_color: Tuple[int, int, int]=(0,0,0), distance: int=1, opacity: Union[int, float]=127,
                    gen_new_img: bool=True,
                    **kw):
    """给图片添加可以夹杂emoji的文字

    Args:
        img (Image.Image): 源图片
        text (str): 文字
        emoji_size (int): emoji大小，通常可以设置为于普通字体大小相等，如果有特殊字体差异过大根据情况调整此项
        positon (Tuple[float, float]): 文字位置，为了emoji与文字垂直平齐，使用此函数添加文字时锚点y轴固定成middle了
        align (Literal[, optional): 左右对齐方式，可以设置为right、middle，传入其它其它方式都会被默认使用left. Defaults to 'left'.
        text_shadow (bool): 开启文字阴影.  Defaults to False.
        shadow_color (Tuple[int, int, int], optional): 阴影颜色. Defaults to (0,0,0).
        distance (int, optional): 阴影长度，由于PIL限制最终xy长度分量只能是int. Defaults to 1.
        opacity (Union[int, float], optional): 不透明度，可以是0-1之间的float或直接输入8位深黑白值. Defaults to 127.
        gen_new_img (bool): 是否生成新Image，如果为False，则会在传入的Image上进行绘制. Defaults to True.
        **kw: 传递给ImageDraw.text的参数
    """
    structure = split_emoji_text(text)
    draw_layer = Image.new(mode='RGBA', size=img.size, color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(draw_layer)
    if text_shadow:
        shadow = draw_layer.copy()
        shadow_draw = ImageDraw.Draw(shadow)
    total_length = 0

    # 计算字符长度，设置初始位置偏移
    for s in structure:
        if s['emoji']:
            total_length += emoji_size
        else:
            length = draw.textlength(s['text'], kw['font'])
            total_length += length
            s['length'] = length

    if align == 'right':
        offset = total_length
    elif align == 'middle':
        offset = total_length * 0.5
    else:
        offset = 0
    pos = (round(positon[0] - offset), positon[1])

    for s in structure:
        if s['emoji']:
            emoji_array = load_emoji(s['text'], size=emoji_size)
            emoji_pic = Image.fromarray(cv2.cvtColor(emoji_array, cv2.COLOR_BGRA2RGBA), mode='RGBA')
            fix_pos = (pos[0], round(pos[1] - emoji_size * 0.5))
            # img.paste(emoji_pic, fix_pos)
            draw_layer.alpha_composite(emoji_pic, fix_pos)
            if text_shadow:
                emoji_array[:, :, 0] = emoji_array[:, :, 1] = emoji_array[:, :, 2] = 255  # preserve alpha

                shadow_opacity = opacity if isinstance(opacity, float) else opacity / 255
                shadow_rgba = np.array((shadow_color[2] / 255, shadow_color[1] / 255, shadow_color[0] / 255, shadow_opacity))

                emoji_shadow = emoji_array * shadow_rgba  # multiply composition
                emoji_shadow = emoji_shadow.astype(np.uint8)  # convert type to uint8
                shadow_pil = Image.fromarray(cv2.cvtColor(emoji_shadow, cv2.COLOR_BGRA2RGBA), 'RGBA')

                offset = round(distance * 2 ** 0.5 * 0.5)
                shadow_pos = (fix_pos[0] + offset, fix_pos[1] + offset)
                shadow.alpha_composite(shadow_pil, shadow_pos)
            pos = (round(pos[0] + emoji_size), positon[1])
        else:
            # length = draw.textlength(s['text'], kw['font'])
            draw.text(pos, s['text'], anchor='lm', **kw)
            if text_shadow:
                draw_text_shadow(shadow_color=shadow_color, distance=distance, opacity=opacity, shadow_draw=shadow_draw, xy=pos, text=s['text'], anchor='lm', **kw)
            pos = (round(pos[0] + s['length']), positon[1])
    
    if gen_new_img:
        if text_shadow:
            return Image.alpha_composite(Image.alpha_composite(img, shadow), draw_layer)
        else:
            return Image.alpha_composite(img, draw_layer)
    else:
        if text_shadow:
            img.alpha_composite(shadow)
        img.alpha_composite(draw_layer)


def draw_text_shadow(img: Optional[Image.Image]=None,
                    shadow_color: Tuple[int, int, int]=(0,0,0),
                    distance: int=1, opacity: Union[int, float]=127,
                    only_shadow: bool=False,
                    shadow_draw=None,
                    **kw):
    """给文字添加阴影

    不会直接把文字绘制在其上，可以把ImageDraw.text的参数打包好分别传入此函数和主绘制函数
    Args:
        img (Optional[Image.Image]): 源图片，如果传入了shadow_draw则此参数无效.Defaults to None.
        shadow_color (Tuple[int, int, int], optional): 阴影颜色. Defaults to (0,0,0).
        distance (int, optional): 阴影长度，由于PIL限制最终xy长度分量只能是int. Defaults to 1.
        opacity (Union[int, float], optional): 不透明度，可以是0-1之间的float或直接输入8位深黑白值. Defaults to 127.
        only_shadow (bool): 是否只输出阴影，只有没传入shadow_draw的情况下才有用. Defaults to False.
        shadow_draw: (Optional[ImageDraw]): 使用自定的阴影图层进行绘制. Defaults to None.
        **kw: 所有传递给ImageDraw.text的参数，stroke_fill等颜色参数会自动覆盖

    Raises:
        TypeError: opacity不符合要求时会抛出非数字参数的异常

    Returns:
        Union[Image.Image, None]: 如果没有自定义shadow_draw并且开启了only_shadow，会返回一个带alpha的阴影层
    """
    if shadow_draw is None:
        modify_src = True
        shadow = Image.new(mode='RGBA', size=img.size, color=(0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
    else:
        modify_src = False

    if isinstance(opacity, int):
        shadow_color = (shadow_color[0], shadow_color[1], shadow_color[2], opacity)
    elif isinstance(opacity, float):
        shadow_color = (shadow_color[0], shadow_color[1], shadow_color[2], round(opacity * 255))
    else:
        raise TypeError('opacity只能是数字参数')

    kw['fill'] = shadow_color
    xy = kw['xy'] if 'xy' in kw else (0, 0)
    offset = round(distance * 2 ** 0.5 * 0.5)
    kw['xy'] = (xy[0] + offset, xy[1] + offset)

    if 'stroke_fill' in kw:
        del kw['stroke_fill']
    shadow_draw.text(**kw)

    if modify_src:
        if only_shadow:
            return shadow
        img.alpha_composite(shadow)


def text_box(text: str, width: int, font: ImageFont.FreeTypeFont):
    """生成固定宽度的文字排版

    Args:
        text (str): 字符串
        width (int): 宽度
        font (ImageFont.FreeTypeFont): 字体

    Returns:
        str: 重排过的文字
    """
    accu = 0  # 字符积累长度
    pre_pt = 0  # 之前的断点
    seg = []  # 字符串被分割的片段

    for i, c in enumerate(text):
        l = font.getlength(c)  # 字符长度
        if text[i] == '\n':  # 遇到回车直接重新积累长度
            accu = 0
        elif accu + l > width:  # 超过设定宽度时添加片段
            seg.append(text[pre_pt: i])
            accu = l
            pre_pt = i
        else:
            accu += l

    return ('\n'.join(seg) + '\n' + text[pre_pt:]).lstrip('\n')  # 连接所有片段


if __name__ == "__main__":
    from datetime import datetime
    RESPATH = r"E:\Develop\QQbot\resource"
    font_folder = Path(RESPATH)/'fonts'
    fnt_path = font_folder/'经典粗圆简.TTF'

    img = np.zeros((200, 1000, 3), dtype=np.uint8)
    img[:] = (255, 255, 255)
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGBA))

    fnt = ImageFont.truetype(str(fnt_path), 35)

    start_time = datetime.now()
    new_pil= draw_emoji_text(img_pil, 'wdnmd🔷😄😝👌🥓wtd🥗🧀草🍣发动a✝🛐♏♒♊', emoji_size=35, positon=(10, 50), align='',
                    text_shadow=True, shadow_color=(0, 0, 50), distance=4, opacity=0.5,
                    fill=(255, 255, 255), font=fnt,
                    gen_new_img=True)

    print('cost time: ', datetime.now() - start_time)
    # img_pil.show()
    new_pil.show()