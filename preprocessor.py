import csv
import os
import pony
from collections import Counter
import numpy as np
from scipy.io import wavfile as wavf
from scipy.interpolate import interp1d, InterpolatedUnivariateSpline
import matplotlib.pyplot as plt
from bisect import bisect as bs
import json
import geopy.distance
from types import SimpleNamespace as sn

with open('settings.json') as settings_file:
    settings = json.loads(settings_file.read(), object_hook=lambda d: sn(**d))

tracks = []


class Point:
    def __init__(self, t, gFx, gFy, gFz, lat, lng, s, dfs=0):
        self.time = t
        self.gfx = gFx
        self.gfy = gFy
        self.gfz = gFz
        self.lat = lat
        self.lng = lng
        self.speed = s
        self.dfromstart = dfs

    def equals(self, other):
        return self.time == other.time and \
               self.gfx == other.gfx and \
               self.gfy == other.gfy and \
               self.gfz == other.gfz and \
               self.lat == other.lat and \
               self.lng == other.lng

    def samecoords(self, other):
        return self.lat == other.lat and \
               self.lng == other.lng

    def getdistance(self, other):
        return abs(geopy.distance.vincenty((self.lat, self.lng), (other.lat, other.lng)).m)

    def getdfromstartusingprev(self, prev):
        self.dfromstart = round(prev.dfromstart + self.getdistance(prev), settings.preprocessor.resolutionplaces)


class Track:
    def __init__(self, fname, points=[]):
        self.filename = fname
        self.points = points
        self.interpoints = []
        self.breakpoints = []

    def loadcsv(self):
        print("Loading track {}".format(self.filename))
        points2interpolate = []
        with open(self.filename, 'r') as c:
            r = csv.DictReader(c)
            prev = Point(0, 0, 0, 0, 0, 0, 0)
            for d in r:
                if not (float(d["Latitude"]) == 0 or float(d["Longitude"]) == 0):
                    n = Point(float(d["time"]), float(d["gFx"]), float(d["gFy"]), float(d["gFz"]),
                              float(d["Latitude"]), float(d["Longitude"]), float(d["Speed (m/s)"]))
                    if n.equals(prev):
                        continue
                    elif n.samecoords(prev):
                        points2interpolate.append(n)
                        prev = n
                    else:
                        prev = n
                        if len(points2interpolate) > 1:
                            [self.points.append(p) for p in self.interpolate(points2interpolate, n)]
                            points2interpolate = []
                        else:
                            points2interpolate.append(n)

        # for i in range(len(self.points)):
        #     print(self.points[i].__dict__)
        # print("Track has {} points! :)".format(len(self.points)))
        # with open("/big/home/karl/Downloads/000_test_all.txt", "a+") as file:
        #     for point in self.points:
        #         file.write(str(point.__dict__).replace("'", '"') + '\r\n')
        # print("DONE!")

    def find_breakpoints(self):
        return 0

    def sort(self):
        self.points.sort(key=lambda x: x.dfromstart)

    def interpolate(self, points, nxt):
        print("Interpolating locations for {}".format(self.filename))
        k = len(points)
        latdiff = nxt.lat - points[0].lat
        lngdiff = nxt.lng - points[0].lng
        latinc = latdiff / k
        lnginc = lngdiff / k
        for p in range(k):
            points[p].lat += p * latinc
            points[p].lng += p * lnginc
        return points

    def locateonpath(self):
        print("Calculating relative positions for {}".format(self.filename))
        for i in range(1, len(self.points)):
            self.points[i].getdfromstartusingprev(self.points[i - 1])

    def resampinterp(self):
        print("Calculating spline for {}".format(self.filename))
        dist = round(self.points[len(self.points)-1].dfromstart, 3)
        x = []
        gfx = []
        gfy = []
        gfz = []
        [x.append(p.dfromstart) for p in self.points]
        x.sort()
        if any((Counter(x) - Counter(set(x))).keys()):
            return 0
        [gfx.append(p.gfx) for p in self.points]
        [gfy.append(p.gfy) for p in self.points]
        [gfz.append(p.gfz) for p in self.points]
        splx = interp1d(x, gfx)
        sply = interp1d(x, gfy)
        splz = interp1d(x, gfz)
        xs = np.linspace(0, dist - dist % settings.preprocessor.meterspersample,
                         int((dist - dist % settings.preprocessor.meterspersample) // settings.preprocessor.meterspersample))

        [self.interpoints.append(Point(None, splx(a), sply(a), splz(a), None, None, None, a)) for a in xs]

        # plt.plot(xs, splx(xs), 'r', lw=1, alpha=0.4)
        # plt.plot(xs, sply(xs), 'g', lw=1, alpha=0.4)
        # plt.plot(xs, splz(xs), 'b', lw=1, alpha=0.4)
        # plt.show()
        # plt.clf()
        # plt.cla()
        # plt.close()

    def toaudio(self):
        x = []
        y = []
        z = []
        [x.append(a.gfx) for a in self.interpoints]
        [y.append(a.gfy) for a in self.interpoints]
        [z.append(a.gfz) for a in self.interpoints]
        x = np.asarray(x)
        y = np.asarray(y)
        z = np.asarray(z)
        print(x)
        print(y)
        print(z)
        try:
            wavf.write('audio3' + self.filename[6:-4] + 'x.wav', 48000, np.interp(x, (x.min(), x.max()), (-1, +1)))
            wavf.write('audio3' + self.filename[6:-4] + 'y.wav', 48000, np.interp(y, (y.min(), y.max()), (-1, +1)))
            wavf.write('audio3' + self.filename[6:-4] + 'z.wav', 48000, np.interp(z, (z.min(), z.max()), (-1, +1)))
            wavf.write('audio3' + self.filename[6:-4] + 'yz.wav', 48000, np.interp(y+z, ((y+z).min(), (y+z).max()), (-1, +1)))
        except:
            print("wtf")

        x = []
        y = []
        z = []
        [x.append(a.gfx) for a in self.points]
        [y.append(a.gfy) for a in self.points]
        [z.append(a.gfz) for a in self.points]
        x = np.asarray(x)
        y = np.asarray(y)
        z = np.asarray(z)
        try:
            wavf.write('audio3' + self.filename[6:-4] + 'xr.wav', 4000, np.interp(x, (x.min(), x.max()), (-1, +1)))
            wavf.write('audio3' + self.filename[6:-4] + 'yr.wav', 4000, np.interp(y, (y.min(), y.max()), (-1, +1)))
            wavf.write('audio3' + self.filename[6:-4] + 'zr.wav', 4000, np.interp(z, (z.min(), z.max()), (-1, +1)))
            wavf.write('audio3' + self.filename[6:-4] + 'yzr.wav', 4000, np.interp(y + z, ((y + z).min(), (y + z).max()), (-1, +1)))
        except:
            print("wtf2")

    def remap(self):
        print("Remapping positions to path {}".format(self.filename))
        rawpositions = []
        [rawpositions.append(x.dfromstart) for x in self.points]
        betweenwho = []
        [betweenwho.append(bs(rawpositions, y.dfromstart)) for y in self.interpoints]
        print(betweenwho)


    def explode(self):
        '''
        This should split tracks to contiguous sets of points.
        '''
        return 0


if __name__ == "__main__":
    files = os.listdir(settings.preprocessor.trackpath)
    for file in files:
        if file.endswith('csv'):
            print(file)
            tracks.append(Track(settings.preprocessor.trackpath + '/' + file))
    for track in tracks:
        track.loadcsv()
        track.explode()
        track.locateonpath()
        track.sort()
        track.resampinterp()
        track.toaudio()
        track.remap()



