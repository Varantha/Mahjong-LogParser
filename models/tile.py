class Tile:
    tile = None
    akaDora = False

    def __init__(self, tileID, akaDora=False):
        self.tileID = tileID
        self.akaDora = akaDora

    def __str__(self):
        return str(self.tileID)

    def __repr__(self):
        return self.__str__()

    def strAkaDora(self):
        return "tile: {}, akaDora: {}".format(self.tileID, self.akaDora)

