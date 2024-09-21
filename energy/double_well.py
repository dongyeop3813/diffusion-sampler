import torch

from .base_energy import HighDimensionalEnergy


def compute_distances(x, n_particles, n_dimensions, remove_duplicates=True):
    """
    Computes the all distances for a given particle configuration x.

    Parameters
    ----------
    x : torch.Tensor
        Positions of n_particles in n_dimensions.
    remove_duplicates : boolean
        Flag indicating whether to remove duplicate distances
        and distances be.
        If False the all distance matrix is returned instead.

    Returns
    -------
    distances : torch.Tensor
        All-distances between particles in a configuration
        Tensor of shape `[n_batch, n_particles * (n_particles - 1) // 2]` if remove_duplicates.
        Otherwise `[n_batch, n_particles , n_particles]`
    """
    x = x.reshape(-1, n_particles, n_dimensions)
    distances = torch.cdist(x, x)
    if remove_duplicates:
        distances = distances[
            :, torch.triu(torch.ones((n_particles, n_particles)), diagonal=1) == 1
        ]
        distances = distances.reshape(-1, n_particles * (n_particles - 1) // 2)
    return distances


class DoubleWellEnergy(HighDimensionalEnergy):
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
        dists = compute_distances(x, self.n_particles, self.spatial_dim)
        dists = dists - self.offset

        energy = self.a * dists**4 + self.b * dists**2 + self.c

        return energy.sum(-1)

    def _generate_sample(self, batch_size: int):
        raise NotImplementedError

    def _remove_mean(self, x):
        x = x.view(-1, self.n_particles, self.spatial_dim)
        return x - torch.mean(x, dim=1, keepdim=True)

    def interatomic_dist(self, x):
        batch_shape = x.shape[:-1]
        x = x.view(*batch_shape, self.n_particles, self.spatial_dim)

        # Compute the pairwise interatomic distances
        # removes duplicates and diagonal
        distances = x[:, None, :, :] - x[:, :, None, :]
        distances = distances[
            :,
            torch.triu(torch.ones((self.n_particles, self.n_particles)), diagonal=1)
            == 1,
        ]
        dist = torch.linalg.norm(distances, dim=-1)
        return dist