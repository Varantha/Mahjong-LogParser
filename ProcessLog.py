
import xml.etree.ElementTree as ET
from models.agari import processAgari


from models.meld import processMeld
from models.round import Round, processRound
from models.agari import Agari




lastEntry = ""
FileNumber = 1

tree = ET.parse('ExampleLog.xml')
for elem in tree.iter():
    #print("%s: '%s'" % (elem.tag, elem.attrib))
    if(elem.tag == "INIT"):
        round = processRound(elem.attrib)
    if(elem.tag == "REACH"):
        if(elem.attrib["step"]== "2"):
            round.addRiichiStick()
    if(elem.tag == "AGARI"):
        agari: Agari = processAgari(elem.attrib,lastEntry,round)
        #print(elem.attrib)
        #print("Hand: {}, melds: {}, Tsumo: {}, Riichi: {}, YakusAndHan: {}".format(agari.handToTileString(),agari.meldsToTileStringArray(),agari.isTsumo,agari.isRiichi,agari.yakusAchieved))

        with open('./output/{}.json'.format(FileNumber), 'w') as file:
            file.write(str(agari.toJson()))
        FileNumber = FileNumber + 1


    lastEntry = elem.tag




