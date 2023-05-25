"""Standard A* search with priority queue
Author: Ryo Yonetani
Affiliation: OSX
"""

from __future__ import annotations
from typing import List, NamedTuple, Optional

import numpy as np
import torch
from pqdict import pqdict


class AstarOutput(NamedTuple):
    """
    Output structure of A* search planners
    """

    histories: torch.tensor
    paths: torch.tensor
    intermediate_results: Optional[List[dict]] = None


def get_neighbor_indices(idx: int, H: int, W: int, D: int) -> np.array:
    """Get neighbor indices"""

    neighbor_indices = []
    if idx % W - 1 >= 0:
        neighbor_indices.append(idx - 1)
    if idx % W + 1 < W:
        neighbor_indices.append(idx + 1)
    if idx // W % H - 1 >= 0:
        neighbor_indices.append(idx - W)
    if idx // W % H + 1 < H:#
        neighbor_indices.append(idx + W)
    if (idx % W - 1 >= 0) & (idx // W % H - 1 >= 0):
        neighbor_indices.append(idx - W - 1)
    if (idx % W + 1 < W) & (idx // W % H - 1 >= 0):
        neighbor_indices.append(idx - W + 1)
    if (idx % W - 1 >= 0) & (idx // W % H + 1 < H):#
        neighbor_indices.append(idx + W - 1)
    if (idx % W + 1 < W) & (idx // W % H + 1 < H):#
        neighbor_indices.append(idx + W + 1)
    #3d additions
    #forwards and backwards
    if (idx + W * H < H * W * D):
        neighbor_indices.append(idx + W * H)
    if (idx - W * H >= 0):
        neighbor_indices.append(idx - W * H)
    #forwards l/r
    if (idx + W * H < H * W * D) & (idx % W - 1 >= 0):
        neighbor_indices.append(idx + W * H - 1)
    if (idx + W * H < H * W * D) & (idx % W + 1 < W):
        neighbor_indices.append(idx + W * H + 1)
    #forwards u/d
    if (idx + W * H < H * W * D) & (idx // W % H - 1 >= 0):
        neighbor_indices.append(idx + W * H - W)
    if (idx + W * H < H * W * D) & (idx // W % H + 1 < H):#
        neighbor_indices.append(idx + W * H + W)
    #forwards diagonals
    if (idx + W * H < H * W * D) & (idx % W - 1 >= 0) & (idx // W % H - 1 >= 0):
        neighbor_indices.append(idx + W * H - 1 - W)
    if (idx + W * H < H * W * D) & (idx % W + 1 < W) & (idx // W % H - 1 >= 0):
        neighbor_indices.append(idx + W * H + 1 - W)
    if (idx + W * H < H * W * D) & (idx % W - 1 >= 0) & (idx // W % H + 1 < H):#
        neighbor_indices.append(idx + W * H - 1 + W)
    if (idx + W * H < H * W * D) & (idx % W + 1 < W) & (idx // W % H + 1 < H):#
        neighbor_indices.append(idx + W * H + 1 + W)
    #backwards l/r
    if (idx - W * H >= 0) & (idx % W - 1 >= 0):
        neighbor_indices.append(idx - W * H - 1)
    if (idx - W * H >= 0) & (idx % W + 1 < W):
        neighbor_indices.append(idx - W * H + 1)
    #backwards u/d
    if (idx - W * H >= 0) & (idx // W % H - 1 >= 0):
        neighbor_indices.append(idx - W * H - W)
    if (idx - W * H >= 0) & (idx // W % H + 1 < H):#
        neighbor_indices.append(idx - W * H + W)
    #backwards diagonals
    if (idx - W * H >= 0) & (idx % W - 1 >= 0) & (idx // W % H - 1 >= 0):
        neighbor_indices.append(idx - W * H - 1 - W)
    if (idx - W * H >= 0) & (idx % W + 1 < W) & (idx // W % H - 1 >= 0):
        neighbor_indices.append(idx - W * H + 1 - W)
    if (idx - W * H >= 0) & (idx % W - 1 >= 0) & (idx // W % H + 1 < H):#
        neighbor_indices.append(idx - W * H - 1 + W)
    if (idx - W * H >= 0) & (idx % W + 1 < W) & (idx // W % H + 1 < H):#
        neighbor_indices.append(idx - W * H + 1 + W)
    return np.array(neighbor_indices)

def compute_chebyshev_distance(idx: int, goal_idx: int, W: int, H: int) -> float:
    """Compute chebyshev heuristic"""

    loc = np.array([idx % W, idx // W % H, idx // (W * H)])
    goal_loc = np.array([goal_idx % W, goal_idx // W % H, goal_idx // (W * H)])
    dxdydz = np.abs(loc - goal_loc)
    h = dxdydz.sum() - dxdydz.min()
    euc = np.sqrt(((loc - goal_loc) ** 2).sum())
    return h + 0.001 * euc


def get_history(close_list: list, H: int, W: int, D: int) -> np.array:
    """Get search history"""

    history = np.array([[idx % W, idx // W % H, idx // (W * H)] for idx in close_list.keys()])
    history_map = np.zeros((H, W, D))
    history_map[history[:, 1], history[:, 0], history[:, 2]] = 1

    return history_map


def backtrack(parent_list: list, goal_idx: int, H: int, W: int, D: int) -> np.array:
    """Backtrack to obtain path"""

    current_idx = goal_idx
    path = []
    while current_idx != None:
        path.append([current_idx % W, current_idx // W % H, current_idx // (W * H)])
        current_idx = parent_list[current_idx]
    path = np.array(path)
    path_map = np.zeros((H, W, D))
    path_map[path[:, 1], path[:, 0], path[:, 2]] = 1

    return path_map


def pq_astar(
    pred_costs: np.array,
    start_maps: np.array,
    goal_maps: np.array,
    map_designs: np.array,
    store_intermediate_results: bool = False,
    g_ratio: float = 0.5,
) -> AstarOutput:
    """Perform standard A* on a batch of problems"""

    assert (
        store_intermediate_results == False
    ), "store_intermediate_results = True is currently supported only for differentiable A*"

    pred_costs_np = pred_costs.detach().numpy()
    start_maps_np = start_maps.detach().numpy()
    goal_maps_np = goal_maps.detach().numpy()
    map_designs_np = map_designs.detach().numpy()
    histories = np.zeros_like(goal_maps_np)
    path_maps = np.zeros_like(goal_maps_np, np.int64)
    for n in range(len(pred_costs)):
        histories[n, 0], path_maps[n, 0] = solve_single(
            pred_costs_np[n, 0],
            start_maps_np[n, 0],
            goal_maps_np[n, 0],
            map_designs_np[n, 0],
            g_ratio,
        )

    return AstarOutput(torch.tensor(histories), torch.tensor(path_maps))


def solve_single(
    pred_cost: np.array,
    start_map: np.array,
    goal_map: np.array,
    map_design: np.array,
    g_ratio: float = 0.5,
) -> list:
    """Solve a single problem"""

    H, W, D = map_design.shape
    start_idx = np.argwhere(start_map.flatten('F')).item()
    goal_idx = np.argwhere(goal_map.flatten('F')).item()
    map_design_vct = map_design.flatten('F')
    pred_cost_vct = pred_cost.flatten('F')
    open_list = pqdict()
    close_list = pqdict()
    open_list.additem(start_idx, 0)
    parent_list = dict()
    parent_list[start_idx] = None

    #print(start_idx)
    #print(goal_idx)

    num_steps = 0
    while goal_idx not in close_list:
        if len(open_list) == 0:
            print("goal not found")
            return np.zeros_like(goal_map), np.zeros_like(goal_map)
        num_steps += 1
        idx_selected, f_selected = open_list.popitem()
        #print(idx_selected)
        close_list.additem(idx_selected, f_selected)
        for idx_nei in get_neighbor_indices(idx_selected, H, W, D):

            #if map_design_vct[idx_nei] == 1:
                f_new = (
                    f_selected
                    - (1 - g_ratio)
                    * compute_chebyshev_distance(idx_selected, goal_idx, W, H)
                    + g_ratio * pred_cost_vct[idx_nei]
                    + (1 - g_ratio) * compute_chebyshev_distance(idx_nei, goal_idx, W, H)
                )

                # conditions for the nodes not yet in the open list nor closed list
                cond = (idx_nei not in open_list) & (idx_nei not in close_list)

                # condition for the nodes already in the open list but with larger f value
                if idx_nei in open_list:
                    cond = cond | (open_list[idx_nei] > f_new)

                if cond:
                    try:
                        open_list.additem(idx_nei, f_new)
                    except:
                        open_list[idx_nei] = f_new
                    parent_list[idx_nei] = idx_selected

    history_map = get_history(close_list, H, W, D)
    path_map = backtrack(parent_list, goal_idx, H, W, D)
    return history_map, path_map
