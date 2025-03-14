#!/usr/bin/env python

import re
from random import randrange
from re import search
import argparse
import os

from PIL import Image, ImageDraw, ImageFont
import requests


class xkcd_downloader:

    def __init__(self, download_dir):
        if not os.path.exists(download_dir+os.path.sep):
            print("Error:", "'"+download_dir+"', no such directory")
            raise SystemExit
        if not os.access(download_dir, os.W_OK):
            print("Error:", "'"+download_dir+"', permission denied")
            raise SystemExit
        self.download_dir = download_dir
        self.title_fontsize = 28
        self.alt_fontsize = 18
        self.line_offset = 10

    def download_json(self, comic_number) -> dict:
        if comic_number < 0:
            raise ValueError

        if comic_number == 0:
            return requests.get("http://xkcd.com/info.0.json", timeout=5).json()
        else:
            return requests.get(f"http://xkcd.com/{comic_number}/info.0.json", timeout=5).json()

    def text_wrap(self, font: ImageFont.FreeTypeFont, text: str, image_width, i=0):
        lines: list[list[str]] = []
        text_split = text.split(" ")
        while len(text_split) > 0:
            lines.append([])
            while len(text_split) > 0 \
                    and font.getlength(" ".join(lines[i])) < image_width:
                if font.getlength(text_split[0]+" "+" ".join(lines[i])) \
                        > image_width*0.95:
                    if len(lines[i]) == 0:
                        text_split[0] = text_split[0][:len(text_split[0])//2+1] \
                            + " " + text_split[0][:len(text_split[0])//2+1:]
                        text_split = text_split[0].split(" ") + text_split[1:]
                    break
                lines[i].append(text_split[0])
                text_split.pop(0)
            i += 1
        lines = [line for line in lines if len(line) != 0]
        return lines

    def add_text(self, image, title: str, alt: str, tfont='xkcd.ttf',
                 afont='xkcd.ttf', scaling=1):

        try:
            img = Image.open(image)
        except OSError:
            return

        tfont = ImageFont.truetype("xkcd.ttf", self.title_fontsize*scaling)
        afont = ImageFont.truetype("xkcd.ttf", self.alt_fontsize*scaling)
        line_padding = 5
        draw = ImageDraw.Draw(img)
        lines = self.text_wrap(tfont, title, img.size[0])
        lheight = max([tfont.getbbox(" ".join(i))[3] for i in lines])
        lheight_total = (lheight+line_padding)*(len(lines))+line_padding*4
        title_crop = (0, -1*lheight_total, img.size[0], img.size[1])
        img = img.crop(title_crop)
        w, h = img.size
        old_h = h
        draw = ImageDraw.Draw(img)
        lheight_total = line_padding
        for i in lines:
            draw.text((w/2-tfont.getlength(" ".join(i))/2,
                      lheight_total),
                      " ".join(i),
                      font=tfont,
                      fill=0xffffff)
            lheight_total += lheight + line_padding
        lheight_total = line_padding
        lines = self.text_wrap(afont, alt, w)
        lheight = max([afont.getbbox(" ".join(i))[3] for i in lines])
        lheight_total = lheight*len(lines)
        alt_crop = (0, 0, img.size[0],
                    img.size[1]+lheight_total+(len(lines)+3)*line_padding)
        img = img.crop(alt_crop)
        draw = ImageDraw.Draw(img)
        lheight_total = old_h + line_padding
        for i in lines:
            if not i:
                continue
            draw.text((w/2-afont.getlength(" ".join(i))/2,
                      lheight_total),
                      " ".join(i),
                      font=afont,
                      fill=0xffffff)
            lheight_total += lheight + line_padding

        img.save(image)

    def download_images(self, comic_number, download_only):
        if comic_number == 404:
            return
        if comic_number == 0:
            print("Fetching comic -> Latest")
        else:
            print(f"Fetching comic -> {comic_number}")
        try:
            info = self.download_json(comic_number)
        except requests.exceptions.ConnectionError:
            print("Error: URL could not be retrieved")
            return

        title, alt, num = info['safe_title'], info['alt'], str(info['num'])
        image = num + search(r"\.([a-z])+$", info['img']).group()
        with open(self.download_dir+'/'+image, 'wb') as image_file:
            url = info['img']
            url_2x = re.sub(r"(\.\w+)$", "_2x\\1", url)
            req = requests.get(url_2x, stream=True, timeout=5)
            scaling = 2
            if req.status_code != 200:
                # for old comics, only the 1x image is available
                req = requests.get(url, stream=True, timeout=5)
                scaling = 1
            for block in req.iter_content(1024):
                if block:
                    image_file.write(block)
                    image_file.flush()
            if not download_only and not search(r"\.gif", info['img']):
                print(f"Processing comic -> {comic_number}")
                self.add_text(self.download_dir+'/'+image, title, alt, scaling=scaling)

    def download_all(self, download_only):
        for i in range(1, self.download_json(0)['num']+1):
            self.download_images(i, download_only)

    def download_random(self, download_only, iterations=1):
        info = self.download_json(0)
        for _ in range(iterations):
            self.download_images(randrange(1, info['num']+1), download_only)


def main():

    parser = argparse.ArgumentParser(description='Retrieve and embed the\
                                     titles and alt text from XKCD comics\
                                     into single images.', prefix_chars='-+')
    parser.add_argument('N', type=int, nargs='*', help='an integer or set\
                        of integers greater than or equal to zero')
    parser.add_argument('-r', '--range', action="store", metavar='N',
                        type=int, nargs=2, help='fetch comics within\
                        a certain range')
    parser.add_argument('-o', '--output-dir', metavar='DIRECTORY',
                        action='store', default='./', help='change the\
                        output directory. default: current directory')
    parser.add_argument('-a', '--all', action='store_true',
                        help='fetch all comics')
    parser.add_argument('-d', '--download-only', action='store_true',
                        help='download images only')
    parser.add_argument('--random', metavar='ITERATIONS', type=int,
                        help='fetch random comics', nargs='?', const=1)
    args = parser.parse_args()

    x = xkcd_downloader(args.output_dir)
    if args.range:
        if args.N or args.random or args.all:
            raise argparse.ArgumentTypeError("Value may not be used in\
                                             addition to the --range flag")
        else:
            for i in range(args.range[0], args.range[1]+1):
                x.download_images(i, args.download_only)
            return
    if args.all:
        if args.N or args.random:
            raise argparse.ArgumentTypeError("Value may not be used in\
                                             addition to the --all flag")
        return x.download_all(args.download_only)

    if args.random:
        if args.N:
            raise argparse.ArgumentTypeError("'{args.N}': Value may not be used\
                                             in addition to the --random\
                                             flag")
        return x.download_random(args.download_only, args.random)
    else:
        if not args.N:
            parser.print_help()
        for i in args.N:
            x.download_images(i, args.download_only)
        return


if __name__ == '__main__':
    main()
