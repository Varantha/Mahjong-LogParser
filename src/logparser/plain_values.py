"""Plain values: the facts about a hand that drills filter on directly.

Plain values are never tags. The limit tier is one of them, and is also part of the answer key.
"""

# The named payment caps a hand can reach, lowest first. A kazoe yakuman reaches the yakuman's cap
# with 13 han or more and no yakuman; it is told apart from a yakuman.
LIMIT_TIERS = ("none", "mangan", "haneman", "baiman", "sanbaiman", "kazoe-yakuman", "yakuman")
