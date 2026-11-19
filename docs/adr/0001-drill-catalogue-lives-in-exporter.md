# The drill catalogue lives in the exporter, not the trainer

Drills are the Scoring Trainer's only way of choosing hands, so you might expect them to be defined in the trainer's UI code. They are defined here instead, and the second stage builds each drill's pool of hands by searching the whole hand store. The trainer only ever sees the trainer bundle, which is a small sample. A drill over rare hands (kazoe yakuman, ambiguous waits) needs hands found across millions of wins, and drills built on tags that give the answer away need lookalikes drawn from the same pool. Neither can be done from the bundle alone.

## Considered Options

- **Trainer defines drills as filters over the bundle.** New drills need no re-export, but a drill's pool is limited to whatever the bundle happened to include, so rare drills come out thin or empty.
- **Exporter defines drills (chosen).** Adding or changing a drill means running the second stage again. That is cheap compared with shipping drills that have too few hands.

## Consequences

The bundle records which hands belong to which drill by hand ID, and stores each hand only once. The trainer shows display names for drills by translating their keys, the same way it handles yaku names.
