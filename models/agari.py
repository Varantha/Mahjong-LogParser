from operator import truediv
from models.constants import *
import re

from models.meld import Meld, processMeld
from models.round import Round


class Agari:  
    hand = [int]
    melds = [Meld]
    winningTile = None
    riichiSticks = None
    honbaSticks = None
    roundWind = None
    seatWind = None
    doraIndicator = None
    isDealer = False
    isTsumo = False

    def __init__(self, hand, melds , roundWind, seatWind, doraIndicator, winningTile, isDealer, isTsumo,riichiSticks=0, honbaSticks=0,isRiichi=False):
        self.hand = hand
        if self.melds is None: 
            self.melds = []
        else: 
            self.melds = melds
        self.winningTile = winningTile
        self.riichiSticks = riichiSticks
        self.honbaSticks = honbaSticks
        self.roundWind = roundWind
        self.seatWind =seatWind
        self.doraIndicator = doraIndicator
        self.isDealer = isDealer
        self.isTsumo = isTsumo
        self.isRiichi = isRiichi

    def toHandConfig(self):
        True

    def meldsToTileStringArray(self):
        melds = self.melds
        meldStrings = []
        if melds is None:
            return meldStrings
            
        for meld in melds:
            meldStrings.append(meld.toTileString())
        return meldStrings


    def handToTileString(self):
        tileOrder = ["s","p","m","h"]
        tileArray = [[],[],[],[]]
        allTiles = self.hand

        for tile in allTiles:
            tileID = tile // 4
            whichSuit = tileID // 9
            if(tile in AKA_DORA_LIST):
                tileArray[whichSuit].append("0")
            else:
                tileArray[whichSuit].append(str(((tileID) % 9) + 1))
        
        outputString = "" 
        for i in range(0,len(tileArray)):
            for j in range(0,len(tileArray[i])):
                outputString += tileArray[i][j]
            if(len(tileArray[i]) > 0):
                outputString += tileOrder[i]
        return outputString        


def processAgari(agariString,lastEntry,roundObject):
    handTiles = getHand(agariString)
    if('m' in agariString):
        melds = getMelds(agariString["m"])
    winningTile = getWinningTile(lastEntry)
    roundWind = roundObject.roundWind
    seatWind = getSeatWind(roundObject.dealerId,agariString["who"])
    honbaSticks = roundObject.honbaSticks, 
    riichiSticks = roundObject.riichiSticks
    doraIndicator = roundObject.doraIndicator
    isDealer = isPlayerDealer(agariString,roundObject.dealerId)
    yakusAchieved = splitYakuString(agariString)
    isTsumo = isWinTsumo(yakusAchieved)
    isRiichi = isPlayerRiichi(yakusAchieved)
    
    
    if('m' in agariString):
        return Agari(handTiles, melds , roundWind, seatWind, doraIndicator, winningTile, isDealer, isTsumo,riichiSticks, honbaSticks,isRiichi)
    else: 
        return Agari(handTiles, None , roundWind, seatWind, doraIndicator, winningTile, isDealer, isTsumo,riichiSticks, honbaSticks,isRiichi)


def getHand(agariString):
    tileArray = [int(x) for x in agariString["hai"].split(",")]
    return(tileArray)

def getMelds(melds):
    allMelds = []
    for meld in melds.split(","):
        allMelds.append(processMeld(meld))
    return allMelds

def getWinningTile(lastEntry):
    return int(re.search("\d+",lastEntry).group())

def getSeatWind(oya,winner):
    return WINDS[int(winner)-int(oya)]

def isPlayerDealer(agariString, dealerId):
    return(agariString["who"]==dealerId)

def isWinTsumo(yakusAchieved):
    return("0" in yakusAchieved)

def isPlayerRiichi(yakusAchieved):
    return("1" in yakusAchieved)

def splitYakuString(agariString):
    yakuString = agariString["yaku"].split(",")
    yakusAchieved = {}
    for x in range(0,len(yakuString)):
        if(x % 2 == 0):
            yakusAchieved[yakuString[x]] = yakuString[x + 1]
    return yakusAchieved




