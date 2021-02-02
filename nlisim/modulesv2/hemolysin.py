import attr
from attr import attrib, attrs
import numpy as np

from nlisim.coordinates import Voxel
from nlisim.grid import RectangularGrid
from nlisim.module import ModuleState
from nlisim.modulesv2.afumigatus import AfumigatusCellData, AfumigatusState, FungalForm
from nlisim.modulesv2.geometry import GeometryState
from nlisim.modulesv2.molecule import MoleculeModel
from nlisim.modulesv2.molecules import MoleculesState
from nlisim.state import State
from nlisim.util import turnover_rate


def molecule_grid_factory(self: 'HemolysinState') -> np.ndarray:
    return np.zeros(shape=self.global_state.grid.shape, dtype=float)


@attrs(kw_only=True, repr=False)
class HemolysinState(ModuleState):
    grid: np.ndarray = attrib(default=attr.Factory(molecule_grid_factory, takes_self=True))
    hemolysin_qtty: float


class Hemolysin(MoleculeModel):
    """Hemolysin"""

    name = 'hemolysin'
    StateClass = HemolysinState

    def initialize(self, state: State) -> State:
        hemolysin: HemolysinState = state.hemolysin
        geometry: GeometryState = state.geometry
        voxel_volume = geometry.voxel_volume

        # config file values
        hemolysin.hemolysin_qtty = self.config.getfloat('hemolysin_qtty')
        # constant from setting rate of secretion rate to 1

        # computed values (none)

        return state

    def advance(self, state: State, previous_time: float) -> State:
        """Advance the state by a single time step."""
        hemolysin: HemolysinState = state.hemolysin
        molecules: MoleculesState = state.molecules
        afumigatus: AfumigatusState = state.afumigatus
        grid: RectangularGrid = state.grid

        # fungus releases hemolysin
        for afumigatus_cell_index in afumigatus.cells.alive():
            afumigatus_cell: AfumigatusCellData = afumigatus.cells[afumigatus_cell_index]
            if afumigatus_cell['status'] == FungalForm.HYPHAE:
                afumigatus_cell_voxel: Voxel = grid.get_voxel(afumigatus_cell['point'])
                hemolysin.grid[tuple(afumigatus_cell_voxel)] += hemolysin.hemolysin_qtty

        # Degrade Hemolysin
        hemolysin.grid *= turnover_rate(x_mol=hemolysin.grid,
                                        x_system_mol=0.0,
                                        turnover_rate=molecules.turnover_rate,
                                        rel_cyt_bind_unit_t=molecules.rel_cyt_bind_unit_t)

        return state
