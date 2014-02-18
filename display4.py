import code
from datetime import datetime, timedelta
import pdb
import signal

from freezegun import freeze_time
import pygame
from pygame.locals import K_1, K_2, K_3, K_4, K_5, K_6, K_7, K_8, K_9
from pygame.locals import K_SPACE, KEYDOWN, MOUSEBUTTONUP, QUIT

from gauge import Gauge


def later(seconds):
    return datetime.utcnow() + timedelta(0, seconds)


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
    bar_height = 5

    def __init__(self, gauge):
        self.gauge = gauge
        self.surf = pygame.Surface(self.size)

    def render(self, at):
        # draw bg
        surf = self.surf
        surf.fill(BASE3)
        bg = pygame.Surface((self.size[0], self.bar_height))
        bg.fill(BASE2)
        surf.blit(bg, (0, 0))
        # draw bar
        ratio = self.gauge.current(at) / float(self.gauge.max)
        if ratio > 1:
            bar_color = BLUE
            ratio = 1
        elif ratio == 1:
            bar_color = CYAN
        elif ratio > 0.3:
            bar_color = GREEN
        elif ratio > 0.1:
            bar_color = YELLOW
        elif ratio > 0:
            bar_color = ORANGE
        if ratio > 0:
            bar = pygame.Surface((int(self.size[0] * ratio), self.bar_height))
            bar.fill(bar_color)
            surf.blit(bar, (0, 0))
        # write current state
        text = font.render('{0}/{1}'.format(
            int(self.gauge.current(at)), self.gauge.max), True, BASE1)
        surf.blit(text, (10, font.get_height() / 2))
        # write time recover in
        speed = self.gauge.velocity(at)
        if speed != 0:
            text = font.render('{0:+.2f}/s'.format(speed), True,
                               GREEN if speed > 0 else RED)
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


class GaugeGraph(object):

    size = (300, 100)

    def __init__(self, gauge):
        self.gauge = gauge
        self.surf = pygame.Surface(self.size)

    def render(self, at):
        # draw bg
        surf = self.surf
        surf.fill(BASE3)
        bg = pygame.Surface(self.size)
        bg.fill(BASE2)
        surf.blit(bg, (0, 0))
        # draw axes
        col = self.size[0] / 60
        past = 10
        left = past * col
        pygame.draw.line(surf, BASE3, (left, 0), (left, self.size[1]), 2)
        pygame.draw.line(
            surf, BASE3, (0, 0.25 * self.size[1]),
            (self.size[0], 0.25 * self.size[1]))
        pygame.draw.line(
            surf, BASE3, (0, 0.75 * self.size[1]),
            (self.size[0], 0.75 * self.size[1]))
        # gauge values
        points = []
        real_points = []
        x = 0
        at = at.replace(microsecond=0)
        #d = at.microsecond / 1000000.
        while True:
            left = x * col
            if left > self.size[0]:
                break
            value = self.gauge.current(at + timedelta(0, x - past))
            ratio = (1 - value / float(self.gauge.max)) / 2 + 0.25
            points.append((left, int(ratio * self.size[1])))
            x += 1
        pygame.draw.lines(surf, RED, False, points)
        return surf


def main(gauge, fps=30, padding=0):
    def editor(signo, frame):
        def add_linear_momentum(delta, until=None, interval=1):
            if until is not None:
                until = later(until)
            since = datetime.utcnow()
            gauge.add_momentum(Linear(delta, interval), since, until)
        code.interact(local={'g': gauge, 'm': add_linear_momentum})
    signal.signal(signal.SIGQUIT, editor)
    disp = GaugeDisplay(gauge)
    graph = GaugeGraph(gauge)
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
                elif e.type == KEYDOWN:
                    pressed = pygame.key.get_pressed()
                    if pressed[K_1]:
                        gauge.inertia(-2, at, later(1))
                    elif pressed[K_2]:
                        gauge.inertia(-2, at, later(2))
                    elif pressed[K_3]:
                        gauge.inertia(-2, at, later(3))
                    elif pressed[K_4]:
                        gauge.inertia(-2, at, later(4))
                    elif pressed[K_5]:
                        gauge.inertia(-2, at, later(5))
                    elif pressed[K_6]:
                        gauge.inertia(-2, at, later(6))
                    elif pressed[K_7]:
                        gauge.inertia(-2, at, later(7))
                    elif pressed[K_8]:
                        gauge.inertia(-2, at, later(8))
                    elif pressed[K_9]:
                        gauge.inertia(-2, at, later(9))
                    elif pressed[K_SPACE]:
                        with freeze_time(at):
                            pdb.set_trace()
                elif e.type == MOUSEBUTTONUP and e.button == 3:
                    do = Gauge.incr
                elif e.type == MOUSEBUTTONUP and e.button == 1:
                    do = Gauge.decr
            # draw gauges
            screen.fill(BASE3)
            surf = None
            if do is not None:
                try:
                    do(disp.gauge, 1, False, at=at)
                except ValueError:
                    surf = disp.surf
                    surf.fill(RED)
            if surf is None:
                surf = disp.render(at)
            left = (screen.get_width() - surf.get_width()) / 2
            screen.blit(surf, (left, 20))
            graph_surf = graph.render(at)
            screen.blit(graph_surf, (left - 50, 60))
            # end of loop
            first = False
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    g = Gauge(0)
    g.inertia(+1)
    main(g, 5)
