from mahjong.hand_calculating.hand import HandCalculator

from mahjong.hand_calculating.hand_config import HandConfig, OptionalRules
from mahjong.shanten import Shanten
from mahjong.tile import TilesConverter



calculator = HandCalculator()


# useful helper
def print_hand_result(hand_result):
    print(hand_result.han,",", hand_result.fu)
    print(hand_result.cost['main'])
    print(hand_result.yaku)
    for fu_item in hand_result.fu_details:
        print(fu_item)
    print('')

# we had to use all 14 tiles in that array
tiles = TilesConverter.string_to_136_array(man='11123456788999')
win_tile = TilesConverter.string_to_136_array(man='9')[0]

result = calculator.estimate_hand_value(tiles, win_tile)
print_hand_result(result)

from models.converters import converter
from mahjong.meld import Meld
from models.hand import Hand
meld1 = Meld("chi",[converter.tenhouToTileClass(1),converter.tenhouToTileClass(5),converter.tenhouToTileClass(9)])
meld2 = Meld("pon",[converter.tenhouToTileClass(12),converter.tenhouToTileClass(13),converter.tenhouToTileClass(14)])
melds = [meld1,meld2]

hand1 = Hand([converter.tenhouToTileClass(22),converter.tenhouToTileClass(31),converter.tenhouToTileClass(32)])

test = [c for b in melds for c in b.tiles]
test.extend(hand1.tiles)

print(test)