"""
Donut Crush - a match-3 game with swap/pop animations, particle bursts,
a scoring HUD (score, best score, moves, goal progress, combo), and
win/lose/pause states.

Run locally with:
    pip install -r requirements.txt
    python candy_crush.py

Controls:
    Click a donut, then click an orthogonally adjacent donut to swap them.
    Matching 3+ donuts in a row/column pops them (with an animation) and
    awards points. Invalid swaps animate back to their original spot.
    R restarts, P (or the Pause button) pauses.
"""

import json
import math
import random
import sys
from pathlib import Path

import pygame

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROWS, COLS = 8, 8
CELL = 64
CANDY_PADDING = 8      # inset between a donut and its cell edge
BOARD_PADDING = 14     # panel padding around the grid
HEADER_HEIGHT = 104
FOOTER_HEIGHT = 44
FPS = 60

BOARD_LEFT = BOARD_PADDING
BOARD_TOP = HEADER_HEIGHT + BOARD_PADDING
GRID_W = COLS * CELL
GRID_H = ROWS * CELL
WIDTH = GRID_W + BOARD_PADDING * 2
HEIGHT = BOARD_TOP + GRID_H + BOARD_PADDING + FOOTER_HEIGHT

SWAP_DURATION = 0.16    # seconds for a swap tween
POP_DURATION = 0.22     # seconds for the pop/shrink animation
GRAVITY = 2600.0        # pixels / s^2 for falling candies
COMBO_BADGE_TIME = 1.2  # seconds the "Combo xN" badge stays visible

LEVEL_TARGET = 1000     # score needed to win the level
STARTING_MOVES = 30     # moves allowed before losing

HIGHSCORE_PATH = Path(__file__).resolve().parent / "highscore.json"

BG_TOP = (30, 24, 46)
BG_BOTTOM = (16, 13, 26)
PANEL_COLOR = (48, 42, 72)
PANEL_SHADOW = (10, 9, 18)
GRID_COLOR_A = (58, 51, 86)
GRID_COLOR_B = (52, 46, 78)
TEXT_COLOR = (240, 240, 245)
MUTED_TEXT = (176, 172, 200)
GOLD = (255, 205, 86)
COMBO_COLOR = (255, 140, 90)
BUTTON_COLOR = (74, 66, 116)
BUTTON_BORDER = (108, 98, 156)
BAR_BG = (60, 54, 88)
WIN_COLOR = (120, 220, 150)
LOSE_COLOR = (230, 110, 100)

# Donut flavors: icing color, topping accent color, hole shade, topping pattern.
FLAVORS = [
    {"name": "Chocolate",  "icing": (94, 58, 36),   "accent": (245, 235, 220),
     "hole": (55, 32, 18),  "pattern": "drizzle"},
    {"name": "Strawberry", "icing": (233, 108, 146), "accent": (255, 255, 255),
     "hole": (168, 60, 96), "pattern": "sprinkles"},
    {"name": "Blueberry",  "icing": (96, 98, 206),   "accent": (210, 210, 250),
     "hole": (56, 56, 138), "pattern": "dots"},
    {"name": "Vanilla",    "icing": (247, 224, 168), "accent": (255, 250, 235),
     "hole": (198, 165, 108), "pattern": "sprinkles"},
    {"name": "Pistachio",  "icing": (150, 196, 92),  "accent": (222, 240, 190),
     "hole": (92, 130, 52), "pattern": "stripes"},
    {"name": "Caramel",    "icing": (214, 148, 62),  "accent": (250, 220, 170),
     "hole": (150, 96, 33), "pattern": "swirl"},
]
N_COLORS = len(FLAVORS)

SPRINKLE_COLORS = [
    (255, 255, 255), (231, 76, 60), (241, 196, 15),
    (46, 204, 113), (52, 152, 219), (155, 89, 182),
]

BUTTON_W, BUTTON_H = 80, 26


def cell_pos(row, col):
    """Top-left pixel position of a grid cell."""
    return BOARD_LEFT + col * CELL, BOARD_TOP + row * CELL


def cell_center(row, col):
    x, y = cell_pos(row, col)
    return x + CELL / 2, y + CELL / 2


def darken(color, amount):
    return tuple(max(0, c - amount) for c in color)


def lighten(color, amount):
    return tuple(min(255, c + amount) for c in color)


def make_gradient(width, height, top_color, bottom_color):
    surf = pygame.Surface((width, height))
    for y in range(height):
        t = y / max(1, height - 1)
        color = tuple(int(top_color[i] + (bottom_color[i] - top_color[i]) * t) for i in range(3))
        pygame.draw.line(surf, color, (0, y), (width, y))
    return surf


def alpha_circle(radius, color, alpha):
    radius = max(1, int(radius))
    d = radius * 2
    s = pygame.Surface((d, d), pygame.SRCALPHA)
    pygame.draw.circle(s, (*color, max(0, min(255, int(alpha)))), (radius, radius), radius)
    return s


def load_best():
    try:
        with open(HIGHSCORE_PATH) as f:
            return int(json.load(f).get("best", 0))
    except Exception:
        return 0


def save_best(value):
    try:
        with open(HIGHSCORE_PATH, "w") as f:
            json.dump({"best": int(value)}, f)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Donut drawing
# ---------------------------------------------------------------------------

def draw_topping(surf, cx, cy, radius, pattern, accent):
    outer = radius * 0.92
    inner = radius * 0.5
    width = max(2, int(radius * 0.11))

    if pattern == "sprinkles":
        n = 9
        for i in range(n):
            angle = (2 * math.pi * i / n) + 0.3
            rr = inner + (outer - inner) * (0.3 + 0.6 * ((i * 37) % 5) / 5)
            x = cx + math.cos(angle) * rr
            y = cy + math.sin(angle) * rr
            color = SPRINKLE_COLORS[i % len(SPRINKLE_COLORS)]
            length = max(3, radius * 0.16)
            dx = math.cos(angle + 1.2) * length / 2
            dy = math.sin(angle + 1.2) * length / 2
            pygame.draw.line(surf, color, (x - dx, y - dy), (x + dx, y + dy), width)
    elif pattern == "dots":
        n = 8
        rr = (outer + inner) / 2
        for i in range(n):
            angle = 2 * math.pi * i / n
            x = cx + math.cos(angle) * rr
            y = cy + math.sin(angle) * rr
            pygame.draw.circle(surf, accent, (int(x), int(y)), max(2, int(radius * 0.11)))
    elif pattern == "drizzle":
        for i in range(4):
            base_angle = 2 * math.pi * i / 4 + 0.4
            pts = []
            for k in range(4):
                a = base_angle + k * 0.5
                rr = inner + (outer - inner) * (k / 3)
                pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
            pygame.draw.lines(surf, accent, False, pts, width)
    elif pattern == "stripes":
        for i in range(5):
            angle = 2 * math.pi * i / 5
            x1, y1 = cx + math.cos(angle) * inner, cy + math.sin(angle) * inner
            x2, y2 = cx + math.cos(angle) * outer, cy + math.sin(angle) * outer
            pygame.draw.line(surf, accent, (x1, y1), (x2, y2), width)
    elif pattern == "swirl":
        pts = []
        steps = 14
        for s in range(steps + 1):
            t = s / steps
            a = t * 1.4 * 2 * math.pi
            rr = inner + (outer - inner) * t
            pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
        pygame.draw.lines(surf, accent, False, pts, width)


def draw_donut(surf, cx, cy, radius, flavor):
    if radius <= 1:
        return
    icing = flavor["icing"]
    hole = flavor["hole"]

    shadow = alpha_circle(radius * 1.02, (0, 0, 0), 70)
    surf.blit(shadow, (cx - shadow.get_width() / 2, cy - shadow.get_height() / 2 + 4))

    pygame.draw.circle(surf, icing, (int(cx), int(cy)), int(radius))
    pygame.draw.circle(surf, darken(icing, 40), (int(cx), int(cy)), int(radius),
                        max(1, int(radius * 0.07)))

    draw_topping(surf, cx, cy, radius, flavor["pattern"], flavor["accent"])

    hole_r = radius * 0.42
    pygame.draw.circle(surf, hole, (int(cx), int(cy)), int(hole_r))
    pygame.draw.circle(surf, darken(hole, 25), (int(cx), int(cy)), int(hole_r), 2)

    hl = alpha_circle(radius * 0.26, (255, 255, 255), 95)
    surf.blit(hl, (cx - radius * 0.4 - hl.get_width() / 2,
                   cy - radius * 0.4 - hl.get_height() / 2))


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
        if self.scale <= 0:
            return
        cx = self.x + CELL / 2
        cy = self.y + CELL / 2
        radius = (CELL / 2 - CANDY_PADDING) * self.scale
        draw_donut(surf, cx, cy, radius, FLAVORS[self.color])


# ---------------------------------------------------------------------------
# Particles & floating text
# ---------------------------------------------------------------------------

class Particle:
    def __init__(self, x, y, color):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(60, 170)
        self.x, self.y = x, y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed - 60
        self.color = color
        self.life = random.uniform(0.35, 0.6)
        self.age = 0.0
        self.radius = random.uniform(2, 4)

    def update(self, dt):
        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 320 * dt

    @property
    def alive(self):
        return self.age < self.life

    def draw(self, surf):
        t = self.age / self.life
        r = self.radius * (1 - t)
        if r <= 0.3:
            return
        alpha = int(255 * (1 - t))
        s = alpha_circle(r, self.color, alpha)
        surf.blit(s, (self.x - s.get_width() / 2, self.y - s.get_height() / 2))


class FloatingText:
    def __init__(self, text, x, y, color, delay=0.0, life=0.9):
        self.text = text
        self.x = x
        self.y = y
        self.color = color
        self.life = life
        self.age = -delay

    def update(self, dt):
        self.age += dt

    @property
    def alive(self):
        return self.age < self.life

    def draw(self, surf, font):
        if self.age < 0:
            return
        t = max(0.0, min(1.0, self.age / self.life))
        y = self.y - 30 * t
        alpha = int(255 * (1 - t))
        txt = font.render(self.text, True, self.color)
        txt.set_alpha(alpha)
        surf.blit(txt, txt.get_rect(center=(self.x, y)))


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
        self.displayed_score = 0.0
        self.best_score = load_best()
        self.moves_left = STARTING_MOVES
        self.game_over = None   # None, "won", "lost"
        self.paused = False
        self.anim_time = 0.0
        self.combo_flash_timer = 0.0
        self.last_event = "Click a donut, then an adjacent one to swap."

        self.pending_swap = None   # (r1, c1, r2, c2)
        self.swap_start = {}
        self.swap_is_trial = True
        self.popping_cells = []

        self.particles = []
        self.floating_texts = []

        self.bg = make_gradient(WIDTH, HEIGHT, BG_TOP, BG_BOTTOM)

        self.title_font = pygame.font.SysFont("arial", 25, bold=True)
        self.score_font = pygame.font.SysFont("arial", 18, bold=True)
        self.info_font = pygame.font.SysFont("arial", 14)
        self.button_font = pygame.font.SysFont("arial", 14, bold=True)
        self.float_font = pygame.font.SysFont("arial", 20, bold=True)
        self.combo_font = pygame.font.SysFont("arial", 17, bold=True)
        self.big_font = pygame.font.SysFont("arial", 32, bold=True)

        self.restart_rect = pygame.Rect(WIDTH - BUTTON_W - 12, 10, BUTTON_W, BUTTON_H)
        self.pause_rect = pygame.Rect(
            WIDTH - 2 * BUTTON_W - 20, 10, BUTTON_W, BUTTON_H)

    # -- input -------------------------------------------------------------

    def handle_click(self, pos):
        if self.state != Game.IDLE or self.game_over or self.paused:
            return
        x, y = pos
        col = (x - BOARD_LEFT) // CELL
        row = (y - BOARD_TOP) // CELL
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

    def toggle_pause(self):
        if not self.game_over:
            self.paused = not self.paused

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
        points = len(matched) * 10 * self.combo
        self.score += points

        colors_here = {self.grid[r][c].color for (r, c) in matched if self.grid[r][c]}
        if len(colors_here) == 1:
            flavor_name = FLAVORS[next(iter(colors_here))]["name"]
            msg = f"Matched {len(matched)} {flavor_name} donuts! +{points}"
        else:
            msg = f"Sweet combo! {len(matched)} donuts +{points}"
        if self.combo >= 2:
            msg += f"  (Combo x{self.combo})"
            self.combo_flash_timer = COMBO_BADGE_TIME
        self.last_event = msg

        cx = sum(cell_center(r, c)[0] for r, c in matched) / len(matched)
        cy = sum(cell_center(r, c)[1] for r, c in matched) / len(matched)
        self.floating_texts.append(FloatingText(f"+{points}", cx, cy, GOLD))
        if self.combo >= 2:
            self.floating_texts.append(
                FloatingText(f"Combo x{self.combo}!", cx, cy - 22, COMBO_COLOR, delay=0.12))

        for (r, c) in matched:
            candy = self.grid[r][c]
            if candy is not None:
                candy.popping = True
                candy.pop_t = 0.0
                px, py = cell_center(r, c)
                flavor = FLAVORS[candy.color]
                for _ in range(6):
                    self.particles.append(Particle(px, py, flavor["accent"]))

        self.popping_cells = list(matched)
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
                spawn_y = BOARD_TOP - (missing - i) * CELL
                candy = Candy(color, row, c, spawn_y=spawn_y)
                candy.vy = 0.0
                new_column[row] = candy
                write_row -= 1

            for r in range(ROWS):
                self.grid[r][c] = new_column[r]

        self.state = Game.FALLING
        self.timer = 0.0

    def finish_game(self, result):
        self.game_over = result
        if self.score > self.best_score:
            self.best_score = self.score
            save_best(self.best_score)

    # -- update --------------------------------------------------------------

    def update(self, dt):
        self.anim_time += dt
        self.displayed_score += (self.score - self.displayed_score) * min(1.0, dt * 8)
        if abs(self.score - self.displayed_score) < 0.5:
            self.displayed_score = self.score
        if self.combo_flash_timer > 0:
            self.combo_flash_timer = max(0.0, self.combo_flash_timer - dt)

        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.alive]

        for ft in self.floating_texts:
            ft.update(dt)
        self.floating_texts = [ft for ft in self.floating_texts if ft.alive]

        if self.game_over:
            return

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
        bounce = 1 + 0.15 * math.sin(min(1.0, t) * math.pi)
        for (r, c) in ((self.pending_swap[0], self.pending_swap[1]),
                       (self.pending_swap[2], self.pending_swap[3])):
            candy = self.grid[r][c]
            tx, ty = candy.target_xy()
            sx, sy = self.swap_start[(r, c)]
            candy.x = sx + (tx - sx) * eased
            candy.y = sy + (ty - sy) * eased
            candy.scale = bounce

        if t >= 1.0:
            for (r, c) in ((self.pending_swap[0], self.pending_swap[1]),
                           (self.pending_swap[2], self.pending_swap[3])):
                candy = self.grid[r][c]
                candy.x, candy.y = candy.target_xy()
                candy.scale = 1.0

            matched = find_matches(self.grid)
            if matched:
                if self.swap_is_trial:
                    self.moves_left = max(0, self.moves_left - 1)
                self.combo = 0
                self.begin_pop(matched)
            elif self.swap_is_trial:
                self.last_event = "No match there — try again!"
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
                return

            self.combo = 0
            if self.score >= LEVEL_TARGET:
                self.last_event = "Level complete! Great job!"
                self.finish_game("won")
            elif self.moves_left <= 0:
                self.last_event = "Out of moves — press Restart to try again."
                self.finish_game("lost")
            elif not has_valid_move(self.grid):
                self.reshuffle()
                self.last_event = "No moves left on the board — reshuffled!"
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
        surf.blit(self.bg, (0, 0))
        self._draw_header(surf)
        self._draw_board(surf)
        self._draw_footer(surf)

        for p in self.particles:
            p.draw(surf)
        for ft in self.floating_texts:
            ft.draw(surf, self.float_font)

        if self.combo_flash_timer > 0 and self.combo >= 2:
            alpha = 255 if self.combo_flash_timer > 0.3 else int(255 * (self.combo_flash_timer / 0.3))
            badge = self.combo_font.render(f"COMBO x{self.combo}!", True, COMBO_COLOR)
            badge.set_alpha(alpha)
            surf.blit(badge, badge.get_rect(center=(WIDTH / 2, 22)))

        if self.paused and not self.game_over:
            self._draw_overlay(surf, "Paused", MUTED_TEXT, "Click Pause or press P to resume")
        elif self.game_over == "won":
            self._draw_overlay(surf, "Level Complete!", WIN_COLOR,
                                f"Final score: {self.score}  •  Press Restart to play again")
        elif self.game_over == "lost":
            self._draw_overlay(surf, "Out of Moves", LOSE_COLOR,
                                f"Final score: {self.score}  •  Press Restart to try again")

    def _draw_header(self, surf):
        title = self.title_font.render("Donut Crush", True, TEXT_COLOR)
        surf.blit(title, (16, 10))

        self._draw_button(surf, self.pause_rect, "Resume" if self.paused else "Pause")
        self._draw_button(surf, self.restart_rect, "Restart")

        score_txt = self.score_font.render(
            f"Score: {int(self.displayed_score)}", True, TEXT_COLOR)
        surf.blit(score_txt, (16, 44))
        best_txt = self.info_font.render(f"Best: {self.best_score}", True, MUTED_TEXT)
        surf.blit(best_txt, (16 + score_txt.get_width() + 14, 49))

        moves_txt = self.score_font.render(f"Moves: {self.moves_left}", True, TEXT_COLOR)
        surf.blit(moves_txt, (WIDTH - 16 - moves_txt.get_width(), 44))

        bar_x, bar_y, bar_w, bar_h = 16, 78, WIDTH - 32, 10
        pygame.draw.rect(surf, BAR_BG, (bar_x, bar_y, bar_w, bar_h), border_radius=5)
        frac = min(1.0, self.score / LEVEL_TARGET)
        if frac > 0:
            pygame.draw.rect(surf, GOLD, (bar_x, bar_y, max(6, int(bar_w * frac)), bar_h),
                              border_radius=5)
        goal_txt = self.info_font.render(f"Goal: {LEVEL_TARGET}", True, MUTED_TEXT)
        surf.blit(goal_txt, (bar_x, bar_y - 15))

    def _draw_button(self, surf, rect, label):
        pygame.draw.rect(surf, BUTTON_COLOR, rect, border_radius=7)
        pygame.draw.rect(surf, BUTTON_BORDER, rect, 2, border_radius=7)
        txt = self.button_font.render(label, True, TEXT_COLOR)
        surf.blit(txt, txt.get_rect(center=rect.center))

    def _draw_board(self, surf):
        panel = pygame.Rect(BOARD_LEFT - 6, BOARD_TOP - 6, GRID_W + 12, GRID_H + 12)
        pygame.draw.rect(surf, PANEL_SHADOW, panel.move(0, 6), border_radius=20)
        pygame.draw.rect(surf, PANEL_COLOR, panel, border_radius=20)

        for r in range(ROWS):
            for c in range(COLS):
                x, y = cell_pos(r, c)
                color = GRID_COLOR_A if (r + c) % 2 == 0 else GRID_COLOR_B
                pygame.draw.rect(surf, color, (x + 1, y + 1, CELL - 2, CELL - 2),
                                  border_radius=10)

        if self.selected is not None and self.state == Game.IDLE:
            r, c = self.selected
            cx, cy = cell_center(r, c)
            pulse = 0.5 + 0.5 * math.sin(self.anim_time * 6)
            ring_r = CELL / 2 - 2 + pulse * 3
            ring = alpha_circle(ring_r, GOLD, 140 + int(60 * pulse))
            surf.blit(ring, (cx - ring.get_width() / 2, cy - ring.get_height() / 2))
            pygame.draw.circle(surf, GOLD, (int(cx), int(cy)), int(ring_r), 3)

        for r in range(ROWS):
            for c in range(COLS):
                candy = self.grid[r][c]
                if candy is None:
                    continue
                if candy.popping:
                    glow_r = (CELL / 2) * 1.6
                    glow_alpha = 180 * (1 - candy.pop_t)
                    if glow_alpha > 1:
                        glow = alpha_circle(glow_r, (255, 244, 200), glow_alpha)
                        cx = candy.x + CELL / 2
                        cy = candy.y + CELL / 2
                        surf.blit(glow, (cx - glow.get_width() / 2, cy - glow.get_height() / 2))
                candy.draw(surf)

    def _draw_footer(self, surf):
        y = BOARD_TOP + GRID_H + BOARD_PADDING + 6
        txt = self.info_font.render(self.last_event, True, MUTED_TEXT)
        surf.blit(txt, (16, y))

    def _draw_overlay(self, surf, title, title_color, subtitle):
        panel = pygame.Rect(BOARD_LEFT - 6, BOARD_TOP - 6, GRID_W + 12, GRID_H + 12)
        shade = pygame.Surface(panel.size, pygame.SRCALPHA)
        shade.fill((10, 9, 18, 200))
        surf.blit(shade, panel.topleft)

        title_txt = self.big_font.render(title, True, title_color)
        surf.blit(title_txt, title_txt.get_rect(center=(panel.centerx, panel.centery - 16)))
        sub_txt = self.info_font.render(subtitle, True, TEXT_COLOR)
        surf.blit(sub_txt, sub_txt.get_rect(center=(panel.centerx, panel.centery + 20)))


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    pygame.init()
    pygame.display.set_caption("Donut Crush")
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
                if game.restart_rect.collidepoint(event.pos):
                    game = Game()
                elif game.pause_rect.collidepoint(event.pos):
                    game.toggle_pause()
                else:
                    game.handle_click(event.pos)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    game = Game()
                elif event.key == pygame.K_p:
                    game.toggle_pause()

        if not game.paused:
            game.update(dt)
        else:
            # still let purely cosmetic timers settle so the frame looks stable
            pass
        game.draw(screen)
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
