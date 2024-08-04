import abc

import torch

import matplotlib.pyplot as plt
from tqdm import trange

from omegaconf import DictConfig

from energy import BaseEnergy, Plotter
from models import SamplerModel
from buffer import *

from metrics import compute_all_metrics, add_prefix_to_dict_key
from .utils.etc import get_experiment_output_dir


class BaseTrainer(abc.ABC):
    """
    Base Trainer class for training models.
    User need to implement the following methods:
        - initialize
        - train_step

    If you want to use own evaluation method, you can override eval_step method.
    """

    def __init__(
        self,
        model: SamplerModel,
        energy_function: BaseEnergy,
        train_cfg: DictConfig,
        eval_cfg: DictConfig,
    ):
        self.model = model
        self.energy_function = energy_function
        self.plotter = Plotter(energy_function, **eval_cfg.plot)

        self.train_cfg = train_cfg
        self.eval_cfg = eval_cfg

        self.current_epoch = 0
        self.max_epoch = train_cfg.epochs

        self.optimizer = self.model.get_optimizer()

    @abc.abstractmethod
    def initialize(self):
        pass

    def train_step(self) -> float:
        """
        Execute one training step and return train loss.

        Returns:
            loss: training loss
        """
        raise NotImplementedError("train_step method must be implemented.")

    def eval_step(self) -> dict:
        """
        Execute evaluation step and return metric dictionary.

        Returns:
            metric: a dictionary containing metric value
        """

        eval_data_size = (
            self.eval_cfg.final_eval_data_size
            if self.train_end
            else self.eval_cfg.eval_data_size
        )

        metrics: dict = compute_all_metrics(
            model=self.model,
            eval_data_size=eval_data_size,
            do_resample=self.train_end,
            # At the end of training, we resample the evaluation data.
        )

        metrics = add_prefix_to_dict_key("eval/", metrics)

        return metrics

    def make_plot(self):
        """
        Generate sample from model and plot it using energy function's make_plot method.
        If energy function does not have make_plot method, return empty dict.

        If you want to add more visualization, you can override this method.

        Returns:
            dict: dictionary that has figure objects as value
        """
        output_dir = get_experiment_output_dir()
        plot_sample_size = self.eval_cfg.plot_sample_size

        model = self.model

        samples = model.sample(batch_size=plot_sample_size)

        fig, _ = self.plotter.make_plot(samples)

        fig.savefig(f"{output_dir}/plot.pdf", bbox_inches="tight")

        return {
            "visuals/sample-plot": fig,
        }

    def train(self):
        # Initialize some variables (e.g., optimizer, buffer, frequently used values)
        self.initialize()

        self.model.train()
        for epoch in trange(self.max_epoch + 1):
            self.current_epoch = epoch

            loss = self.train_step()

            self.log_loss_to_run(loss)

            if self.must_eval(epoch):
                self.log_metric_to_run(self.eval_step())

                self.log_visual_to_run(self.make_plot())

                # Prevent too much plt objects from lasting
                plt.close("all")

            if self.must_save(epoch):
                self.save_model()

    def log_loss_to_run(self, loss: float):
        self.run["train/loss"].append(loss)

    def log_metric_to_run(self, metrics: dict):
        epoch = self.current_epoch

        for metric_name, metric_value in metrics.items():
            self.run[metric_name].append(value=metric_value, step=epoch)

    def log_visual_to_run(self, visuals: dict):
        for visual_name, plot in visuals.items():
            self.run[visual_name].append(plot, step=self.current_epoch)

    @property
    def train_end(self):
        return self.current_epoch == self.max_epoch

    def must_save(self, epoch: int = 0):
        return epoch % self.eval_cfg.save_model_every_n_epoch == 0 or self.train_end

    def must_eval(self, epoch: int = 0):
        return epoch % self.eval_cfg.eval_every_n_epoch == 0 or self.train_end

    def save_model(self):
        final = "_final" if self.train_end else ""
        output_dir = get_experiment_output_dir()

        model_path = f"{output_dir}/model{final}.pt"

        torch.save(self.model.state_dict(), model_path)

        self.run[f"model_ckpts/epoch_{self.current_epoch}"].upload(model_path)
