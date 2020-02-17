from math import ceil

import attr
import click

from simulation.config import SimulationConfig
from simulation.geometry.generator import generate_geometry
from simulation.solver import advance, initialize
from simulation.state import State


@click.group()
def main():
    pass


@main.command()
@click.option(
    '--config',
    type=click.Path(exists=True),
    default='geometry.json',
    help='Path to a geometry config',
    show_default=True,
)
@click.option(
    '--output',
    type=click.Path(),
    default='geometry.hdf5',
    help='Name of the output file. Support .vtk and .hdf5',
    show_default=True,
)
@click.option(
    '--preview',
    is_flag=True,
    default=False,
    help='Preview geometry as VTK file',
    show_default=True,
)
def generate(config, output, preview):
    click.echo('generating geometry')
    generate_geometry(config, output, preview)
    pass


@main.command()
@click.argument('target_time', type=click.FLOAT, default=20)
@click.option(
    '--config',
    type=click.Path(exists=True),
    default='config.ini',
    help='Path to a simulation config',
    show_default=True,
)
def run(target_time, config):
    """Run a simulation."""
    config = SimulationConfig(config)
    total = ceil(target_time / config.getfloat('simulation', 'time_step'))

    attr.set_run_validators(config.getboolean('simulation', 'validate'))

    def get_time(x):
        if x is None:
            return '0'
        return '%.2f' % x.time

    state = initialize(State.create(config))
    with click.progressbar(
        advance(state, target_time),
        label='Running simulation',
        length=total,
        item_show_func=get_time,
    ) as bar:
        for _state in bar:
            pass

    state.save('simulation-final.pkl')


if __name__ == '__main__':
    run()
