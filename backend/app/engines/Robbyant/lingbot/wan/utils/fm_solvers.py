# Copied from https://github.com/huggingface/diffusers/blob/main/src/diffusers/schedulers/scheduling_dpmsolver_multistep.py
# Convert dpm solver for flow matching


import inspect
import math
from typing import List, Optional, Tuple, Union

import numpy as np
import torch
from diffusers.configuration_utils import ConfigMixin, register_to_config
from diffusers.schedulers.scheduling_utils import (
    KarrasDiffusionSchedulers,
    SchedulerMixin,
    SchedulerOutput,
)
from diffusers.utils import deprecate, is_scipy_available
from diffusers.utils.torch_utils import randn_tensor

if is_scipy_available():
    pass


def get_sampling_sigmas(sampling_steps, shift):
    sigma = np.linspace(1, 0, sampling_steps + 1)[:sampling_steps]
    sigma = (shift * sigma / (1 + (shift - 1) * sigma))

    return sigma


def retrieve_timesteps(
    scheduler,
    num_inference_steps=None,
    device=None,
    timesteps=None,
    sigmas=None,
    **kwargs,
):
    if timesteps is not None and sigmas is not None:
        raise ValueError(
            "Only one of `timesteps` or `sigmas` can be passed. Please choose one to set custom values"
        )
    if timesteps is not None:
        accepts_timesteps = "timesteps" in set(
            inspect.signature(scheduler.set_timesteps).parameters.keys())
        if not accepts_timesteps:
            raise ValueError(
                f"The current scheduler class {scheduler.__class__}'s `set_timesteps` does not support custom"
                f" timestep schedules. Please check whether you are using the correct scheduler."
            )
        scheduler.set_timesteps(timesteps=timesteps, device=device, **kwargs)
        timesteps = scheduler.timesteps
        num_inference_steps = len(timesteps)
    elif sigmas is not None:
        accept_sigmas = "sigmas" in set(
            inspect.signature(scheduler.set_timesteps).parameters.keys())
        if not accept_sigmas:
            raise ValueError(
                f"The current scheduler class {scheduler.__class__}'s `set_timesteps` does not support custom"
                f" sigmas schedules. Please check whether you are using the correct scheduler."
            )
        scheduler.set_timesteps(sigmas=sigmas, device=device, **kwargs)
        timesteps = scheduler.timesteps
        num_inference_steps = len(timesteps)
    else:
        scheduler.set_timesteps(num_inference_steps, device=device, **kwargs)
        timesteps = scheduler.timesteps
    return timesteps, num_inference_steps


class FlowDPMSolverMultistepScheduler(SchedulerMixin, ConfigMixin):
    """
    `FlowDPMSolverMultistepScheduler` 是一个用于扩散 ODE 的快速专用高阶求解器。
    该模型继承自 [`SchedulerMixin`] 和 [`ConfigMixin`]。请查看超类文档以了解库为所有调度器实现的通用方法，如加载和保存。
    Args:
        num_train_timesteps (`int`, defaults to 1000):
            训练模型的扩散步数。这决定了扩散过程的分辨率。
        solver_order (`int`, defaults to 2):
            DPMSolver 的阶数，可以是 `1`、`2` 或 `3`。建议对于引导采样使用 `solver_order=2`，对于无条件采样使用 `solver_order=3`。
            这会影响多步更新中存储和使用的模型输出数量。
        prediction_type (`str`, defaults to "flow_prediction"):
            调度器函数的预测类型；对于此调度器必须是 `flow_prediction`，它预测扩散过程的流。
        shift (`float`, *optional*, defaults to 1.0):
            用于调整噪声计划中 sigmas 的因子。它在采样过程中修改步长。
        use_dynamic_shifting (`bool`, defaults to `False`):
            是否根据图像分辨率动态调整时间步。如果为 `True`，则实时应用调整。
        thresholding (`bool`, defaults to `False`):
            是否使用 "动态阈值" 方法。此方法调整预测样本以防止饱和并提高真实感。
        dynamic_thresholding_ratio (`float`, defaults to 0.995):
            动态阈值方法的比率。仅当 `thresholding=True` 时有效。
        sample_max_value (`float`, defaults to 1.0):
            动态阈值的阈值。仅当 `thresholding=True` 且 `algorithm_type="dpmsolver++"` 时有效。
        algorithm_type (`str`, defaults to `dpmsolver++`):
            求解器的算法类型；可以是 `dpmsolver`、`dpmsolver++`、`sde-dpmsolver` 或 `sde-dpmsolver++`。
            `dpmsolver` 类型实现了 [DPMSolver](https://huggingface.co/papers/2206.00927) 论文中的算法，
            `dpmsolver++` 类型实现了 [DPMSolver++](https://huggingface.co/papers/2211.01095) 论文中的算法。
            建议使用 `dpmsolver++` 或 `sde-dpmsolver++` 并设置 `solver_order=2` 用于引导采样，如 Stable Diffusion 中所示。
        solver_type (`str`, defaults to `midpoint`):
            二阶求解器的求解器类型；可以是 `midpoint` 或 `heun`。求解器类型稍微影响样本质量，特别是对于少量步数。建议使用 `midpoint` 求解器。
        lower_order_final (`bool`, defaults to `True`):
            是否在最后几步使用低阶求解器。仅对 < 15 推理步数有效。这可以稳定 DPMSolver 在步数 < 15 时的采样，特别是对于步数 <= 10 的情况。
        euler_at_final (`bool`, defaults to `False`):
            是否在最后一步使用 Euler 方法。这是数值稳定性和细节丰富度之间的权衡。这可以稳定 SDE 变体 DPMSolver 在少量推理步数下的采样，但有时可能会导致模糊。
        final_sigmas_type (`str`, *optional*, defaults to "zero"):
            采样过程中噪声计划的最终 `sigma` 值。如果为 `"sigma_min"`，最终 sigma 与训练计划中的最后一个 sigma 相同。如果为 `zero`，最终 sigma 设置为 0。
        lambda_min_clipped (`float`, defaults to `-inf`):
            `lambda(t)` 最小值的裁剪阈值，用于数值稳定性。这对于余弦 (`squaredcos_cap_v2`) 噪声计划至关重要。
        variance_type (`str`, *optional*):
            对于预测方差的扩散模型，设置为 "learned" 或 "learned_range"。如果设置，模型的输出包含预测的高斯方差。
    """

    _compatibles = [e.name for e in KarrasDiffusionSchedulers]
    order = 1

    @register_to_config
    def __init__(
        self,
        num_train_timesteps: int = 1000,
        solver_order: int = 2,
        prediction_type: str = "flow_prediction",
        shift: Optional[float] = 1.0,
        use_dynamic_shifting=False,
        thresholding: bool = False,
        dynamic_thresholding_ratio: float = 0.995,
        sample_max_value: float = 1.0,
        algorithm_type: str = "dpmsolver++",
        solver_type: str = "midpoint",
        lower_order_final: bool = True,
        euler_at_final: bool = False,
        final_sigmas_type: Optional[str] = "zero",  # "zero", "sigma_min"
        lambda_min_clipped: float = -float("inf"),
        variance_type: Optional[str] = None,
        invert_sigmas: bool = False,
    ):
        if algorithm_type in ["dpmsolver", "sde-dpmsolver"]:
            deprecation_message = f"algorithm_type {algorithm_type} is deprecated and will be removed in a future version. Choose from `dpmsolver++` or `sde-dpmsolver++` instead"
            deprecate("algorithm_types dpmsolver and sde-dpmsolver", "1.0.0",
                      deprecation_message)

        # settings for DPM-Solver
        if algorithm_type not in [
                "dpmsolver", "dpmsolver++", "sde-dpmsolver", "sde-dpmsolver++"
        ]:
            if algorithm_type == "deis":
                self.register_to_config(algorithm_type="dpmsolver++")
            else:
                raise NotImplementedError(
                    f"{algorithm_type} is not implemented for {self.__class__}")

        if solver_type not in ["midpoint", "heun"]:
            if solver_type in ["logrho", "bh1", "bh2"]:
                self.register_to_config(solver_type="midpoint")
            else:
                raise NotImplementedError(
                    f"{solver_type} is not implemented for {self.__class__}")

        if algorithm_type not in ["dpmsolver++", "sde-dpmsolver++"
                                 ] and final_sigmas_type == "zero":
            raise ValueError(
                f"`final_sigmas_type` {final_sigmas_type} is not supported for `algorithm_type` {algorithm_type}. Please choose `sigma_min` instead."
            )

        # setable values
        self.num_inference_steps = None
        alphas = np.linspace(1, 1 / num_train_timesteps,
                             num_train_timesteps)[::-1].copy()
        sigmas = 1.0 - alphas
        sigmas = torch.from_numpy(sigmas).to(dtype=torch.float32)

        if not use_dynamic_shifting:
            # when use_dynamic_shifting is True, we apply the timestep shifting on the fly based on the image resolution
            sigmas = shift * sigmas / (1 +
                                       (shift - 1) * sigmas)  # pyright: ignore

        self.sigmas = sigmas
        self.timesteps = sigmas * num_train_timesteps

        self.model_outputs = [None] * solver_order
        self.lower_order_nums = 0
        self._step_index = None
        self._begin_index = None

        # self.sigmas = self.sigmas.to(
        #     "cpu")  # to avoid too much CPU/GPU communication
        self.sigma_min = self.sigmas[-1].item()
        self.sigma_max = self.sigmas[0].item()

    @property
    def step_index(self):
        """
        当前时间步的索引计数器。每次调度器步进后增加 1。
        """
        return self._step_index

    @property
    def begin_index(self):
        """
        第一个时间步的索引。应使用 `set_begin_index` 方法从管道设置。
        """
        return self._begin_index

    # Copied from diffusers.schedulers.scheduling_dpmsolver_multistep.DPMSolverMultistepScheduler.set_begin_index
    def set_begin_index(self, begin_index: int = 0):
        """
        设置调度器的起始索引。此函数应在推理前从管道运行。
        Args:
            begin_index (`int`):
                调度器的起始索引。
        """
        self._begin_index = begin_index

    # Modified from diffusers.schedulers.scheduling_flow_match_euler_discrete.FlowMatchEulerDiscreteScheduler.set_timesteps
    def set_timesteps(
        self,
        num_inference_steps: Union[int, None] = None,
        device: Union[str, torch.device] = None,
        sigmas: Optional[List[float]] = None,
        mu: Optional[Union[float, None]] = None,
        shift: Optional[Union[float, None]] = None,
    ):
        """
        设置用于扩散链的离散时间步（在推理前运行）。
        Args:
            num_inference_steps (`int`):
                时间步的总数。
            device (`str` or `torch.device`, *optional*):
                时间步应移动到的设备。如果为 `None`，则不移动时间步。
        """

        if self.config.use_dynamic_shifting and mu is None:
            raise ValueError(
                " you have to pass a value for `mu` when `use_dynamic_shifting` is set to be `True`"
            )

        if sigmas is None:
            sigmas = np.linspace(self.sigma_max, self.sigma_min,
                                 num_inference_steps +
                                 1).copy()[:-1]  # pyright: ignore

        if self.config.use_dynamic_shifting:
            sigmas = self.time_shift(mu, 1.0, sigmas)  # pyright: ignore
        else:
            if shift is None:
                shift = self.config.shift
            sigmas = shift * sigmas / (1 +
                                       (shift - 1) * sigmas)  # pyright: ignore

        if self.config.final_sigmas_type == "sigma_min":
            sigma_last = ((1 - self.alphas_cumprod[0]) /
                          self.alphas_cumprod[0])**0.5
        elif self.config.final_sigmas_type == "zero":
            sigma_last = 0
        else:
            raise ValueError(
                f"`final_sigmas_type` must be one of 'zero', or 'sigma_min', but got {self.config.final_sigmas_type}"
            )

        timesteps = sigmas * self.config.num_train_timesteps
        sigmas = np.concatenate([sigmas, [sigma_last]
                                ]).astype(np.float32)  # pyright: ignore

        self.sigmas = torch.from_numpy(sigmas)
        self.timesteps = torch.from_numpy(timesteps).to(
            device=device, dtype=torch.int64)

        self.num_inference_steps = len(timesteps)

        self.model_outputs = [
            None,
        ] * self.config.solver_order
        self.lower_order_nums = 0

        self._step_index = None
        self._begin_index = None
        # self.sigmas = self.sigmas.to(
        #     "cpu")  # to avoid too much CPU/GPU communication

    # Copied from diffusers.schedulers.scheduling_ddpm.DDPMScheduler._threshold_sample
    def _threshold_sample(self, sample: torch.Tensor) -> torch.Tensor:
        """
        "Dynamic thresholding: At each sampling step we set s to a certain percentile absolute pixel value in xt0 (the
        prediction of x_0 at timestep t), and if s > 1, then we threshold xt0 to the range [-s, s] and then divide by
        s. Dynamic thresholding pushes saturated pixels (those near -1 and 1) inwards, thereby actively preventing
        pixels from saturation at each step. We find that dynamic thresholding results in significantly better
        photorealism as well as better image-text alignment, especially when using very large guidance weights."
        https://arxiv.org/abs/2205.11487
        """
        dtype = sample.dtype
        batch_size, channels, *remaining_dims = sample.shape

        if dtype not in (torch.float32, torch.float64):
            sample = sample.float(
            )  # upcast for quantile calculation, and clamp not implemented for cpu half

        # Flatten sample for doing quantile calculation along each image
        sample = sample.reshape(batch_size, channels * np.prod(remaining_dims))

        abs_sample = sample.abs()  # "a certain percentile absolute pixel value"

        s = torch.quantile(
            abs_sample, self.config.dynamic_thresholding_ratio, dim=1)
        s = torch.clamp(
            s, min=1, max=self.config.sample_max_value
        )  # When clamped to min=1, equivalent to standard clipping to [-1, 1]
        s = s.unsqueeze(
            1)  # (batch_size, 1) because clamp will broadcast along dim=0
        sample = torch.clamp(
            sample, -s, s
        ) / s  # "we threshold xt0 to the range [-s, s] and then divide by s"

        sample = sample.reshape(batch_size, channels, *remaining_dims)
        sample = sample.to(dtype)

        return sample

    # Copied from diffusers.schedulers.scheduling_flow_match_euler_discrete.FlowMatchEulerDiscreteScheduler._sigma_to_t
    def _sigma_to_t(self, sigma):
        return sigma * self.config.num_train_timesteps

    def _sigma_to_alpha_sigma_t(self, sigma):
        return 1 - sigma, sigma

    # Copied from diffusers.schedulers.scheduling_flow_match_euler_discrete.set_timesteps
    def time_shift(self, mu: float, sigma: float, t: torch.Tensor):
        return math.exp(mu) / (math.exp(mu) + (1 / t - 1)**sigma)

    # Copied from diffusers.schedulers.scheduling_dpmsolver_multistep.DPMSolverMultistepScheduler.convert_model_output
    def convert_model_output(
        self,
        model_output: torch.Tensor,
        *args,
        sample: torch.Tensor = None,
        **kwargs,
    ) -> torch.Tensor:
        """
        将模型输出转换为 DPMSolver/DPMSolver++ 算法所需的相应类型。DPM-Solver 旨在离散化噪声预测模型的积分，
        而 DPM-Solver++ 旨在离散化数据预测模型的积分。
        <Tip>
        算法和模型类型是解耦的。您可以为噪声预测和数据预测模型使用 DPMSolver 或 DPMSolver++。
        </Tip>
        Args:
            model_output (`torch.Tensor`):
                学习到的扩散模型的直接输出。
            sample (`torch.Tensor`):
                扩散过程创建的当前样本实例。
        Returns:
            `torch.Tensor`:
                转换后的模型输出。
        """
        timestep = args[0] if len(args) > 0 else kwargs.pop("timestep", None)
        if sample is None:
            if len(args) > 1:
                sample = args[1]
            else:
                raise ValueError(
                    "missing `sample` as a required keyward argument")
        if timestep is not None:
            deprecate(
                "timesteps",
                "1.0.0",
                "Passing `timesteps` is deprecated and has no effect as model output conversion is now handled via an internal counter `self.step_index`",
            )

        # DPM-Solver++ needs to solve an integral of the data prediction model.
        if self.config.algorithm_type in ["dpmsolver++", "sde-dpmsolver++"]:
            if self.config.prediction_type == "flow_prediction":
                sigma_t = self.sigmas[self.step_index]
                x0_pred = sample - sigma_t * model_output
            else:
                raise ValueError(
                    f"prediction_type given as {self.config.prediction_type} must be one of `epsilon`, `sample`,"
                    " `v_prediction`, or `flow_prediction` for the FlowDPMSolverMultistepScheduler."
                )

            if self.config.thresholding:
                x0_pred = self._threshold_sample(x0_pred)

            return x0_pred

        # DPM-Solver needs to solve an integral of the noise prediction model.
        elif self.config.algorithm_type in ["dpmsolver", "sde-dpmsolver"]:
            if self.config.prediction_type == "flow_prediction":
                sigma_t = self.sigmas[self.step_index]
                epsilon = sample - (1 - sigma_t) * model_output
            else:
                raise ValueError(
                    f"prediction_type given as {self.config.prediction_type} must be one of `epsilon`, `sample`,"
                    " `v_prediction` or `flow_prediction` for the FlowDPMSolverMultistepScheduler."
                )

            if self.config.thresholding:
                sigma_t = self.sigmas[self.step_index]
                x0_pred = sample - sigma_t * model_output
                x0_pred = self._threshold_sample(x0_pred)
                epsilon = model_output + x0_pred

            return epsilon

    # Copied from diffusers.schedulers.scheduling_dpmsolver_multistep.DPMSolverMultistepScheduler.dpm_solver_first_order_update
    def dpm_solver_first_order_update(
        self,
        model_output: torch.Tensor,
        *args,
        sample: torch.Tensor = None,
        noise: Optional[torch.Tensor] = None,
        **kwargs,
    ) -> torch.Tensor:
        """
        一阶 DPMSolver 的一步（相当于 DDIM）。
        Args:
            model_output (`torch.Tensor`):
                学习到的扩散模型的直接输出。
            sample (`torch.Tensor`):
                扩散过程创建的当前样本实例。
        Returns:
            `torch.Tensor`:
                上一个时间步的样本张量。
        """
        timestep = args[0] if len(args) > 0 else kwargs.pop("timestep", None)
        prev_timestep = args[1] if len(args) > 1 else kwargs.pop(
            "prev_timestep", None)
        if sample is None:
            if len(args) > 2:
                sample = args[2]
            else:
                raise ValueError(
                    " missing `sample` as a required keyward argument")
        if timestep is not None:
            deprecate(
                "timesteps",
                "1.0.0",
                "Passing `timesteps` is deprecated and has no effect as model output conversion is now handled via an internal counter `self.step_index`",
            )

        if prev_timestep is not None:
            deprecate(
                "prev_timestep",
                "1.0.0",
                "Passing `prev_timestep` is deprecated and has no effect as model output conversion is now handled via an internal counter `self.step_index`",
            )

        sigma_t, sigma_s = self.sigmas[self.step_index + 1], self.sigmas[
            self.step_index]  # pyright: ignore
        alpha_t, sigma_t = self._sigma_to_alpha_sigma_t(sigma_t)
        alpha_s, sigma_s = self._sigma_to_alpha_sigma_t(sigma_s)
        lambda_t = torch.log(alpha_t) - torch.log(sigma_t)
        lambda_s = torch.log(alpha_s) - torch.log(sigma_s)

        h = lambda_t - lambda_s
        if self.config.algorithm_type == "dpmsolver++":
            x_t = (sigma_t /
                   sigma_s) * sample - (alpha_t *
                                        (torch.exp(-h) - 1.0)) * model_output
        elif self.config.algorithm_type == "dpmsolver":
            x_t = (alpha_t /
                   alpha_s) * sample - (sigma_t *
                                        (torch.exp(h) - 1.0)) * model_output
        elif self.config.algorithm_type == "sde-dpmsolver++":
            assert noise is not None
            x_t = ((sigma_t / sigma_s * torch.exp(-h)) * sample +
                   (alpha_t * (1 - torch.exp(-2.0 * h))) * model_output +
                   sigma_t * torch.sqrt(1.0 - torch.exp(-2 * h)) * noise)
        elif self.config.algorithm_type == "sde-dpmsolver":
            assert noise is not None
            x_t = ((alpha_t / alpha_s) * sample - 2.0 *
                   (sigma_t * (torch.exp(h) - 1.0)) * model_output +
                   sigma_t * torch.sqrt(torch.exp(2 * h) - 1.0) * noise)
        return x_t  # pyright: ignore

    # Copied from diffusers.schedulers.scheduling_dpmsolver_multistep.DPMSolverMultistepScheduler.multistep_dpm_solver_second_order_update
    def multistep_dpm_solver_second_order_update(
        self,
        model_output_list: List[torch.Tensor],
        *args,
        sample: torch.Tensor = None,
        noise: Optional[torch.Tensor] = None,
        **kwargs,
    ) -> torch.Tensor:
        """
        二阶多步 DPMSolver 的一步。
        Args:
            model_output_list (`List[torch.Tensor]`):
                当前和后续时间步学习到的扩散模型的直接输出。
            sample (`torch.Tensor`):
                扩散过程创建的当前样本实例。
        Returns:
            `torch.Tensor`:
                上一个时间步的样本张量。
        """
        timestep_list = args[0] if len(args) > 0 else kwargs.pop(
            "timestep_list", None)
        prev_timestep = args[1] if len(args) > 1 else kwargs.pop(
            "prev_timestep", None)
        if sample is None:
            if len(args) > 2:
                sample = args[2]
            else:
                raise ValueError(
                    " missing `sample` as a required keyward argument")
        if timestep_list is not None:
            deprecate(
                "timestep_list",
                "1.0.0",
                "Passing `timestep_list` is deprecated and has no effect as model output conversion is now handled via an internal counter `self.step_index`",
            )

        if prev_timestep is not None:
            deprecate(
                "prev_timestep",
                "1.0.0",
                "Passing `prev_timestep` is deprecated and has no effect as model output conversion is now handled via an internal counter `self.step_index`",
            )

        sigma_t, sigma_s0, sigma_s1 = (
            self.sigmas[self.step_index + 1],  # pyright: ignore
            self.sigmas[self.step_index],
            self.sigmas[self.step_index - 1],  # pyright: ignore
        )

        alpha_t, sigma_t = self._sigma_to_alpha_sigma_t(sigma_t)
        alpha_s0, sigma_s0 = self._sigma_to_alpha_sigma_t(sigma_s0)
        alpha_s1, sigma_s1 = self._sigma_to_alpha_sigma_t(sigma_s1)

        lambda_t = torch.log(alpha_t) - torch.log(sigma_t)
        lambda_s0 = torch.log(alpha_s0) - torch.log(sigma_s0)
        lambda_s1 = torch.log(alpha_s1) - torch.log(sigma_s1)

        m0, m1 = model_output_list[-1], model_output_list[-2]

        h, h_0 = lambda_t - lambda_s0, lambda_s0 - lambda_s1
        r0 = h_0 / h
        D0, D1 = m0, (1.0 / r0) * (m0 - m1)
        if self.config.algorithm_type == "dpmsolver++":
            # See https://arxiv.org/abs/2211.01095 for detailed derivations
            if self.config.solver_type == "midpoint":
                x_t = ((sigma_t / sigma_s0) * sample -
                       (alpha_t * (torch.exp(-h) - 1.0)) * D0 - 0.5 *
                       (alpha_t * (torch.exp(-h) - 1.0)) * D1)
            elif self.config.solver_type == "heun":
                x_t = ((sigma_t / sigma_s0) * sample -
                       (alpha_t * (torch.exp(-h) - 1.0)) * D0 +
                       (alpha_t * ((torch.exp(-h) - 1.0) / h + 1.0)) * D1)
        elif self.config.algorithm_type == "dpmsolver":
            # See https://arxiv.org/abs/2206.00927 for detailed derivations
            if self.config.solver_type == "midpoint":
                x_t = ((alpha_t / alpha_s0) * sample -
                       (sigma_t * (torch.exp(h) - 1.0)) * D0 - 0.5 *
                       (sigma_t * (torch.exp(h) - 1.0)) * D1)
            elif self.config.solver_type == "heun":
                x_t = ((alpha_t / alpha_s0) * sample -
                       (sigma_t * (torch.exp(h) - 1.0)) * D0 -
                       (sigma_t * ((torch.exp(h) - 1.0) / h - 1.0)) * D1)
        elif self.config.algorithm_type == "sde-dpmsolver++":
            assert noise is not None
            if self.config.solver_type == "midpoint":
                x_t = ((sigma_t / sigma_s0 * torch.exp(-h)) * sample +
                       (alpha_t * (1 - torch.exp(-2.0 * h))) * D0 + 0.5 *
                       (alpha_t * (1 - torch.exp(-2.0 * h))) * D1 +
                       sigma_t * torch.sqrt(1.0 - torch.exp(-2 * h)) * noise)
            elif self.config.solver_type == "heun":
                x_t = ((sigma_t / sigma_s0 * torch.exp(-h)) * sample +
                       (alpha_t * (1 - torch.exp(-2.0 * h))) * D0 +
                       (alpha_t * ((1.0 - torch.exp(-2.0 * h)) /
                                   (-2.0 * h) + 1.0)) * D1 +
                       sigma_t * torch.sqrt(1.0 - torch.exp(-2 * h)) * noise)
        elif self.config.algorithm_type == "sde-dpmsolver":
            assert noise is not None
            if self.config.solver_type == "midpoint":
                x_t = ((alpha_t / alpha_s0) * sample - 2.0 *
                       (sigma_t * (torch.exp(h) - 1.0)) * D0 -
                       (sigma_t * (torch.exp(h) - 1.0)) * D1 +
                       sigma_t * torch.sqrt(torch.exp(2 * h) - 1.0) * noise)
            elif self.config.solver_type == "heun":
                x_t = ((alpha_t / alpha_s0) * sample - 2.0 *
                       (sigma_t * (torch.exp(h) - 1.0)) * D0 - 2.0 *
                       (sigma_t * ((torch.exp(h) - 1.0) / h - 1.0)) * D1 +
                       sigma_t * torch.sqrt(torch.exp(2 * h) - 1.0) * noise)
        return x_t  # pyright: ignore

    # Copied from diffusers.schedulers.scheduling_dpmsolver_multistep.DPMSolverMultistepScheduler.multistep_dpm_solver_third_order_update
    def multistep_dpm_solver_third_order_update(
        self,
        model_output_list: List[torch.Tensor],
        *args,
        sample: torch.Tensor = None,
        **kwargs,
    ) -> torch.Tensor:
        """
        三阶多步 DPMSolver 的一步。
        Args:
            model_output_list (`List[torch.Tensor]`):
                当前和后续时间步学习到的扩散模型的直接输出。
            sample (`torch.Tensor`):
                扩散过程创建的当前样本实例。
        Returns:
            `torch.Tensor`:
                上一个时间步的样本张量。
        """

        timestep_list = args[0] if len(args) > 0 else kwargs.pop(
            "timestep_list", None)
        prev_timestep = args[1] if len(args) > 1 else kwargs.pop(
            "prev_timestep", None)
        if sample is None:
            if len(args) > 2:
                sample = args[2]
            else:
                raise ValueError(
                    " missing`sample` as a required keyward argument")
        if timestep_list is not None:
            deprecate(
                "timestep_list",
                "1.0.0",
                "Passing `timestep_list` is deprecated and has no effect as model output conversion is now handled via an internal counter `self.step_index`",
            )

        if prev_timestep is not None:
            deprecate(
                "prev_timestep",
                "1.0.0",
                "Passing `prev_timestep` is deprecated and has no effect as model output conversion is now handled via an internal counter `self.step_index`",
            )

        sigma_t, sigma_s0, sigma_s1, sigma_s2 = (
            self.sigmas[self.step_index + 1],  # pyright: ignore
            self.sigmas[self.step_index],
            self.sigmas[self.step_index - 1],  # pyright: ignore
            self.sigmas[self.step_index - 2],  # pyright: ignore
        )

        alpha_t, sigma_t = self._sigma_to_alpha_sigma_t(sigma_t)
        alpha_s0, sigma_s0 = self._sigma_to_alpha_sigma_t(sigma_s0)
        alpha_s1, sigma_s1 = self._sigma_to_alpha_sigma_t(sigma_s1)
        alpha_s2, sigma_s2 = self._sigma_to_alpha_sigma_t(sigma_s2)

        lambda_t = torch.log(alpha_t) - torch.log(sigma_t)
        lambda_s0 = torch.log(alpha_s0) - torch.log(sigma_s0)
        lambda_s1 = torch.log(alpha_s1) - torch.log(sigma_s1)
        lambda_s2 = torch.log(alpha_s2) - torch.log(sigma_s2)

        m0, m1, m2 = model_output_list[-1], model_output_list[
            -2], model_output_list[-3]

        h, h_0, h_1 = lambda_t - lambda_s0, lambda_s0 - lambda_s1, lambda_s1 - lambda_s2
        r0, r1 = h_0 / h, h_1 / h
        D0 = m0
        D1_0, D1_1 = (1.0 / r0) * (m0 - m1), (1.0 / r1) * (m1 - m2)
        D1 = D1_0 + (r0 / (r0 + r1)) * (D1_0 - D1_1)
        D2 = (1.0 / (r0 + r1)) * (D1_0 - D1_1)
        if self.config.algorithm_type == "dpmsolver++":
            # See https://arxiv.org/abs/2206.00927 for detailed derivations
            x_t = ((sigma_t / sigma_s0) * sample -
                   (alpha_t * (torch.exp(-h) - 1.0)) * D0 +
                   (alpha_t * ((torch.exp(-h) - 1.0) / h + 1.0)) * D1 -
                   (alpha_t * ((torch.exp(-h) - 1.0 + h) / h**2 - 0.5)) * D2)
        elif self.config.algorithm_type == "dpmsolver":
            # See https://arxiv.org/abs/2206.00927 for detailed derivations
            x_t = ((alpha_t / alpha_s0) * sample - (sigma_t *
                                                    (torch.exp(h) - 1.0)) * D0 -
                   (sigma_t * ((torch.exp(h) - 1.0) / h - 1.0)) * D1 -
                   (sigma_t * ((torch.exp(h) - 1.0 - h) / h**2 - 0.5)) * D2)
        return x_t  # pyright: ignore

    def index_for_timestep(self, timestep, schedule_timesteps=None):
        if schedule_timesteps is None:
            schedule_timesteps = self.timesteps

        indices = (schedule_timesteps == timestep).nonzero()

        # The sigma index that is taken for the **very** first `step`
        # is always the second index (or the last index if there is only 1)
        # This way we can ensure we don't accidentally skip a sigma in
        # case we start in the middle of the denoising schedule (e.g. for image-to-image)
        pos = 1 if len(indices) > 1 else 0

        return indices[pos].item()

    def _init_step_index(self, timestep):
        """
        初始化调度器的 step_index 计数器。
        """

        if self.begin_index is None:
            if isinstance(timestep, torch.Tensor):
                timestep = timestep.to(self.timesteps.device)
            self._step_index = self.index_for_timestep(timestep)
        else:
            self._step_index = self._begin_index

    # Modified from diffusers.schedulers.scheduling_dpmsolver_multistep.DPMSolverMultistepScheduler.step
    def step(
        self,
        model_output: torch.Tensor,
        timestep: Union[int, torch.Tensor],
        sample: torch.Tensor,
        generator=None,
        variance_noise: Optional[torch.Tensor] = None,
        return_dict: bool = True,
    ) -> Union[SchedulerOutput, Tuple]:
        """
        通过反转 SDE 预测上一个时间步的样本。此函数使用多步 DPMSolver 传播样本。
        Args:
            model_output (`torch.Tensor`):
                学习到的扩散模型的直接输出。
            timestep (`int`):
                扩散链中的当前离散时间步。
            sample (`torch.Tensor`):
                扩散过程创建的当前样本实例。
            generator (`torch.Generator`, *optional*):
                随机数生成器。
            variance_noise (`torch.Tensor`):
                替代使用 `generator` 生成噪声，直接提供用于方差本身的噪声。对 [`LEdits++`] 等方法有用。
            return_dict (`bool`):
                是否返回 [`~schedulers.scheduling_utils.SchedulerOutput`] 或 `tuple`。
        Returns:
            [`~schedulers.scheduling_utils.SchedulerOutput`] or `tuple`:
                如果 return_dict 为 `True`，则返回 [`~schedulers.scheduling_utils.SchedulerOutput`]，否则返回一个元组，其中第一个元素是样本张量。
        """
        if self.num_inference_steps is None:
            raise ValueError(
                "Number of inference steps is 'None', you need to run 'set_timesteps' after creating the scheduler"
            )

        if self.step_index is None:
            self._init_step_index(timestep)

        # Improve numerical stability for small number of steps
        lower_order_final = (self.step_index == len(self.timesteps) - 1) and (
            self.config.euler_at_final or
            (self.config.lower_order_final and len(self.timesteps) < 15) or
            self.config.final_sigmas_type == "zero")
        lower_order_second = ((self.step_index == len(self.timesteps) - 2) and
                              self.config.lower_order_final and
                              len(self.timesteps) < 15)

        model_output = self.convert_model_output(model_output, sample=sample)
        for i in range(self.config.solver_order - 1):
            self.model_outputs[i] = self.model_outputs[i + 1]
        self.model_outputs[-1] = model_output

        # Upcast to avoid precision issues when computing prev_sample
        sample = sample.to(torch.float32)
        if self.config.algorithm_type in ["sde-dpmsolver", "sde-dpmsolver++"
                                         ] and variance_noise is None:
            noise = randn_tensor(
                model_output.shape,
                generator=generator,
                device=model_output.device,
                dtype=torch.float32)
        elif self.config.algorithm_type in ["sde-dpmsolver", "sde-dpmsolver++"]:
            noise = variance_noise.to(
                device=model_output.device,
                dtype=torch.float32)  # pyright: ignore
        else:
            noise = None

        if self.config.solver_order == 1 or self.lower_order_nums < 1 or lower_order_final:
            prev_sample = self.dpm_solver_first_order_update(
                model_output, sample=sample, noise=noise)
        elif self.config.solver_order == 2 or self.lower_order_nums < 2 or lower_order_second:
            prev_sample = self.multistep_dpm_solver_second_order_update(
                self.model_outputs, sample=sample, noise=noise)
        else:
            prev_sample = self.multistep_dpm_solver_third_order_update(
                self.model_outputs, sample=sample)

        if self.lower_order_nums < self.config.solver_order:
            self.lower_order_nums += 1

        # Cast sample back to expected dtype
        prev_sample = prev_sample.to(model_output.dtype)

        # upon completion increase step index by one
        self._step_index += 1  # pyright: ignore

        if not return_dict:
            return (prev_sample,)

        return SchedulerOutput(prev_sample=prev_sample)

    # Copied from diffusers.schedulers.scheduling_dpmsolver_multistep.DPMSolverMultistepScheduler.scale_model_input
    def scale_model_input(self, sample: torch.Tensor, *args,
                          **kwargs) -> torch.Tensor:
        """
        确保与需要根据当前时间步缩放去噪模型输入的调度器可互换。
        Args:
            sample (`torch.Tensor`):
                输入样本。
        Returns:
            `torch.Tensor`:
                缩放后的输入样本。
        """
        return sample

    # Copied from diffusers.schedulers.scheduling_dpmsolver_multistep.DPMSolverMultistepScheduler.scale_model_input
    def add_noise(
        self,
        original_samples: torch.Tensor,
        noise: torch.Tensor,
        timesteps: torch.IntTensor,
    ) -> torch.Tensor:
        # Make sure sigmas and timesteps have the same device and dtype as original_samples
        sigmas = self.sigmas.to(
            device=original_samples.device, dtype=original_samples.dtype)
        if original_samples.device.type == "mps" and torch.is_floating_point(
                timesteps):
            # mps does not support float64
            schedule_timesteps = self.timesteps.to(
                original_samples.device, dtype=torch.float32)
            timesteps = timesteps.to(
                original_samples.device, dtype=torch.float32)
        else:
            schedule_timesteps = self.timesteps.to(original_samples.device)
            timesteps = timesteps.to(original_samples.device)

        # begin_index is None when the scheduler is used for training or pipeline does not implement set_begin_index
        if self.begin_index is None:
            step_indices = [
                self.index_for_timestep(t, schedule_timesteps)
                for t in timesteps
            ]
        elif self.step_index is not None:
            # add_noise is called after first denoising step (for inpainting)
            step_indices = [self.step_index] * timesteps.shape[0]
        else:
            # add noise is called before first denoising step to create initial latent(img2img)
            step_indices = [self.begin_index] * timesteps.shape[0]

        sigma = sigmas[step_indices].flatten()
        while len(sigma.shape) < len(original_samples.shape):
            sigma = sigma.unsqueeze(-1)

        alpha_t, sigma_t = self._sigma_to_alpha_sigma_t(sigma)
        noisy_samples = alpha_t * original_samples + sigma_t * noise
        return noisy_samples

    def __len__(self):
        return self.config.num_train_timesteps
