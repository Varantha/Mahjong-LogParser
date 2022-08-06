
import xml.etree.ElementTree as ET
from models.agari import processAgari

from models.meld import processMeld
from models.round import Round, processRound
from models.agari import Agari




lastEntry = ""

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
        print(elem.attrib)
        print("Hand: {}, melds: {}".format(agari.hand,agari.melds))

        print(agari.isRiichi)


    lastEntry = elem.tag




