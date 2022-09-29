from os import listdir
from os.path import isfile, join

from ProcessLog import GetWinsFromLog

path = "./input"

onlyfiles = [f for f in listdir(path) if isfile(join(path, f))]

for file in onlyfiles:
    print("./input/{}".format(file))
    name = file.split(".")[0]
    ext = file.split(".")[1]

    GetWinsFromLog("./input/{}".format(file),name)

