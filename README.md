# Candy Crush-like

A small match-3 game built with [pygame](https://www.pygame.org/), with swap
and pop (disappear) animations, plus gravity-based falling and cascades.

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

- Click a candy, then click an orthogonally adjacent candy to swap them.
- If the swap creates a run of 3+ same-colored candies (row or column), they
  pop with a shrink animation, you score points, and candies above fall down
  to fill the gaps (new candies spawn from the top) — this can chain into
  combos.
- If the swap doesn't create a match, the two candies animate back to their
  original spots.
- Press `R` to restart with a fresh board.
- The board automatically reshuffles if no valid moves remain.
