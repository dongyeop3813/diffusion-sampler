import numpy as np

import torch
import torch.distributions as D

from .base_energy import BaseEnergy


class Funnel(BaseEnergy):
    """
    Funnel energy function.
    For this, the ground truth sampling is available.

    x0 ~ N(0, sigma^2),

    xi | x0 ~ N(0, exp(x0))
    """

    logZ_is_available = True
    _ground_truth_logZ = 0.0

    can_sample = True

    def __init__(
        self,
        device: str,
        dim: int = 10,
        dominant_sigma: float = 3.0,
    ):
        super().__init__(device=device, dim=dim)
        # xlim = 0.01 if nmode == 1 else xlim

        self.dominant_distribution = D.Normal(
            torch.tensor([0.0], device=self.device),
            torch.tensor([dominant_sigma], device=self.device),
        )

        self.mean_other = torch.zeros(
            self.data_ndim - 1, dtype=float, device=self.device
        )
        self.cov_eye = torch.eye(
            self.data_ndim - 1, dtype=float, device=self.device
        ).view(1, self.data_ndim - 1, self.data_ndim - 1)

    def energy(self, x: torch.Tensor):
        return -self.log_prob(x)

    @BaseEnergy._match_device
    def log_prob(self, x: torch.Tensor):
        dominant_x = x[..., 0]
        log_density_dominant = self.dominant_distribution.log_prob(dominant_x)  # (B, )

        log_sigma = 0.5 * x[..., 0:1]
        sigma_square = torch.exp(x[..., 0:1])
        minus_log_density_other = (
            0.5 * np.log(2 * np.pi) + log_sigma + 0.5 * x[..., 1:] ** 2 / sigma_square
        )
        log_density_other = torch.sum(-minus_log_density_other, dim=-1)

        return log_density_dominant + log_density_other

    def _generate_sample(self, batch_size: int) -> torch.Tensor:
        dominant_x = self.dominant_distribution.sample((batch_size,))  # (B,1)
        x_others = self._other_distribution(dominant_x).sample()  # (B, dim-1)

        return torch.hstack([dominant_x, x_others])

    def _other_distribution(self, dominant_x: torch.Tensor):
        variance_other = torch.exp(dominant_x)
        cov_other = variance_other.view(-1, 1, 1) * self.cov_eye
        # use covariance matrix, not std
        return D.multivariate_normal.MultivariateNormal(self.mean_other, cov_other)
