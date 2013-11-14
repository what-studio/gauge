from datetime import datetime
import math
import pdb
import sys

import pygame
from pygame.locals import MOUSEBUTTONUP, QUIT

from gauge import Discrete, Gauge, Linear
from test import Energy, Life, define_gauge


SCREEN_SIZE = (300, 200)


# solarized
BASE03 = (0, 43, 54)
BASE02 = (7, 54, 66)
BASE01 = (88, 110, 117)
BASE00 = (101, 123, 131)
BASE0 = (131, 148, 150)
BASE1 = (147, 161, 161)
BASE2 = (238, 232, 213)
BASE3 = (253, 246, 227)
YELLOW = (181, 137, 0)
ORANGE = (203, 75, 22)
RED = (220, 50, 47)
MAGENTA = (211, 54, 130)
VIOLET = (108, 113, 196)
BLUE = (38, 139, 210)
CYAN = (42, 161, 152)
GREEN = (133, 153, 0)


# pygame stuffs
pygame.init()
pygame.display.set_mode(SCREEN_SIZE)
screen = pygame.display.get_surface()
clock = pygame.time.Clock()
font = pygame.font.SysFont('Consolas', 20)


class GaugeDisplay(object):

    size = (200, 30)

    def __init__(self, gauge):
        self.gauge = gauge
        self.surf = pygame.Surface(self.size)

    def render(self, at):
        # draw bg
        surf = self.surf
        surf.fill(BASE2)
        # draw bar
        ratio = self.gauge.current(at) / float(self.gauge.max)
        if ratio > 1:
            bar_color = BLUE
            text_colors = (BASE3, BASE3)
            ratio = 1
        elif ratio == 1:
            bar_color = CYAN
            text_colors = (BASE3, BASE3)
        elif ratio > 0.3:
            bar_color = GREEN
            text_colors = (BASE3, BASE1)
        elif ratio > 0.1:
            bar_color = YELLOW
            text_colors = (BASE3, BASE1)
        elif ratio > 0:
            bar_color = ORANGE
            text_colors = (BASE3, BASE1)
        elif ratio == 0:
            text_colors = (BASE1, BASE1)
        else:
            text_colors = (RED, BASE1)
        if ratio > 0:
            bar = pygame.Surface((int(self.size[0] * ratio), self.size[1]))
            bar.fill(bar_color)
            surf.blit(bar, (0, 0))
        # write current state
        text = font.render(
            '{0}/{1}'.format(int(self.gauge.current(at)), self.gauge.max),
            True, text_colors[0])
        surf.blit(text, (10, font.get_height() / 2))
        # write time recover in
        dps = 0
        effects = False
        for momentum in self.gauge.momenta:
            effects = effects or momentum.effects(self.gauge, at)
            dps += float(momentum.delta) / momentum.interval
        timedelta = self.gauge.time_passed(at)
        interval = 1 / dps
        move_in = interval - timedelta.total_seconds() % interval
        if effects and move_in:
            text = font.render('{0:.1f}'.format(move_in), True, text_colors[1])
            surf.blit(text, (surf.get_width() - text.get_width() - 10,
                             font.get_height() / 2))
        '''
        try:
            move_in = self.gauge.momenta[0].move_in(self.gauge, at)
        except (AttributeError, IndexError):
            pass
        else:
            if move_in:
                move_in = math.ceil(move_in)
                text = font.render('{0:02.0f}:{1:02.0f}'.format(
                    move_in / 60, move_in % 60), True, text_colors[1])
                surf.blit(text, (surf.get_width() - text.get_width() - 10,
                                 font.get_height() / 2))
        '''
        return surf


def main(gauges, fps=30, padding=10):
    gauge_displays = [GaugeDisplay(gauge) for gauge in gauges]
    first = True
    try:
        while True:
            if not first:
                # sleep since second frame
                pygame.display.update()
                clock.tick(fps)
            at = datetime.utcnow()
            # process user inputs
            do = None
            for e in pygame.event.get():
                if e.type == QUIT:
                    pygame.display.quit()
                    raise KeyboardInterrupt
                elif e.type == MOUSEBUTTONUP and e.button == 3:
                    do = Gauge.incr
                elif e.type == MOUSEBUTTONUP and e.button == 1:
                    do = Gauge.decr
            # draw gauges
            screen.fill(BASE3)
            for x, disp in enumerate(gauge_displays):
                surf = None
                if do is not None:
                    try:
                        do(disp.gauge, 1, False, at=at)
                    except ValueError:
                        surf = disp.surf
                        surf.fill(RED)
                if surf is None:
                    surf = disp.render(at)
                #print disp.gauge.current(at), disp.gauge.stuffs(at)
                left = (screen.get_width() - surf.get_width()) / 2
                max = int(
                    screen.get_height() / 2 +
                    (surf.get_height() + padding) *
                    (x - len(gauge_displays) / 2.))
                screen.blit(surf, (left, max))
            first = False
    except KeyboardInterrupt:
        pass
    except:
        import traceback
        traceback.print_exc()
        pdb.post_mortem()


if __name__ == '__main__':
    Gauge10 = define_gauge('Gauge10', 10, value_type=float)
    g1 = Gauge10(8)
    g2 = Gauge10(8)
    g3 = Gauge10(0)
    g1.add_momentum(Discrete(+1, 3))
    #g2.add_momentum(Linear(+1, 2))
    g2.add_momentum(Discrete(-1, 3))
    g3.add_momentum(Linear(-1, 5))
    g3.add_momentum(Linear(-1, 30))
    main([g1, g2, g3], 5)
