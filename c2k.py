import datetime
from time import sleep

import sdl2.ext
import sdl2.sdlgfx
import sys

from sdl2.ext import SDLError
from screeninfo import get_monitors

row_lights = {
    0: 'big_red',
    1: 'big_green',
    2: 'small_yellow',
    3: 'small_red',
    4: 'small_green'
}
lights = ['big_red', 'big_green', 'small_yellow', 'small_red', 'small_green', 'big_grey', 'small_grey']


class SoftwareRenderer(sdl2.ext.SoftwareSpriteRenderSystem):

    def __init__(self, window):
        super(SoftwareRenderer, self).__init__(window)

    def render(self, components, x=None, y=None):
        sdl2.ext.fill(self.surface, sdl2.ext.Color(0, 0, 0))
        super(SoftwareRenderer, self).render(components)


def get_scaled_surface(surface, factor=1):
    return sdl2.sdlgfx.rotozoomSurface(surface, 0, factor, 1).contents


class Light(sdl2.ext.Entity):
    def __init__(self, world, sprite, posx=0, posy=0, depth=-1):
        self.sprite = sprite
        self.sprite.position = posx, posy
        self.sprite.depth = depth


class Calculator:

    width = 640
    height = 480
    lights = {name: (0, 0) for name in lights}
    light_size = 0
    light_size_factor = {
        'big': None,
        'small': None
    }
    positions = {index: [] for index in range(5)}
    last_tick_values = {index: None for index in range(5)}

    def set_screen_size(self, width, height):
        self.width = width
        self.height = height

    def get_screen_size(self):
        return self.width, self.height

    def add_light(self, name, width, height):

        # set on first call only
        if 0 == self.light_size:
            self.light_size = width

        if width != height:
            raise SDLError('width and height of light image must be equal')

        # check for different size
        if width != self.light_size:
            raise SDLError('all light images must have the same resolution')

        self.lights[name] = width

    def get_light_scale(self, name):

        default_size = 192

        if 'big' in name:
            if self.light_size_factor.get('big') is None:
                self.light_size_factor['big'] = self.lights[name] / default_size

            return self.light_size_factor.get('big')
        else:
            if self.light_size_factor.get('small') is None:
                self.light_size_factor['small'] = self.lights[name] / default_size / 2

            return self.light_size_factor.get('small')

    def calculate(self):

        # amount of lights per row
        _lights = {
            0: 4,
            1: 4,
            2: 11,
            3: 4,
            4: 1
        }

        # calculate vertical positions (rows)
        row_height = self.height / 5
        for row_num, num_lights in _lights.items():

            # calculate horizontal positions (columns)
            column_width = self.width / num_lights

            for col_num in range(num_lights):

                x = int((col_num + 1) * column_width) - int(column_width / 2)
                y = int((row_num + 1) * row_height) - int(row_height / 2)

                # special condition for 5-minute lights
                if row_num == 2:
                    if col_num in [3, 7, 11]:
                        y -= 50  # FIXME
                    elif col_num in [1, 5, 9]:
                        y += 50  # FIXME

                self.positions[row_num].append((x, y))

    def correct_image_position(self, position, type):
        return (
            position[0] - int(self.light_size * self.light_size_factor.get(type) // 2),
            position[1] - int(self.light_size * self.light_size_factor.get(type) // 2)
        )

    def get_big_grey_positions(self):
        return [self.correct_image_position(pos, 'big') for pos in self.positions[0] + self.positions[1]]

    def get_small_grey_positions(self):
        return [self.correct_image_position(pos, 'small') for pos in self.positions[2] + self.positions[3] + self.positions[4]]

    def get_changes(self):

        now = datetime.datetime.now()
        tick_values = {
            0: now.hour // 5,
            1: now.hour % 5,
            2: now.minute // 5,
            3: now.minute % 5,
            4: now.second % 2
        }
        changes = {index: {'changed': False, 'positions': []} for index in range(5)}

        for index, value in tick_values.items():

            if value != self.last_tick_values[index] or self.last_tick_values[index] is None:

                self.last_tick_values[index] = value

                changes[index]['changed'] = True
                changes[index]['positions'] = [
                    self.correct_image_position(pos, 'big' if index < 2 else 'small') for pos in self.positions[index][0:value]
                ]

        return changes


def run():

    # get monitors (used to get desktop resolution)
    monitors = get_monitors()
    if len(monitors) > 1:
        raise SDLError('only single screen supported')

    # init calculator (used for positions)
    calculator = Calculator()
    calculator.set_screen_size(monitors[0].width, monitors[0].height)

    # init main window
    sdl2.ext.init()
    window = sdl2.ext.Window(
        'c2k',
        size=calculator.get_screen_size(),
        position=(0, 1),  # weird bug on i3?
        flags=sdl2.SDL_WINDOW_BORDERLESS
    )
    window.show()

    # init renderer (software)
    sprite_renderer = SoftwareRenderer(window)
    factory = sdl2.ext.SpriteFactory(sdl2.ext.SOFTWARE)

    # init world an add renderer
    world = sdl2.ext.World()
    world.add_system(sprite_renderer)

    # dict of all lights as sprite in correct size
    light_sprites = {name: None for name in lights}

    for sprite_name in lights:

        # load surface and add resolution to calculator
        surface = sdl2.ext.load_image('resources/{}.png'.format(sprite_name))
        calculator.add_light(sprite_name, surface.w, surface.h)

        # scale the surface
        light_sprites[sprite_name] = get_scaled_surface(surface, calculator.get_light_scale(sprite_name))

    # calculate light positions
    calculator.calculate()

    # draw big grey lights
    for pos in calculator.get_big_grey_positions():
        Light(world, factory.from_surface(light_sprites.get('big_grey')), pos[0], pos[1], -2)

    # draw small grey lights
    for pos in calculator.get_small_grey_positions():
        Light(world, factory.from_surface(light_sprites.get('small_grey')), pos[0], pos[1], -2)

    _lights = {index: set() for index in range(5)}

    while True:

        # listen for exit event
        events = sdl2.ext.get_events()
        for event in events:
            if event.type == sdl2.SDL_QUIT:
                sys.exit(0)

        changes = calculator.get_changes()
        for index, change in changes.items():

            if change['changed']:

                for entity in _lights[index]:
                    world.delete(entity)

                _lights[index] = set()

                for position in change['positions']:
                    _lights[index].add(
                        Light(
                            world,
                            factory.from_surface(light_sprites.get(row_lights[index])),
                            position[0],
                            position[1]
                        )
                    )

        world.process()
        sleep(1)


if __name__ == "__main__":
    sys.exit(run())
