import xml.etree.ElementTree as ET
from models.agari import processAgari

from models.round import processRound
from models.agari import Agari

def GetWinsFromLog(logPath,outputFilename):

    lastEntry = ""
    FileNumber = 1

    tree = ET.parse(logPath)
    for elem in tree.iter():
        if(elem.tag == "INIT"):
            round = processRound(elem.attrib)
        if(elem.tag == "REACH"):
            if(elem.attrib["step"]== "2"):
                round.addRiichiStick()
        if(elem.tag == "AGARI"):
            agari: Agari = processAgari(elem.attrib,lastEntry,round)
            with open('./output/{}{}.json'.format(outputFilename,FileNumber), 'w') as file:
                file.write(str(agari.toJson()))
            FileNumber = FileNumber + 1

    lastEntry = elem.tag




