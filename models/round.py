
class Round:
    riichiSticks = None
    honbaSticks = None
    roundName = None
    roundWind = None
    doraIndicator = None
    dealerId = None
    
    def __init__(self, riichiSticks=0, honbaSticks=0, dealerId=None, roundId=None, doraIndicator=None):
        roundId = int(roundId)
        roundWind = roundIdToWind(roundId)
        roundNumber = (roundId + 1 ) - (4 * (roundId // 4))
        
        self.riichiSticks = riichiSticks
        self.honbaSticks = honbaSticks
        self.dealerId = dealerId
        self.roundName = "{}{}".format(roundWind,str(roundNumber))
        self.roundWind = roundWind
        self.doraIndicator = doraIndicator

    def addRiichiStick(self, number=1):
        self.riichiSticks = int(self.riichiSticks) + int(number)

    def __str__(self) -> str:
        output = "riichiSticks: {}, honbaSticks: {}, dealerId: {}, roundName: {}, roundWind: {}, doraIndicator: {}".format(self.riichiSticks,self.honbaSticks,self.dealerId,self.roundName,self.roundWind,self.doraIndicator)
        return output    

def roundIdToWind(roundID):
    roundNames = ["EAST","SOUTH","WEST","NORTH"]
    return roundNames[roundID // 4]

def processRound(roundObject):
    roundID = roundObject["seed"].split(",")[0]
    honbaSticks = roundObject["seed"].split(",")[1]
    riichiSticks = roundObject["seed"].split(",")[2]
    doraIndicator = roundObject["seed"].split(",")[5]
    dealerID = roundObject["oya"]
    return Round(riichiSticks,honbaSticks,dealerID,roundID,doraIndicator)
