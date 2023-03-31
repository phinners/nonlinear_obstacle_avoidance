"""
Create 'Arch'-Obstacle which might be often used
"""
from dataclasses import dataclass, field
from typing import Optional, Iterator
import numpy as np
import numpy.typing as npt

import networkx as nx

from vartools.states import Pose
from vartools.dynamical_systems import LinearSystem

from dynamic_obstacle_avoidance.obstacles import Obstacle
from dynamic_obstacle_avoidance.obstacles import CuboidXd as Cuboid

from nonlinear_avoidance.multi_obstacle_avoider import MultiObstacleAvoider
from nonlinear_avoidance.multi_obstacle_avoider import HierarchyObstacle
from nonlinear_avoidance.nonlinear_rotation_avoider import (
    SingularityConvergenceDynamics,
)
from nonlinear_avoidance.dynamics.projected_rotation_dynamics import (
    ProjectedRotationDynamics,
)


@dataclass(slots=True)
class MultiObstacleContainer:
    _obstacle_list: list[HierarchyObstacle] = field(default_factory=list)

    def get_gamma(self, position: np.ndarray, in_global_frame: bool = True) -> float:
        if not in_global_frame:
            raise NotImplementedError()
        gammas = np.zeros(len(self._obstacle_list))
        for oo, obs in enumerate(self._obstacle_list):
            gammas[oo] = obs.get_gamma(position, in_global_frame=True)

        return min(gammas)

    def append(self, obstacle: HierarchyObstacle) -> None:
        self._obstacle_list.append(obstacle)

    def __iter__(self) -> Iterator[int]:
        return iter(self._obstacle_list)

    def __len__(self) -> int:
        return len(self._obstacle_list)

    def is_in_free_space(
        self, position: np.ndarray, in_global_frame: bool = True
    ) -> bool:
        if not in_global_frame:
            raise NotImplementedError()
        for obs in self:
            if obs.is_in_free_space(position, in_global_frame=True):
                continue
            return False

        return True


class BlockArchObstacle:
    def __init__(self, wall_width: float, axes_length: np.ndarray, pose: Pose):
        self.dimension = 2

        self.pose = pose
        self.axes_length = axes_length
        self._graph = nx.DiGraph()

        self._local_poses = []
        self._obstacle_list = []

        self._root_idx = 0
        self.set_root(
            Cuboid(
                axes_length=np.array([wall_width, axes_length[1]]),
                pose=Pose(np.zeros(self.dimension), orientation=0.0),
            ),
        )

        delta_pos = (axes_length - wall_width) * 0.5
        self.add_component(
            Cuboid(
                axes_length=np.array([axes_length[0], wall_width]),
                pose=Pose(delta_pos, orientation=0.0),
            ),
            reference_position=np.array([-delta_pos[0], 0.0]),
            parent_ind=0,
        )

        self.add_component(
            Cuboid(
                axes_length=np.array([axes_length[0], wall_width]),
                pose=Pose(np.array([delta_pos[0], -delta_pos[1]]), orientation=0.0),
            ),
            reference_position=np.array([-delta_pos[0], 0.0]),
            parent_ind=0,
        )

    @property
    def n_components(self) -> int:
        return len(self._obstacle_list)

    @property
    def root_idx(self) -> int:
        return self._root_idx

    def get_gamma(self, position, in_global_frame: bool = True):
        if not in_global_frame:
            position = self.pose.transform_pose_from_relative(position)

        gammas = [
            obs.get_gamma(position, in_global_frame=True) for obs in self._obstacle_list
        ]
        return np.min(gammas)

    def get_parent_idx(self, idx_obs: int) -> Optional[int]:
        if idx_obs == self.root_idx:
            return None
        else:
            try:
                return list(self._graph.predecessors(idx_obs))[0]
            except:
                breakpoint()

    def get_component(self, idx_obs: int) -> Obstacle:
        return self._obstacle_list[idx_obs]

    def set_root(self, obstacle: Obstacle) -> None:
        self._local_poses.append(obstacle.pose)
        obstacle.pose = self.pose.transform_pose_from_relative(self._local_poses[-1])

        self._obstacle_list.append(obstacle)
        obs_id = 0  # Obstacle ID
        self._graph.add_node(obs_id, references_children=[], indeces_children=[])

    def add_component(
        self,
        obstacle: Obstacle,
        reference_position: npt.ArrayLike,
        parent_ind: int,
    ) -> None:
        """Create and add an obstacle container in the local frame of reference."""
        reference_position = np.array(reference_position)
        obstacle.set_reference_point(reference_position, in_global_frame=False)

        new_id = len(self._obstacle_list)
        # Put obstacle to 'global' frame, but store local pose
        self._local_poses.append(obstacle.pose)
        obstacle.pose = self.pose.transform_pose_from_relative(self._local_poses[-1])
        self._obstacle_list.append(obstacle)

        self._graph.add_node(
            new_id,
            local_reference=reference_position,
            indeces_children=[],
            references_children=[],
        )
        # self._graph.nodes[parent_ind]["references_children"].append(
        #     self._local_poses[-1]
        # )
        self._graph.nodes[parent_ind]["indeces_children"].append(new_id)
        self._graph.add_edge(parent_ind, new_id)

    def update_obstacles(self, delta_time):
        # Update all positions of the moved obstacles
        for pose, obs in zip(self._local_poses, self._obstacle_list):
            obs.shape = self.pose.transform_pose_from_relative(pose)


def create_arch_obstacle(
    wall_width: float, axes_length: np.ndarray, pose: Pose
) -> BlockArchObstacle:
    multi_block = BlockArchObstacle(
        wall_width=wall_width,
        axes_length=axes_length,
        pose=pose,
    )
    return multi_block


def test_2d_blocky_arch(visualize=False):
    multi_block = BlockArchObstacle(
        wall_width=0.4,
        axes_length=np.array([3.0, 5]),
        pose=Pose(np.array([0.0, 0]), orientation=0.0),
    )

    multibstacle_avoider = MultiObstacleAvoider(obstacle=multi_block)

    velocity = np.array([-1.0, 0])
    linearized_velociy = np.array([-1.0, 0])

    if visualize:
        import matplotlib.pyplot as plt
        from dynamic_obstacle_avoidance.visualization import plot_obstacle_dynamics
        from dynamic_obstacle_avoidance.visualization import plot_obstacles

        fig, ax = plt.subplots(figsize=(6, 5))

        x_lim = [-5, 5.0]
        y_lim = [-5, 5.0]
        n_grid = 20

        plot_obstacles(
            obstacle_container=multi_block._obstacle_list,
            ax=ax,
            x_lim=x_lim,
            y_lim=y_lim,
            draw_reference=True,
            noTicks=False,
            # reference_point_number=True,
            show_obstacle_number=True,
            # ** kwargs,
        )

        plot_obstacle_dynamics(
            obstacle_container=[],
            collision_check_functor=lambda x: (
                multi_block.get_gamma(x, in_global_frame=True) <= 1
            ),
            # obstacle_container=triple_ellipses._obstacle_list,
            dynamics=lambda x: multibstacle_avoider.get_tangent_direction(
                x, velocity, linearized_velociy
            ),
            x_lim=x_lim,
            y_lim=y_lim,
            ax=ax,
            do_quiver=True,
            # do_quiver=False,
            n_grid=n_grid,
            show_ticks=True,
            # vectorfield_color=vf_color,
        )

    # Test positions [which has been prone to a rounding error]
    position = np.array([4, 1.6])
    averaged_direction = multibstacle_avoider.get_tangent_direction(
        position, velocity, linearized_velociy
    )
    assert averaged_direction[0] < 0, "Velocity is not going left."
    assert averaged_direction[1] > 0, "Avoiding upwards expected."


def test_2d_blocky_arch_rotated(visualize=False):
    multi_block = BlockArchObstacle(
        wall_width=0.4,
        axes_length=np.array([3.0, 5]),
        pose=Pose(np.array([-1.0, -0.4]), orientation=-45 * np.pi / 180.0),
    )

    multibstacle_avoider = MultiObstacleAvoider(obstacle=multi_block)

    velocity = np.array([-1.0, 0])
    linearized_velociy = np.array([-1.0, 0])

    if visualize:
        import matplotlib.pyplot as plt
        from dynamic_obstacle_avoidance.visualization import plot_obstacle_dynamics
        from dynamic_obstacle_avoidance.visualization import plot_obstacles

        fig, ax = plt.subplots(figsize=(6, 5))

        x_lim = [-5, 5.0]
        y_lim = [-5, 5.0]
        n_grid = 20

        plot_obstacles(
            obstacle_container=multi_block._obstacle_list,
            ax=ax,
            x_lim=x_lim,
            y_lim=y_lim,
            draw_reference=True,
            noTicks=False,
            # reference_point_number=True,
            show_obstacle_number=True,
            # ** kwargs,
        )

        plot_obstacle_dynamics(
            obstacle_container=[],
            collision_check_functor=lambda x: (
                multi_block.get_gamma(x, in_global_frame=True) <= 1
            ),
            # obstacle_container=triple_ellipses._obstacle_list,
            dynamics=lambda x: multibstacle_avoider.get_tangent_direction(
                x, velocity, linearized_velociy
            ),
            x_lim=x_lim,
            y_lim=y_lim,
            ax=ax,
            do_quiver=True,
            # do_quiver=False,
            n_grid=n_grid,
            show_ticks=True,
            # vectorfield_color=vf_color,
        )

    print("Doing")
    # Test positions [which has been prone to a rounding error]
    position = np.array([0.25, -3.99])
    averaged_direction = multibstacle_avoider.get_tangent_direction(
        position, velocity, linearized_velociy
    )
    # Evaluate gamma
    assert averaged_direction[0] < 0, "Velocity is not going left."
    assert averaged_direction[1] < 0, "Avoiding downwards expected."

    # On the surface of a leg
    position = np.array([-1.35486, -3.01399])
    averaged_direction = multibstacle_avoider.get_tangent_direction(
        position, velocity, linearized_velociy
    )
    assert averaged_direction[0] > 0, "Expected to go backwards"
    assert np.isclose(
        averaged_direction[0], -averaged_direction[1], atol=1e-1
    ), "Expected to go backwards"


def test_multi_arch_obstacle(visualize=False):
    container = MultiObstacleContainer()
    container.append(
        BlockArchObstacle(
            wall_width=0.4,
            axes_length=np.array([3.0, 5]),
            pose=Pose(np.array([-1.0, -2.5]), orientation=90 * np.pi / 180.0),
        )
    )

    container.append(
        BlockArchObstacle(
            wall_width=0.4,
            axes_length=np.array([3.0, 5]),
            pose=Pose(np.array([1.0, 2.0]), orientation=-90 * np.pi / 180.0),
        )
    )

    attractor = np.array([-4, 4.0])
    initial_dynamics = LinearSystem(attractor_position=attractor, maximum_velocity=1.0)

    # rotation_projector = ProjectedRotationDynamics(
    #     attractor_position=initial_dynamics.attractor_position,
    #     initial_dynamics=initial_dynamics,
    #     reference_velocity=lambda x: x - attractor,
    # )
    multibstacle_avoider = MultiObstacleAvoider(
        obstacle_container=container,
        initial_dynamics=initial_dynamics,
        # convergence_dynamics=rotation_projector,
        create_convergence_dynamics=True,
    )

    velocity = np.array([-1.0, 0])
    linearized_velociy = np.array([-1.0, 0])

    if visualize:
        import matplotlib.pyplot as plt
        from dynamic_obstacle_avoidance.visualization import plot_obstacle_dynamics
        from dynamic_obstacle_avoidance.visualization import plot_obstacles

        fig, ax = plt.subplots(figsize=(6, 5))

        x_lim = [-5, 5.0]
        y_lim = [-5, 5.0]
        n_grid = 20

        for multi_obs in container:
            plot_obstacles(
                obstacle_container=multi_obs._obstacle_list,
                ax=ax,
                x_lim=x_lim,
                y_lim=y_lim,
                draw_reference=True,
                noTicks=False,
                # reference_point_number=True,
                show_obstacle_number=True,
                # ** kwargs,
            )

        plot_obstacle_dynamics(
            obstacle_container=[],
            collision_check_functor=lambda x: (
                container.get_gamma(x, in_global_frame=True) <= 1
            ),
            # obstacle_container=triple_ellipses._obstacle_list,
            # dynamics=lambda x: multibstacle_avoider.get_tangent_direction(
            #     x, velocity, linearized_velociy
            # ),
            dynamics=multibstacle_avoider.evaluate,
            x_lim=x_lim,
            y_lim=y_lim,
            ax=ax,
            do_quiver=True,
            # do_quiver=False,
            n_grid=n_grid,
            show_ticks=True,
            # vectorfield_color=vf_color,
        )

    position = np.array([-0.19, -0.35])
    averaged_direction = multibstacle_avoider.get_tangent_direction(
        position, velocity, linearized_velociy
    )
    assert averaged_direction[0] < 0, "Expected to continue to the left."
    assert averaged_direction[1] < 0, "Expected to rotate down."

    position = np.array([-2.4, -0.19])
    averaged_direction = multibstacle_avoider.get_tangent_direction(
        position, velocity, linearized_velociy
    )
    assert averaged_direction[0] < 0, "Expected to continue to the left."
    assert averaged_direction[1] > 0, "Expected to rotate down."


if (__name__) == "__main__":
    # test_2d_blocky_arch(visualize=False)
    # test_2d_blocky_arch_rotated(visualize=True)
    test_multi_arch_obstacle(visualize=False)

    print("Tests done.")
