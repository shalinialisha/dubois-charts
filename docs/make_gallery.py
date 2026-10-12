"""
Make docs/gallery.png, the picture at the top of the README, from the
images examples/basic_usage.py draws:

    python examples/basic_usage.py
    python docs/make_gallery.py
"""

import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = os.path.join(os.path.dirname(HERE), 'examples')
CHARTS = ['bar_chart', 'stacked_area_chart', 'butterfly_chart', 'spiral_chart',
          'snake_chart', 'pie_chart', 'county_map_chart', 'state_map_chart']
CELL_W, CELL_H, GAP, COLUMNS = 420, 330, 12, 4
CREAM = (222, 215, 201)


def main():
    rows = -(-len(CHARTS) // COLUMNS)
    sheet = Image.new('RGB', (COLUMNS * CELL_W + (COLUMNS + 1) * GAP,
                              rows * CELL_H + (rows + 1) * GAP), CREAM)
    for k, name in enumerate(CHARTS):
        image = Image.open(os.path.join(EXAMPLES, f'example_{name}.png')).convert('RGB')
        image.thumbnail((CELL_W, CELL_H), Image.LANCZOS)
        row, column = divmod(k, COLUMNS)
        x = GAP + column * (CELL_W + GAP) + (CELL_W - image.width) // 2
        y = GAP + row * (CELL_H + GAP) + (CELL_H - image.height) // 2
        sheet.paste(image, (x, y))
    out = os.path.join(HERE, 'gallery.png')
    # A picture of textures compresses badly; 256 colours keeps it small
    # and is indistinguishable at this size.
    sheet.quantize(colors=256, method=Image.MEDIANCUT, dither=Image.FLOYDSTEINBERG).save(out, optimize=True)
    print('wrote', out, os.path.getsize(out) // 1024, 'KB')


if __name__ == '__main__':
    main()
