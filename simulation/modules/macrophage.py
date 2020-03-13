from enum import IntEnum
import random

import attr
import numpy as np

from simulation.cell import CellData, CellList
from simulation.coordinates import Point, Voxel
from simulation.grid import RectangularGrid
from simulation.module import Module, ModuleState
from simulation.modules.geometry import TissueTypes
from simulation.modules.fungus import FungusCellData
from simulation.state import State

MAX_CONIDIA = 50
class MacrophageCellData(CellData):

    MACROPHAGE_FIELDS = [
        ('iteration', 'i4'),
        ('phagosome', (np.int32, (MAX_CONIDIA))),
    ]

    dtype = np.dtype(
        CellData.FIELDS + MACROPHAGE_FIELDS, align=True
    )  # type: ignore

    @classmethod
    def create_cell_tuple(
        cls, **kwargs,
    ) -> np.record:

        iteration = 0
        phagosome = np.empty(MAX_CONIDIA)
        phagosome.fill(-1)
        return CellData.create_cell_tuple(**kwargs) + (iteration, phagosome,)


@attr.s(kw_only=True, frozen=True, repr=False)
class MacrophageCellList(CellList):
    CellDataClass = MacrophageCellData

    def len_phagosome(self, index):
        cell = self[index]
        return len(np.argwhere(cell['phagosome'] != -1))

    def append_to_phagosome(self, index, pathogen_index, max_size):
        cell = self[index]
        index_to_append = MacrophageCellList.len_phagosome(self, index)
        if (
            index_to_append < MAX_CONIDIA
            and index_to_append < max_size
            and pathogen_index not in cell['phagosome']
        ):
            cell['phagosome'][index_to_append] = pathogen_index
            return True
        else:
            return False

    def remove_from_phagosome(self, index, pathogen_index):
        phagosome = self[index]['phagosome']
        if pathogen_index in phagosome:
            itemindex = np.argwhere(phagosome == pathogen_index)[0][0]
            size = MacrophageCellList.len_phagosome(self, index)
            if itemindex == size - 1:
                # full phagosome
                phagosome[itemindex] = -1
                return True
            else:
                phagosome[itemindex:-1] = phagosome[itemindex + 1 :]
                phagosome[-1] = -1
                return True
        else:
            return False

    def clear_all_phagosome(self, index):
        self[index]['phagosome'].fill(-1)

def cell_list_factory(self: 'MacrophageState'):
    return MacrophageCellList(grid=self.global_state.grid)


@attr.s(kw_only=True)
class MacrophageState(ModuleState):
    cells: MacrophageCellList = attr.ib(default=attr.Factory(cell_list_factory, takes_self=True))
    rec_r: float = 1.0
    p_rec_r: float = 1.0
    m_abs: float = 0.1 
    Mn: float =10.0 
    kill: float = 10.0
    m_det: float = 15
    rec_rate_ph:int = 2


class Macrophage(Module):
    name = 'macrophage'
    defaults = {
        'cells': '',
    }
    StateClass = MacrophageState

    def initialize(self, state: State):
        macrophage: MacrophageState = state.macrophage
        grid: RectangularGrid = state.grid
        tissue = state.geometry.lung_tissue

        macrophage.rec_r = self.config.getint('rec_r')
        macrophage.p_rec_r = self.config.getfloat('p_rec_r')
        macrophage.m_abs = self.config.getfloat('m_abs')
        macrophage.Mn = self.config.getfloat('Mn')
        macrophage.kill = self.config.getfloat('kill')
        macrophage.m_det = self.config.getfloat('m_det')
        macrophage.rec_rate_ph = self.config.getint('rec_rate_ph')


        macrophage.cells = MacrophageCellList(grid=grid)

        return state

    def advance(self, state: State, previous_time: float):

        recruit_new(state, previous_time)
        absorb_cytokines(state)
        produce_cytokines(state)
        move(state)
        damage_conidia(state, previous_time)

        return state


def recruit_new(state, time):
    macrophage: MacrophageState = state.macrophage
    m_cells = macrophage.cells
    tissue = state.geometry.lung_tissue
    grid = state.grid
    cyto = state.molecules.grid['m_cyto']

    num_reps = macrophage.rec_rate_ph # number of macrophages recruited per time step

    blood_index = np.argwhere(tissue == TissueTypes.BLOOD.value)
    blood_index = np.transpose(blood_index)
    mask = cyto[blood_index[2], blood_index[1], blood_index[0]] >= macrophage.rec_r
    blood_index = np.transpose(blood_index)
    cyto_index = blood_index[mask]
    np.random.shuffle(cyto_index)

    for i in range(0, num_reps):
        if(len(cyto_index) > 0):
            ii = random.randint(0, len(cyto_index) - 1)
            point = Point(
                x = grid.x[cyto_index[ii][2]], 
                y = grid.y[cyto_index[ii][1]], 
                z = grid.z[cyto_index[ii][0]])

            if(macrophage.p_rec_r > random.random()):
                m_cells.append(MacrophageCellData.create_cell(point=point))

            
def absorb_cytokines(state):
    macrophage: MacrophageState = state.macrophage
    m_cells = macrophage.cells
    cyto = state.molecules.grid['m_cyto']
    grid = state.grid

    for index in m_cells.alive():
        vox = grid.get_voxel(m_cells[index]['point'])
        x = vox.x
        y = vox.y
        z = vox.z
        cyto[z,y,x] = (1 - macrophage.m_abs) * cyto[z,y,x]

    return state


def produce_cytokines(state):
    macrophage: MacrophageState = state.macrophage
    m_cells = macrophage.cells
    fungus = state.fungus.cells

    tissue = state.geometry.lung_tissue
    grid = state.grid
    cyto = state.molecules.grid['n_cyto']

    for i in m_cells.alive():
        vox = grid.get_voxel(m_cells[i]['point'])

        hyphae_count = 0

        m_det = int(macrophage.m_det / 2)
        x_r = []
        y_r = []
        z_r = []

        for num in range(0, m_det + 1):
            x_r.append(num)
            y_r.append(num)
            z_r.append(num)

        for num in range(-1 * m_det, 0):
            x_r.append(num)
            y_r.append(num)
            z_r.append(num)

        for x in x_r:
            for y in y_r:
                for z in z_r:
                    zk = vox.z + z
                    yj = vox.y + y
                    xi = vox.x + x
                    if grid.is_valid_voxel(Voxel(x=xi, y=yj, z=zk)):
                        index_arr = fungus.get_cells_in_voxel(Voxel(x=xi, y=yj, z=zk))
                        for index in index_arr:
                            if(fungus[index]['form'] == FungusCellData.Form.HYPHAE):
                                hyphae_count +=1

        cyto[vox.z, vox.y, vox.x] = cyto[vox.z, vox.y, vox.x] + macrophage.Nn * hyphae_count

    return state


def move(state):
    macrophage = state.macrophage
    m_cells = macrophage.cells

    tissue = state.geometry.lung_tissue
    grid = state.grid
    cyto = state.molecules.grid['m_cyto']

    for cell_index in m_cells.alive():
        cell = m_cells[cell_index]
        vox = grid.get_voxel(cell['point'])

        p = np.zeros(shape=27)
        vox_list = []
        i = -1

        for x in [0, 1, -1]:
            for y in [0, 1, -1]:
                for z in [0, 1, -1]:
                    zk = vox.z + z
                    yj = vox.y + y
                    xi = vox.x + x
                    if grid.is_valid_voxel(Voxel(x=xi, y=yj, z=zk)):
                        vox_list.append([x, y, z])
                        i += 1
                        if cyto[zk, yj, xi] > macrophage.rec_r:
                            p[i] = cyto[zk, yj, xi]
                            

        indices = np.argwhere(p != 0)
        l = len(indices)
        if(l == 1):
            i = indices[0][0]
        elif(l >= 1):
            inds = np.argwhere(p == p[np.argmax(p)])
            np.random.shuffle(inds)
            i = inds[0][0]
        else:
            i = random.randint(0,27)

        cell['point'] = Point(
            x=grid.x[vox.x + vox_list[i][0]],
            y=grid.y[vox.y + vox_list[i][1]],
            z=grid.z[vox.z + vox_list[i][2]]
            )

        m_cells.update_voxel_index([cell_index])              

    return state


def damage_conidia(state, time):
    macrophage: MacrophageState = state.macrophage
    m_cells = macrophage.cells
    fungus = state.fungus.cells

    tissue = state.geometry.lung_tissue
    grid = state.grid
    cyto = state.molecules.grid['m_cyto']
    iron = state.molecules.grid['iron']

    for i in m_cells.alive():
        cell = m_cells[i]
        
        for index in cell['phagosome']:
            fungus[index]['health'] -= time / macrophage.kill
            fungus[index]['point'] = cell['point']
            fungus.update_voxel_index(index)

    return state
