"""
FlatCAM camlib.FlatCAMRTree / FlatCAMRTreeStorage / autolist — verbatim logic
for paint_connect and clear_polygon2 (rtree index).
"""
from __future__ import annotations

from rtree import index as rtindex


def autolist(obj):
    try:
        __ = iter(obj)
        return obj
    except TypeError:
        return [obj]


class FlatCAMRTree(object):
    """
    Indexes geometry (any object with .coords).
    """

    def __init__(self):
        self.rti = rtindex.Index()
        self.obj2points = []
        self.points2obj = []
        self.get_points = lambda go: go.coords

    def grow_obj2points(self, idx):
        if len(self.obj2points) > idx:
            return
        for i in range(len(self.obj2points), idx + 1):
            self.obj2points.append([])

    def insert(self, objid, obj):
        self.grow_obj2points(objid)
        self.obj2points[objid] = []

        for pt in self.get_points(obj):
            self.rti.insert(len(self.points2obj), (pt[0], pt[1], pt[0], pt[1]), obj=objid)
            self.obj2points[objid].append(len(self.points2obj))
            self.points2obj.append(objid)

    def remove_obj(self, objid, obj):
        for i, pt in enumerate(self.get_points(obj)):
            try:
                self.rti.delete(self.obj2points[objid][i], (pt[0], pt[1], pt[0], pt[1]))
            except IndexError:
                pass

    def nearest(self, pt):
        return next(self.rti.nearest(pt, objects=True))

    def intersection(self, pt):
        return next(self.rti.intersection(pt, objects=True))


class FlatCAMRTreeStorage(FlatCAMRTree):
    def __init__(self):
        super().__init__()
        self.objects = []
        self.indexes = {}

    def insert(self, obj):
        self.objects.append(obj)
        idx = len(self.objects) - 1
        self.indexes[id(obj)] = idx
        super().insert(idx, obj)

    def remove(self, obj):
        objidx = self.indexes[id(obj)]
        self.objects[objidx] = None
        self.remove_obj(objidx, obj)

    def get_objects(self):
        return (o for o in self.objects if o is not None)

    def nearest(self, pt):
        tidx = super(FlatCAMRTreeStorage, self).nearest(pt)
        return (tidx.bbox[0], tidx.bbox[1]), self.objects[tidx.object]
