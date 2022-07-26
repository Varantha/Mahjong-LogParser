from models.constants import *

class Meld:
    tiles = []
    meldType = None
    fromWho = None
    calledTile = None
    open = True

    def __init__(self, tiles, meldType, fromWho=0, calledTile=None, open=True):
        self.tiles = tiles
        self.meldType = meldType
        self.fromWho = fromWho
        self.calledTile = calledTile
        self.open = open

    def __str__(self):
        tileString = ""
        for tile in self.tiles:
            tileString += "{},".format(tile)
        output = "{}: [{}],  open: {}".format(self.meldType,tileString[:-1], self.open)
        return output

    def __repr__(self):
        return self.__str__()

    def toTileString(self):
        tileOrder = ["s","p","m","h"]
        tileArray = [[],[],[],[]]
        allTiles = self.tiles

        iskan = (self.meldType == 'kan')
        isShouminkan = (self.meldType == 'shouminkan')

        if(iskan and not self.open):
            tileID = allTiles[0] // 4
            whichSuit = tileID // 9
            outputString = "f{}{}{}f{}{}".format((((tileID) % 9) + 1),(((tileID) % 9) + 1),(((tileID) % 9) + 1),(((tileID) % 9) + 1),tileOrder[whichSuit])
            #We don't need to worry about order or red fives for closed kans
        else:
            orderedTiles = allTiles[:3] #treat open kans / shouminkans like 3 tiles for now
            indexOfCalledTile = allTiles.index(self.calledTile)
            desiredIndex = 3 - self.fromWho
            direction = int((desiredIndex - indexOfCalledTile) / max(abs(desiredIndex - indexOfCalledTile),1)) #return +1 or -1
            while(indexOfCalledTile != desiredIndex):
                orderedTiles[indexOfCalledTile], orderedTiles[indexOfCalledTile + direction] = orderedTiles[indexOfCalledTile + direction], orderedTiles[indexOfCalledTile]
                indexOfCalledTile = indexOfCalledTile + direction

            for tile in orderedTiles:
                tileID = tile // 4
                whichSuit = tileID // 9
                if(tile in AKA_DORA_LIST):
                    tileArray[whichSuit].append("0")
                else:
                    tileArray[whichSuit].append(str(((tileID) % 9) + 1))
            if(iskan):
                tileArray[whichSuit].insert(1,str(((allTiles[3] // 4) % 9) + 1)) #insert the tile we took out earlier
                #it works in all cases if inserted into index 1 
            outputString = "" 
            for j in range(0,len(tileArray[whichSuit])):
                if(j == indexOfCalledTile):
                    outputString += "c{}".format(tileArray[whichSuit][j])
                    if(isShouminkan):
                        outputString += "c{}".format(tileArray[whichSuit][j]) 
                else:
                    outputString += tileArray[whichSuit][j]

            outputString += tileOrder[whichSuit]
    
        return outputString
    
def processMeld(meldCode: int):
    meldCode = int(meldCode)
    binaryString = format(meldCode, "016b")
    openCall = True
    calledFrom = int(binaryString[-2:],2)

    # I have 0.5 idea how any of the below works. Anyone who can explain it to me gets a cookie. Written by @NegativeMjark / @Euophrys
    if binaryString[-3] == '1':
        # Chii
        callType = "Chi"
        t0, t1, t2 = (meldCode >> 3) & 0x3, (meldCode >> 5) & 0x3, (meldCode >> 7) & 0x3
        baseAndCalled = meldCode >> 10
        order = baseAndCalled % 3
        baseTile = baseAndCalled // 3
        baseTile = (baseTile // 7) * 9 + baseTile % 7
        Tiles = [t0 + 4 * (baseTile + 0), t1 + 4 * (baseTile + 1), t2 + 4 * (baseTile + 2)]
        calledTile = Tiles[order]

    elif meldCode & 0x18:
        t4 = (meldCode >> 5) & 0x3
        t0, t1, t2 = ((1, 2, 3), (0, 2, 3), (0, 1, 3), (0, 1, 2))[t4]
        baseAndCalled = meldCode >> 9
        order = baseAndCalled % 3
        base = baseAndCalled // 3
        if meldCode & 0x8:
            callType = "pon"
            Tiles = [t0 + 4 * base, t1 + 4 * base, t2 + 4 * base]
        else:
            callType = "shouminkan"
            Tiles = [t0 + base * 4, t1 + base* 4, t2 + base* 4, t4 + base* 4]
        calledTile = Tiles[order]
      
    else:
        # kan
        callType = "kan"
        baseAndCalled = meldCode >>8
        base = baseAndCalled // 4
        Tiles = [base* 4, 1 + base* 4, 2 + base* 4, 3 + base* 4]
        if(calledFrom == 0):
            openCall = False
        calledTile = Tiles[3 - calledFrom]

    return Meld(Tiles,callType,calledFrom,calledTile,openCall)

