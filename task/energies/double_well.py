import torch
import numpy as np

from .base_energy import BaseEnergy
from .particle_system import interatomic_distance, remove_mean


class DoubleWellEnergy(BaseEnergy):
    logZ_is_available = False
    can_sample = False

    a = 0.9
    b = -4
    c = 0
    offset = 4

    def __init__(
        self,
        device: str,
        spatial_dim: int = 2,
        n_particles: int = 4,
    ):
        super().__init__(device=device, dim=spatial_dim * n_particles)

        self.spatial_dim = spatial_dim
        self.n_particles = n_particles

    def energy(self, x: torch.Tensor):
        assert x.shape[-1] == self.ndim

        x = x.contiguous()
        dists = interatomic_distance(x, self.n_particles, self.spatial_dim)
        dists = dists - self.offset

        energy = self.a * dists**4 + self.b * dists**2 + self.c

        return energy.sum(-1)

    def _generate_sample(self, batch_size: int):
        raise NotImplementedError

    def remove_mean(self, x: torch.Tensor):
        return remove_mean(x, self.n_particles, self.spatial_dim)

    def interatomic_distance(self, x: torch.Tensor):
        return interatomic_distance(
            x, self.n_particles, self.spatial_dim, remove_duplicates=True
        )


class DW4(DoubleWellEnergy):
    can_sample = True

    def __init__(self, device: str):
        super().__init__(device=device, spatial_dim=2, n_particles=4)

        # sample generated by long run MCMC.
        self.approx_sample = torch.tensor(
            np.load("task/energies/data/DW4.npy"), device=device
        )

    def _generate_sample(self, batch_size: int):
        return self.approx_sample[torch.randperm(batch_size)]
