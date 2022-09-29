
from os import listdir
from os.path import isfile, join
import json

path = "./output"
outputfilename = "{}/meta.json".format(path)

onlyfiles = [f for f in listdir(path) if isfile(join(path, f))]

with open(outputfilename, 'w') as outfile:
    json.dump(onlyfiles, outfile)

