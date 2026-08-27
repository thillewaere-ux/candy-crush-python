# Donut Crush

A small match-3 game built with [pygame](https://www.pygame.org/) — six
hand-drawn donut flavors (each with its own icing color and topping pattern),
swap/pop/particle-burst animations, and a full scoring HUD.

## Run it

```bash
pip install -r requirements.txt
python candy_crush.py
```

Requires Python 3.8+.

> **Note:** the dependency is [`pygame-ce`](https://pyga.me/) (the actively
> maintained pygame community fork), not the classic `pygame` package — on
> very new Python versions (e.g. 3.14) the classic `pygame` has no prebuilt
> wheel yet and fails to build from source without SDL dev headers.
> `pygame-ce` is a drop-in replacement; your code still just does
> `import pygame`.

## How to play

- Click a donut, then click an orthogonally adjacent donut to swap them.
- If the swap creates a run of 3+ same-flavored donuts (row or column), they
  pop with a shrink + particle-burst animation, you score points, and donuts
  above fall down to fill the gaps (new ones spawn from the top) — this can
  chain into combos, shown with a floating "Combo xN!" badge.
- If the swap doesn't create a match, the two donuts animate back to their
  original spots.
- Reach the score goal (see the progress bar) before you run out of moves to
  win the level; running out of moves first ends the game.
- Your best score is saved locally to `highscore.json` next to the script.
- Click **Pause**/**Restart** in the top bar, or press `P`/`R`, at any time.
- The board automatically reshuffles if no valid moves remain.

## Tuning

Level difficulty is controlled by two constants near the top of
`candy_crush.py`:

- `LEVEL_TARGET` — score needed to win (default `1000`)
- `STARTING_MOVES` — moves allowed before losing (default `30`)
