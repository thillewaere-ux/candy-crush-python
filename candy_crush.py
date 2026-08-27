"""
Candy Crush-like match-3 game.

Run locally with:
    pip install pygame
    python candy_crush.py

Controls:
    Click a candy, then click an orthogonally adjacent candy to swap them.
    Matching 3+ candies in a row/column pops them (with an animation) and
    awards points. Invalid swaps animate back to their original spot.
"""

import random
import sys

import pygame

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROWS, COLS = 8, 8
CELL = 64
MARGIN_TOP = 70
PADDING = 8
WIDTH = COLS * CELL
HEIGHT = ROWS * CELL + MARGIN_TOP
FPS = 60

SWAP_DURATION = 0.16   # seconds for a swap tween
POP_DURATION = 0.22    # seconds for the pop/shrink animation
GRAVITY = 2600.0       # pixels / s^2 for falling candies

BG_COLOR = (28, 26, 44)
GRID_COLOR_A = (40, 37, 62)
GRID_COLOR_B = (35, 32, 56)
SELECT_COLOR = (255, 255, 255)
TEXT_COLOR = (240, 240, 245)

COLORS = [
    (231, 76, 60),    # red
    (241, 196, 15),   # yellow
    (46, 204, 113),   # green
    (52, 152, 219),   # blue
    (155, 89, 182),   # purple
    (230, 126, 34),   # orange
]

N_COLORS = len(COLORS)


def cell_pos(row, col):
    """Top-left pixel position of a grid cell."""
    return col * CELL, MARGIN_TOP + row * CELL


def cell_center(row, col):
    x, y = cell_pos(row, col)
    return x + CELL / 2, y + CELL / 2


# ---------------------------------------------------------------------------
# Candy
# ---------------------------------------------------------------------------

class Candy:
    __slots__ = ("color", "row", "col", "x", "y", "scale", "vy", "popping",
                 "pop_t", "settled")

    def __init__(self, color, row, col, spawn_y=None):
        self.color = color
        self.row = row
        self.col = col
        x, y = cell_pos(row, col)
        self.x = float(x)
        self.y = float(spawn_y if spawn_y is not None else y)
        self.scale = 1.0
        self.vy = 0.0
        self.popping = False
        self.pop_t = 0.0
        self.settled = False

    def target_xy(self):
        return cell_pos(self.row, self.col)

    def draw(self, surf):
        cx = self.x + CELL / 2
        cy = self.y + CELL / 2
        radius = (CELL / 2 - PADDING) * self.scale
        if radius <= 0:
            return
        r, g, b = COLORS[self.color]
        pygame.draw.circle(surf, (r, g, b), (int(cx), int(cy)), int(radius))
        pygame.draw.circle(surf, (255, 255, 255), (int(cx), int(cy)),
                            int(radius), max(1, int(radius * 0.12)))
        # a soft highlight to make the candy look glossy
        hl_r = max(2, int(radius * 0.35))
        pygame.draw.circle(
            surf, (255, 255, 255),
            (int(cx - radius * 0.35), int(cy - radius * 0.35)), hl_r,
        )


# ---------------------------------------------------------------------------
# Board helpers
# ---------------------------------------------------------------------------

def random_color(exclude=()):
    choices = [c for c in range(N_COLORS) if c not in exclude]
    return random.choice(choices)


def make_board():
    grid = [[None for _ in range(COLS)] for _ in range(ROWS)]
    for r in range(ROWS):
        for c in range(COLS):
            exclude = set()
            if c >= 2 and grid[r][c - 1].color == grid[r][c - 2].color:
                exclude.add(grid[r][c - 1].color)
            if r >= 2 and grid[r - 1][c].color == grid[r - 2][c].color:
                exclude.add(grid[r - 1][c].color)
            color = random_color(exclude)
            grid[r][c] = Candy(color, r, c)
    return grid


def find_matches(grid):
    """Return a set of (row, col) positions that are part of a run of 3+."""
    matched = set()

    for r in range(ROWS):
        run = [0]
        for c in range(1, COLS + 1):
            same = (c < COLS and grid[r][c] is not None and grid[r][c - 1] is not None
                    and grid[r][c].color == grid[r][c - 1].color)
            if same:
                run.append(c)
            else:
                if len(run) >= 3:
                    matched.update((r, k) for k in run)
                run = [c] if c < COLS else []

    for c in range(COLS):
        run = [0]
        for r in range(1, ROWS + 1):
            same = (r < ROWS and grid[r][c] is not None and grid[r - 1][c] is not None
                    and grid[r][c].color == grid[r - 1][c].color)
            if same:
                run.append(r)
            else:
                if len(run) >= 3:
                    matched.update((k, c) for k in run)
                run = [r] if r < ROWS else []

    return matched


def has_valid_move(grid):
    """Check whether any adjacent swap would produce a match."""
    for r in range(ROWS):
        for c in range(COLS):
            for dr, dc in ((0, 1), (1, 0)):
                nr, nc = r + dr, c + dc
                if nr >= ROWS or nc >= COLS:
                    continue
                colors = [[cell.color for cell in row] for row in grid]
                colors[r][c], colors[nr][nc] = colors[nr][nc], colors[r][c]
                if has_match_colors(colors):
                    return True
    return False


def has_match_colors(colors):
    for r in range(ROWS):
        for c in range(COLS - 2):
            if colors[r][c] == colors[r][c + 1] == colors[r][c + 2]:
                return True
    for c in range(COLS):
        for r in range(ROWS - 2):
            if colors[r][c] == colors[r + 1][c] == colors[r + 2][c]:
                return True
    return False


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Game:
    IDLE = "idle"
    SWAPPING = "swapping"
    POPPING = "popping"
    FALLING = "falling"

    def __init__(self):
        self.grid = make_board()
        while not has_valid_move(self.grid):
            self.grid = make_board()

        self.state = Game.IDLE
        self.selected = None
        self.timer = 0.0
        self.combo = 0
        self.score = 0

        self.pending_swap = None   # (r1, c1, r2, c2)
        self.swap_start = {}
        self.swap_is_trial = True
        self.popping_cells = []

        self.font = pygame.font.SysFont("arial", 28, bold=True)
        self.small_font = pygame.font.SysFont("arial", 18)

    # -- input -------------------------------------------------------------

    def handle_click(self, pos):
        if self.state != Game.IDLE:
            return
        x, y = pos
        if y < MARGIN_TOP:
            return
        col = x // CELL
        row = (y - MARGIN_TOP) // CELL
        if not (0 <= row < ROWS and 0 <= col < COLS):
            return

        if self.selected is None:
            self.selected = (row, col)
            return

        sr, sc = self.selected
        if (sr, sc) == (row, col):
            self.selected = None
            return

        if abs(sr - row) + abs(sc - col) == 1:
            self.start_swap(sr, sc, row, col, trial=True)
            self.selected = None
        else:
            self.selected = (row, col)

    # -- state transitions ---------------------------------------------------

    def start_swap(self, r1, c1, r2, c2, trial):
        a, b = self.grid[r1][c1], self.grid[r2][c2]
        self.grid[r1][c1], self.grid[r2][c2] = b, a
        a.row, a.col = r2, c2
        b.row, b.col = r1, c1
        self.pending_swap = (r1, c1, r2, c2)
        self.swap_start = {
            (r2, c2): (a.x, a.y),
            (r1, c1): (b.x, b.y),
        }
        self.swap_is_trial = trial
        self.state = Game.SWAPPING
        self.timer = 0.0

    def begin_pop(self, matched):
        self.combo += 1
        self.score += len(matched) * 10 * self.combo
        self.popping_cells = list(matched)
        for (r, c) in matched:
            candy = self.grid[r][c]
            if candy is not None:
                candy.popping = True
                candy.pop_t = 0.0
        self.state = Game.POPPING
        self.timer = 0.0

    def begin_fall(self):
        for c in range(COLS):
            column = [self.grid[r][c] for r in range(ROWS) if self.grid[r][c] is not None]
            missing = ROWS - len(column)

            new_column = [None] * ROWS
            write_row = ROWS - 1
            for candy in reversed(column):
                candy.row = write_row
                candy.col = c
                candy.settled = False
                new_column[write_row] = candy
                write_row -= 1

            for i in range(missing):
                row = write_row
                color = random_color()
                spawn_y = MARGIN_TOP - (missing - i) * CELL
                candy = Candy(color, row, c, spawn_y=spawn_y)
                candy.vy = 0.0
                new_column[row] = candy
                write_row -= 1

            for r in range(ROWS):
                self.grid[r][c] = new_column[r]

        self.state = Game.FALLING
        self.timer = 0.0

    # -- update --------------------------------------------------------------

    def update(self, dt):
        if self.state == Game.SWAPPING:
            self.update_swapping(dt)
        elif self.state == Game.POPPING:
            self.update_popping(dt)
        elif self.state == Game.FALLING:
            self.update_falling(dt)

    def update_swapping(self, dt):
        self.timer += dt
        t = min(1.0, self.timer / SWAP_DURATION)
        eased = 1 - (1 - t) ** 2  # ease-out
        for (r, c) in ((self.pending_swap[0], self.pending_swap[1]),
                       (self.pending_swap[2], self.pending_swap[3])):
            candy = self.grid[r][c]
            tx, ty = candy.target_xy()
            sx, sy = self.swap_start[(r, c)]
            candy.x = sx + (tx - sx) * eased
            candy.y = sy + (ty - sy) * eased

        if t >= 1.0:
            for (r, c) in ((self.pending_swap[0], self.pending_swap[1]),
                           (self.pending_swap[2], self.pending_swap[3])):
                candy = self.grid[r][c]
                candy.x, candy.y = candy.target_xy()

            matched = find_matches(self.grid)
            if matched:
                self.combo = 0
                self.begin_pop(matched)
            elif self.swap_is_trial:
                r1, c1, r2, c2 = self.pending_swap
                self.start_swap(r1, c1, r2, c2, trial=False)
            else:
                self.state = Game.IDLE
                self.pending_swap = None

    def update_popping(self, dt):
        self.timer += dt
        for (r, c) in self.popping_cells:
            candy = self.grid[r][c]
            if candy is None:
                continue
            candy.pop_t = min(1.0, self.timer / POP_DURATION)
            candy.scale = max(0.0, 1.0 - candy.pop_t)

        if self.timer >= POP_DURATION:
            for (r, c) in self.popping_cells:
                self.grid[r][c] = None
            self.popping_cells = []
            self.begin_fall()

    def update_falling(self, dt):
        all_settled = True
        for c in range(COLS):
            for r in range(ROWS):
                candy = self.grid[r][c]
                if candy is None:
                    continue
                tx, ty = candy.target_xy()
                if candy.y < ty:
                    candy.vy += GRAVITY * dt
                    candy.y += candy.vy * dt
                    if candy.y >= ty:
                        candy.y = ty
                        candy.vy = 0.0
                        candy.settled = True
                    else:
                        all_settled = False
                else:
                    candy.y = ty
                    candy.settled = True
                candy.x = tx

        if all_settled:
            matched = find_matches(self.grid)
            if matched:
                self.begin_pop(matched)
            else:
                self.combo = 0
                if not has_valid_move(self.grid):
                    self.reshuffle()
                self.state = Game.IDLE

    def reshuffle(self):
        colors = [candy.color for row in self.grid for candy in row]
        random.shuffle(colors)
        i = 0
        for r in range(ROWS):
            for c in range(COLS):
                self.grid[r][c].color = colors[i]
                i += 1
        while not has_valid_move(self.grid) or find_matches(self.grid):
            colors = [candy.color for row in self.grid for candy in row]
            random.shuffle(colors)
            i = 0
            for r in range(ROWS):
                for c in range(COLS):
                    self.grid[r][c].color = colors[i]
                    i += 1

    # -- draw ------------------------------------------------------------

    def draw(self, surf):
        surf.fill(BG_COLOR)

        for r in range(ROWS):
            for c in range(COLS):
                x, y = cell_pos(r, c)
                color = GRID_COLOR_A if (r + c) % 2 == 0 else GRID_COLOR_B
                pygame.draw.rect(surf, color, (x, y, CELL, CELL))

        if self.selected is not None and self.state == Game.IDLE:
            r, c = self.selected
            x, y = cell_pos(r, c)
            pygame.draw.rect(surf, SELECT_COLOR, (x, y, CELL, CELL), 3)

        for r in range(ROWS):
            for c in range(COLS):
                candy = self.grid[r][c]
                if candy is not None:
                    candy.draw(surf)

        score_text = self.font.render(f"Score: {self.score}", True, TEXT_COLOR)
        surf.blit(score_text, (12, 18))

        hint = self.small_font.render(
            "Click a candy, then an adjacent one to swap", True, (170, 168, 190))
        surf.blit(hint, (WIDTH - hint.get_width() - 12, 26))


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    pygame.init()
    pygame.display.set_caption("Candy Crush-like")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    game = Game()

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                game.handle_click(event.pos)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                game = Game()

        game.update(dt)
        game.draw(screen)
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
