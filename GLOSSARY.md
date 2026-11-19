# Mahjong Log Parser

Turns Tenhou game logs into verified, tagged hands that the Scoring Trainer uses as practice questions.

## Language

### Pipeline

**Log store**:
The collection of unparsed Tenhou game logs, keyed by log ID, that hands are parsed from.
_Avoid_: raw data, input, db

**Hand store**:
Every hand parsed from the log store, each with its verification result and tags. The first stage's output.
_Avoid_: raw dataset, master dataset

**Trainer bundle**:
The curated slice of the hand store that the Scoring Trainer ships. The second stage's output.
_Avoid_: export, output, app data

### Hands

**Hand**:
One scorable win taken from a log: its tiles, its situation and its answer key. A double ron gives two hands.
_Avoid_: agari (outside parser code), win record, problem, question

**Concealed tiles**:
The tiles of a hand that are not part of any call.
_Avoid_: hand (for the tiles), closed hand

**Raw fu**:
A hand's fu before it is rounded up to the next 10.
_Avoid_: unrounded fu, base fu (base is one fu component)

**Fu breakdown**:
Where a hand's raw fu come from: the base, a closed ron or a tsumo, each set, the pair and the wait, each under a contract key with its fu. Only a hand whose cross-check matched has one.
_Avoid_: fu details, fu reasons (the `mahjong` library's terms)

**Split**:
One way of reading a hand's tiles as four sets and a pair, its calls kept as they were made, together with the concealed set or pair the winning tile completed. A hand can have several splits with different fu; Tenhou scores the one worth the most points. Seven pairs is not a split.
_Avoid_: decomposition, interpretation, hand division (the `mahjong` library's terms)

**Limit tier**:
The named payment cap a hand reaches: none, mangan, haneman, baiman, sanbaiman, kazoe yakuman or yakuman. A kazoe yakuman reaches the yakuman's cap with 13 han or more and no yakuman.
_Avoid_: limit, limit hand level

**Plain value**:
A fact about a hand that drills filter on directly: han, fu, raw fu, limit tier, dealer, tsumo or ron, open or closed, yaku, dora count, honba, riichi sticks and call types. Plain values are never tags.
_Avoid_: attribute, filter, feature

**Dora count**:
The han a hand gets from dora, aka dora and ura dora, as Tenhou recorded them. A yakuman has none, because Tenhou records no dora with it.
_Avoid_: dora (for the count), number of dora

**Tag**:
A named fact derived from a hand, often a trap a player could fall into. Players never see it before answering. Plain values such as han, fu or yaku are not tags.
_Avoid_: indicator (clashes with dora indicator), category, flag

**Drill**:
A set of hands a player picks to practise one scoring skill. Drills are built from tags and plain values.
_Avoid_: category, mode, challenge, quiz

**Lookalike**:
A hand in a drill that comes from the same pool as the drill's trap hands but does not have the trap, so the drill doesn't give the answer away.
_Avoid_: decoy, filler

### Verification

**Answer key**:
The yaku, han, fu and points that Tenhou recorded for a hand.
_Avoid_: expected result, ground truth

**Cross-check**:
A separate recalculation of a hand's score that has to match the answer key exactly.
_Avoid_: validation, test

**Quarantined hand**:
A hand that failed its cross-check or could not be parsed. It stays in the hand store with a reason and never reaches the trainer bundle.
_Avoid_: bad hand, failed hand, rejected hand

**Tenhou rules**:
The only ruleset answer keys are scored under. Variants such as kiriage mangan are applied by the trainer on top.
_Avoid_: standard rules, default rules
