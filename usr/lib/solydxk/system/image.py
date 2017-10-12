#! /usr/bin/env python3

from gi.repository import GdkPixbuf


class ImageHandler(object):

    def __init__(self, imagePath):
        self.imagePath = imagePath
        self.pixbuf = GdkPixbuf.Pixbuf.new_from_file(self.imagePath)
        self.width = self.pixbuf.get_width()
        self.height = self.pixbuf.get_height()

    def makeCenterSquare(self):
        if self.width > self.height:
            nw = self.height
            nh = self.height
            x = (self.width - nw) / 2
            y = 0
        else:
            nh = self.width
            nw = self.width
            y = (self.height - nh) / 2
            x = 0
        self.cropImage(x, y, nw, nh)

    def cropImage(self, x, y, width, height):
        self.pixbuf = self.pixbuf.new_subpixbuf(x, y, width, height)

    def resizeImage(self, width=None, height=None):
        if height is None and width is not None:
            height = self.height / (self.width / width)
        if width is None and height is not None:
            width = self.width / (self.height / height)
        if width is not None and height is not None:
            self.pixbuf = self.pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)

    def saveImage(self, savePath, imageFormat='png'):
        self.pixbuf.savev(savePath, imageFormat, [], [])

    def makeFaceImage(self, path):
        self.makeCenterSquare()
        self.resizeImage(64, 64)
        self.saveImage(path)
