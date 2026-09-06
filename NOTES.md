
- Browser sim round 6 (fork 160f07b / d6f7646): the official daemon wobbler ported line for line (speech tapper +
  head wobbler, offline hops per wav line; synthetic ~4 Hz syllables for browser-TTS lines); the lament turn verified
  by FK (body joint and head world yaw both 80 deg, Stewart joints at home); the pick opens the beak; Reachy moves
  silent; follow cam. PR to Laureen: https://huggingface.co/spaces/FormaLau/microduck-reachy-simulator/discussions/1
  (wobbler port + silent moves, on her `source/src` tree). The turn direction depends on which side the duck stands:
  +1.4 = left = away from a duck on Reachy right (our staging); the sim builder negates it for its own staging.
