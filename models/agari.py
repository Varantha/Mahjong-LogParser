from operator import truediv
from models.constants import *
import re

import json

from models.meld import Meld, processMeld
from models.round import Round

from mahjong.meld import Meld as calcMeld
from mahjong.hand_calculating.hand import HandCalculator
from mahjong.tile import TilesConverter
from mahjong.hand_calculating.hand_config import HandConfig, OptionalRules

class Agari:  
    hand = [int]
    melds = [Meld]
    winningTile = None
    riichiSticks = None
    honbaSticks = None
    roundWind = None
    seatWind = None
    doraIndicators = None
    uraDoraIndicators = None
    isDealer = False
    isTsumo = False
    yakusAchieved = []
    pointValue = 0
    fu = 0
    openHand = False
    fu_details = ""

    def __init__(self, hand, melds , roundWind, seatWind, doraIndicators, uraDoraIndicators, winningTile, isDealer, isTsumo, yakusAchieved, pointValue=0, fu=0, han=0, riichiSticks=0, honbaSticks=0,isRiichi=False):
        self.hand = hand
        if melds is None: 
            self.melds = []
            self.openHand = False
        else: 
            self.melds = melds
            self.openHand = True in [meld.open for meld in melds]
        self.winningTile = winningTile
        self.riichiSticks = riichiSticks
        self.honbaSticks = honbaSticks
        self.roundWind = roundWind
        self.seatWind =seatWind
        self.doraIndicators = doraIndicators
        self.uraDoraIndicators = uraDoraIndicators
        self.isDealer = isDealer
        self.isTsumo = isTsumo
        self.isRiichi = isRiichi
        self.yakusAchieved = yakusAchieved
        self.pointValue = pointValue
        self.fu = fu
        self.han = han
        
        


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

    def toJson(self):
        self.fu_details = self.getFuCalculations()
        newAgari: Agari = self
        newAgari.hand = toTileString(self.hand)
        newAgari.melds = newAgari.meldsToTileStringArray()
        newAgari.winningTile = toTileString(self.winningTile)
        newAgari.seatWind = toTileString(self.seatWind)
        return json.dumps(vars(newAgari))

    def validate(self):
        tileTotal = 0
        handCount = len(self.hand)
        tileTotal = tileTotal + handCount
        if self.melds is not None:
            for meld in self.melds:
                tileTotal = tileTotal + 3
        if tileTotal != 14:
            return False
        if "2" in self.yakusAchieved: #hardcode ippatsu removal for now
            return False
        if "3" in self.yakusAchieved: #hardcode chankan removal for now
            return False
        if "4" in self.yakusAchieved: #hardcode rinshan removal for now
            return False
        if "5" in self.yakusAchieved: #hardcode haitei removal for now
            return False
        if "6" in self.yakusAchieved: #hardcode houtei removal for now
            return False
        if "21" in self.yakusAchieved: #hardcode double riichi removal for now
            return False
        return True

    def getFuCalculations(self):
        hand = HandCalculator()  
        converter = TilesConverter()

        meldstring = ""
        melds = []
        for agariMeld in self.melds:
            meldtiles = agariMeld.toTileString().replace("c","")
            if "f" in meldtiles: 
                meldtiles = meldtiles[0] + meldtiles[0] + meldtiles
                meldtiles = meldtiles.replace("f","")
            meldstring += meldtiles
            meld = calcMeld(meld_type=agariMeld.meldType, tiles=converter.one_line_string_to_136_array(meldtiles), opened=agariMeld.open)
            melds.append(meld)

        handstring = toTileString(self.hand).replace("0","5")
        handstring += meldstring
        tiles = converter.one_line_string_to_136_array(handstring)
        wintilestring = toTileString(self.winningTile).replace("0","5")
        win_tile = converter.one_line_string_to_136_array(wintilestring)[0]

        seatWindString = toTileString(self.seatWind).replace("h","")

        config=HandConfig(is_tsumo=self.isTsumo,is_riichi=self.isRiichi,player_wind=[EAST, SOUTH, WEST, NORTH][int(seatWindString) - 1],round_wind=roundStringToInt(self.roundWind))
        hand_est = hand.estimate_hand_value(tiles, win_tile, melds=melds,config=config)

        calculatedFu = 0

        for line in hand_est.fu_details:
            calculatedFu += line['fu']

        difference = hand_est.fu - calculatedFu
        if(difference != 0):
            hand_est.fu_details.append({'fu': difference, 'reason': 'rounding' })
        

        return hand_est.fu_details
        
def roundStringToInt(round_wind):
    winds = ['EAST','SOUTH','WEST','NORTH']
    index = winds.index(round_wind)
    windInt = index + 27
    return windInt


def toTileString(tiles):
    tileOrder = ["s","p","m","h"]
    tileArray = [[],[],[],[]]
    allTiles =  tiles if isinstance(tiles, list) else [tiles]


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
    honbaSticks = int(roundObject.honbaSticks)
    riichiSticks = int(roundObject.riichiSticks)
    doraIndicator = getDoraIndicators(agariString)
    uraDoraIndicators = getUradoraIndicators(agariString)
    isDealer = isPlayerDealer(agariString,roundObject.dealerId)
    yakusAchieved = splitYakuString(agariString)
    isTsumo = isWinTsumo(agariString)
    isRiichi = isPlayerRiichi(yakusAchieved)
    fu, pointValue = getFuAndPointValue(agariString)
    han = sum(yakusAchieved.values())
    
    if('m' in agariString):
        return Agari(handTiles, melds , roundWind, seatWind, doraIndicator, uraDoraIndicators, winningTile, isDealer, isTsumo, yakusAchieved, pointValue, fu, han, riichiSticks, honbaSticks,isRiichi)
    else: 
        return Agari(handTiles, None , roundWind, seatWind, doraIndicator, uraDoraIndicators, winningTile, isDealer, isTsumo, yakusAchieved, pointValue, fu, han, riichiSticks, honbaSticks,isRiichi)


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
    return WINDS[int(winner)-int(oya)] * 4

def isPlayerDealer(agariString, dealerId):
    return(agariString["who"]==dealerId)

def isWinTsumo(agariString):
    return(agariString["who"]==agariString["fromWho"])

def isPlayerRiichi(yakusAchieved):
    return("1" in yakusAchieved)

def getDoraIndicators(agariString):
    return(list(map(lambda tile: toTileString(int(tile)), agariString["doraHai"].split(","))))

def getUradoraIndicators(agariString):
    if('doraHaiUra' in agariString):
        return(list(map(lambda tile: toTileString(int(tile)), agariString["doraHaiUra"].split(","))))
    else:
        return([])
    
def splitYakuString(agariString):
    yakuString = agariString["yaku"].split(",")
    yakusAchieved = {}
    for x in range(0,len(yakuString)):
        if(x % 2 == 0):
            yakusAchieved[yakuString[x]] = int(yakuString[x + 1])
    return yakusAchieved

def getFuAndPointValue(agariString):
    pointString = agariString["ten"].split(",")
    return(pointString[0],pointString[1])



