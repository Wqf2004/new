from PIL import Image
import re

from PIL import Image


def image_to_oled_array(
    image_path,
    width=128,
    height=64,
    threshold=128,
    force_symmetric=True,
    flip_x=False,
    flip_y=False,
):
    """
    将图片转换为 OLED 点阵 C 数组

    :param image_path: 图片路径
    :param width: 输出宽度，默认 128
    :param height: 输出高度，默认 64
    :param threshold: 二值化阈值，0~255，默认 128
    :param force_symmetric: 是否强制左右对称（取左半边镜像到右半边），默认 True
    :param flip_x: 是否左右翻转，默认 False
    :param flip_y: 是否上下翻转，默认 False
    :return: C 数组字符串
    """
    # 1. 打开图片并转为灰度图
    img = Image.open(image_path).convert("L")

    # 2. 调整尺寸到 128x64（如果原始比例不同，会拉伸）
    img = img.resize((width, height), Image.Resampling.LANCZOS)

    # 3. 可选：强制左右对称（取左半边，镜像到右半边）
    if force_symmetric:
        left_half = img.crop((0, 0, width // 2, height))
        right_half = left_half.transpose(Image.FLIP_LEFT_RIGHT)
        img.paste(left_half, (0, 0))
        img.paste(right_half, (width // 2, 0))

    # 4. 可选：整体翻转
    if flip_x:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if flip_y:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)

    # 5. 二值化处理（大于阈值为亮/白，否则为暗/黑）
    img = img.point(lambda p: 255 if p > threshold else 0)

    # 6. 转换为 OLED 字节数组
    pixels = img.load()
    oled_data = []

    # 128x64 分为 8 页，每页 8 行
    for page in range(height // 8):
        for x in range(width):
            byte_val = 0
            for bit in range(8):
                y = page * 8 + bit
                # 如果像素是白色（亮），则对应 bit 置 1
                if pixels[x, y] > 0:
                    byte_val |= 1 << bit  # bit0 对应最上面一行，bit7 对应最下面一行
            oled_data.append(byte_val)

    # 7. 格式化为 C 数组字符串
    c_array = "const unsigned char BMP_Forward[] = {\n"
    for i in range(0, len(oled_data), 16):
        line_data = oled_data[i : i + 16]
        c_array += "    " + ", ".join(f"0x{val:02X}" for val in line_data) + ",\n"
    c_array += "};\n"

    return c_array

def c_array_to_bmp(c_code, output_path='reversed.bmp',
                   width=128, height=64,
                   bit0_top=True,   # True: bit0在上, bit7在下；False: 反过来
                   flip_x=False,    # 左右镜像
                   flip_y=False):   # 上下镜像
    # 1. 提取所有 0xXX 数据
    hex_values = re.findall(r'0x([0-9A-Fa-f]{2})', c_code)
    data = [int(v, 16) for v in hex_values]
    print(f"提取到 {len(data)} 字节，需要 {width * height // 8} 字节")

    if len(data) < width * height // 8:
        print("警告：数据不足，可能不是完整的 128x64 图片")

    # 2. 创建灰度图像，0=黑，255=白
    img = Image.new('L', (width, height), 0)
    pixels = img.load()

    pages = height // 8  # 8 页

    # 3. 按页、列还原像素
    for page in range(pages):
        for x in range(width):
            idx = page * width + x
            if idx >= len(data):
                break
            byte = data[idx]
            for bit in range(8):
                if bit0_top:
                    y = page * 8 + bit          # bit0 在最上面
                else:
                    y = page * 8 + (7 - bit)    # bit7 在最上面
                if byte & (1 << bit):
                    pixels[x, y] = 255  # 白
                else:
                    pixels[x, y] = 0    # 黑

    # 4. 可选翻转
    if flip_x:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if flip_y:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)

    # 5. 保存为 BMP
    img.save(output_path)
    print(f"已保存为 {output_path}")

if __name__ == "__main__":

    # code1 = image_to_oled_array("打招呼.png", force_symmetric=False)
    # print(code1)

    # 把包含 C 数组的文本保存为 array.txt，和本脚本放一起
    with open('array.txt', 'r', encoding='utf-8') as f:
        c_code = f.read()

    # 默认按 SSD1306 常见方式：bit0 在上，不翻转
    c_array_to_bmp(c_code, 'reversed.bmp', bit0_top=True)
