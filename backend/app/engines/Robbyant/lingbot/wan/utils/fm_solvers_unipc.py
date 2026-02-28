# Copied from https://github.com/huggingface/diffusers/blob/v0.31.0/src/diffusers/schedulers/scheduling_unipc_multistep.py
# Convert unipc for flow matching


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

if is_scipy_available():
    import scipy.stats


class FlowUniPCMultistepScheduler(SchedulerMixin, ConfigMixin):
    """
    `UniPCMultistepScheduler` 是一个专为扩散模型快速采样设计的免训练框架。

    该模型继承自 [`SchedulerMixin`] 和 [`ConfigMixin`]。请查看超类文档以了解库为所有调度器实现的通用方法，如加载和保存。

    Args:
        num_train_timesteps (`int`, defaults to 1000):
            训练模型的扩散步数。
        solver_order (`int`, default `2`):
            UniPC 的阶数，可以是任何正整数。由于 UniC 的存在，有效精度阶数为 `solver_order + 1`。
            建议对于引导采样使用 `solver_order=2`，对于无条件采样使用 `solver_order=3`。
        prediction_type (`str`, defaults to "flow_prediction"):
            调度器函数的预测类型；对于此调度器必须是 `flow_prediction`，它预测扩散过程的流。
        thresholding (`bool`, defaults to `False`):
            是否使用 "动态阈值" 方法。这不适用于潜在空间扩散模型，如 Stable Diffusion。
        dynamic_thresholding_ratio (`float`, defaults to 0.995):
            动态阈值方法的比率。仅当 `thresholding=True` 时有效。
        sample_max_value (`float`, defaults to 1.0):
            动态阈值的阈值。仅当 `thresholding=True` 且 `predict_x0=True` 时有效。
        predict_x0 (`bool`, defaults to `True`):
            是否在预测的 x0 上使用更新算法。
        solver_type (`str`, default `bh2`):
            UniPC 的求解器类型。建议当步数 < 10 时对于无条件采样使用 `bh1`，否则使用 `bh2`。
        lower_order_final (`bool`, default `True`):
            是否在最后几步使用低阶求解器。仅对 < 15 推理步数有效。这可以稳定 DPMSolver 在步数 < 15 时的采样，特别是对于步数 <= 10 的情况。
        disable_corrector (`list`, default `[]`):
            决定在哪些步骤禁用校正器，以减轻 `epsilon_theta(x_t, c)` 和 `epsilon_theta(x_t^c, c)` 之间的不对齐，这可能会影响大引导比例下的收敛。
            通常在最初的几步禁用校正器。
        solver_p (`SchedulerMixin`, default `None`):
            任何其他调度器，如果指定，算法变为 `solver_p + UniC`。
        use_karras_sigmas (`bool`, *optional*, defaults to `False`):
            是否在采样过程中使用 Karras sigmas 作为噪声计划的步长。如果为 `True`，sigmas 将根据噪声水平序列 {σi} 确定。
        use_exponential_sigmas (`bool`, *optional*, defaults to `False`):
            是否在采样过程中使用指数 sigmas 作为噪声计划的步长。
        timestep_spacing (`str`, defaults to `"linspace"`):
            时间步的缩放方式。有关更多信息，请参阅 [Common Diffusion Noise Schedules and Sample Steps are Flawed](https://huggingface.co/papers/2305.08891) 的表 2。
        steps_offset (`int`, defaults to 0):
            添加到推理步骤的偏移量，某些模型系列需要。
        final_sigmas_type (`str`, defaults to `"zero"`):
            采样过程中噪声计划的最终 `sigma` 值。如果为 `"sigma_min"`，最终 sigma 与训练计划中的最后一个 sigma 相同。如果为 `zero`，最终 sigma 设置为 0。
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
            predict_x0: bool = True,
            solver_type: str = "bh2",
            lower_order_final: bool = True,
            disable_corrector: List[int] = [],
            solver_p: SchedulerMixin = None,
            timestep_spacing: str = "linspace",
            steps_offset: int = 0,
            final_sigmas_type: Optional[str] = "zero",  # "zero", "sigma_min"
    ):

        if solver_type not in ["bh1", "bh2"]:
            if solver_type in ["midpoint", "heun", "logrho"]:
                self.register_to_config(solver_type="bh2")
            else:
                raise NotImplementedError(
                    f"{solver_type} is not implemented for {self.__class__}")

        self.predict_x0 = predict_x0
        # setable values
        self.num_inference_steps = None
        alphas = np.linspace(1, 1 / num_train_timesteps,
                             num_train_timesteps)[::-1].copy()
        sigmas = 1.0 - alphas
        sigmas = torch.from_numpy(sigmas).to(dtype=torch.float32)

        if not use_dynamic_shifting:
            # 当 use_dynamic_shifting 为 True 时，我们根据图像分辨率动态应用时间步移位
            sigmas = shift * sigmas / (1 +
                                       (shift - 1) * sigmas)  # pyright: ignore

        self.sigmas = sigmas
        self.timesteps = sigmas * num_train_timesteps

        self.model_outputs = [None] * solver_order
        self.timestep_list = [None] * solver_order
        self.lower_order_nums = 0
        self.disable_corrector = disable_corrector
        self.solver_p = solver_p
        self.last_sample = None
        self._step_index = None
        self._begin_index = None

        self.sigmas = self.sigmas.to(
            "cpu")  # to avoid too much CPU/GPU communication
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
        self.last_sample = None
        if self.solver_p:
            self.solver_p.set_timesteps(self.num_inference_steps, device=device)

        # 添加索引计数器，用于允许重复时间步的调度器
        self._step_index = None
        self._begin_index = None
        self.sigmas = self.sigmas.to(
            "cpu")  # to avoid too much CPU/GPU communication

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

    def convert_model_output(
        self,
        model_output: torch.Tensor,
        *args,
        sample: torch.Tensor = None,
        **kwargs,
    ) -> torch.Tensor:
        r"""
        将模型输出转换为 UniPC 算法所需的相应类型。

        Args:
            model_output (`torch.Tensor`):
                学习到的扩散模型的直接输出。
            timestep (`int`):
                扩散链中的当前离散时间步。
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

        sigma = self.sigmas[self.step_index]
        alpha_t, sigma_t = self._sigma_to_alpha_sigma_t(sigma)

        if self.predict_x0:
            if self.config.prediction_type == "flow_prediction":
                sigma_t = self.sigmas[self.step_index]
                x0_pred = sample - sigma_t * model_output
            else:
                raise ValueError(
                    f"prediction_type given as {self.config.prediction_type} must be one of `epsilon`, `sample`,"
                    " `v_prediction` or `flow_prediction` for the UniPCMultistepScheduler."
                )

            if self.config.thresholding:
                x0_pred = self._threshold_sample(x0_pred)

            return x0_pred
        else:
            if self.config.prediction_type == "flow_prediction":
                sigma_t = self.sigmas[self.step_index]
                epsilon = sample - (1 - sigma_t) * model_output
            else:
                raise ValueError(
                    f"prediction_type given as {self.config.prediction_type} must be one of `epsilon`, `sample`,"
                    " `v_prediction` or `flow_prediction` for the UniPCMultistepScheduler."
                )

            if self.config.thresholding:
                sigma_t = self.sigmas[self.step_index]
                x0_pred = sample - sigma_t * model_output
                x0_pred = self._threshold_sample(x0_pred)
                epsilon = model_output + x0_pred

            return epsilon

    def multistep_uni_p_bh_update(
        self,
        model_output: torch.Tensor,
        *args,
        sample: torch.Tensor = None,
        order: int = None,  # pyright: ignore
        **kwargs,
    ) -> torch.Tensor:
        """
        UniP (B(h) 版本) 的一步。如果指定了 `self.solver_p`，则使用它。

        Args:
            model_output (`torch.Tensor`):
                当前时间步学习到的扩散模型的直接输出。
            prev_timestep (`int`):
                扩散链中的上一个离散时间步。
            sample (`torch.Tensor`):
                扩散过程创建的当前样本实例。
            order (`int`):
                此时间步的 UniP 阶数 (对应于 UniPC-p 中的 *p*)。

        Returns:
            `torch.Tensor`:
                上一个时间步的样本张量。
        """
        prev_timestep = args[0] if len(args) > 0 else kwargs.pop(
            "prev_timestep", None)
        if sample is None:
            if len(args) > 1:
                sample = args[1]
            else:
                raise ValueError(
                    " missing `sample` as a required keyward argument")
        if order is None:
            if len(args) > 2:
                order = args[2]
            else:
                raise ValueError(
                    " missing `order` as a required keyward argument")
        if prev_timestep is not None:
            deprecate(
                "prev_timestep",
                "1.0.0",
                "Passing `prev_timestep` is deprecated and has no effect as model output conversion is now handled via an internal counter `self.step_index`",
            )
        model_output_list = self.model_outputs

        s0 = self.timestep_list[-1]
        m0 = model_output_list[-1]
        x = sample

        if self.solver_p:
            x_t = self.solver_p.step(model_output, s0, x).prev_sample
            return x_t

        sigma_t, sigma_s0 = self.sigmas[self.step_index + 1], self.sigmas[
            self.step_index]  # pyright: ignore
        alpha_t, sigma_t = self._sigma_to_alpha_sigma_t(sigma_t)
        alpha_s0, sigma_s0 = self._sigma_to_alpha_sigma_t(sigma_s0)

        lambda_t = torch.log(alpha_t) - torch.log(sigma_t)
        lambda_s0 = torch.log(alpha_s0) - torch.log(sigma_s0)

        h = lambda_t - lambda_s0
        device = sample.device

        rks = []
        D1s = []
        for i in range(1, order):
            si = self.step_index - i  # pyright: ignore
            mi = model_output_list[-(i + 1)]
            alpha_si, sigma_si = self._sigma_to_alpha_sigma_t(self.sigmas[si])
            lambda_si = torch.log(alpha_si) - torch.log(sigma_si)
            rk = (lambda_si - lambda_s0) / h
            rks.append(rk)
            D1s.append((mi - m0) / rk)  # pyright: ignore

        rks.append(1.0)
        rks = torch.tensor(rks, device=device)

        R = []
        b = []

        hh = -h if self.predict_x0 else h
        h_phi_1 = torch.expm1(hh)  # h\phi_1(h) = e^h - 1
        h_phi_k = h_phi_1 / hh - 1

        factorial_i = 1

        if self.config.solver_type == "bh1":
            B_h = hh
        elif self.config.solver_type == "bh2":
            B_h = torch.expm1(hh)
        else:
            raise NotImplementedError()

        for i in range(1, order + 1):
            R.append(torch.pow(rks, i - 1))
            b.append(h_phi_k * factorial_i / B_h)
            factorial_i *= i + 1
            h_phi_k = h_phi_k / hh - 1 / factorial_i

        R = torch.stack(R)
        b = torch.tensor(b, device=device)

        if len(D1s) > 0:
            D1s = torch.stack(D1s, dim=1)  # (B, K)
            # for order 2, we use a simplified version
            if order == 2:
                rhos_p = torch.tensor([0.5], dtype=x.dtype, device=device)
            else:
                rhos_p = torch.linalg.solve(R[:-1, :-1],
                                            b[:-1]).to(device).to(x.dtype)
        else:
            D1s = None

        if self.predict_x0:
            x_t_ = sigma_t / sigma_s0 * x - alpha_t * h_phi_1 * m0
            if D1s is not None:
                pred_res = torch.einsum("k,bkc...->bc...", rhos_p,
                                        D1s)  # pyright: ignore
            else:
                pred_res = 0
            x_t = x_t_ - alpha_t * B_h * pred_res
        else:
            x_t_ = alpha_t / alpha_s0 * x - sigma_t * h_phi_1 * m0
            if D1s is not None:
                pred_res = torch.einsum("k,bkc...->bc...", rhos_p,
                                        D1s)  # pyright: ignore
            else:
                pred_res = 0
            x_t = x_t_ - sigma_t * B_h * pred_res

        x_t = x_t.to(x.dtype)
        return x_t

    def multistep_uni_c_bh_update(
        self,
        this_model_output: torch.Tensor,
        *args,
        last_sample: torch.Tensor = None,
        this_sample: torch.Tensor = None,
        order: int = None,  # pyright: ignore
        **kwargs,
    ) -> torch.Tensor:
        """
        UniC (B(h) 版本) 的一步。

        Args:
            this_model_output (`torch.Tensor`):
                `x_t` 处的模型输出。
            this_timestep (`int`):
                当前时间步 `t`。
            last_sample (`torch.Tensor`):
                上一个预测器 `x_{t-1}` 之前生成的样本。
            this_sample (`torch.Tensor`):
                上一个预测器 `x_{t}` 之后生成的样本。
            order (`int`):
                此步骤的 UniC-p 的 `p`。有效精度阶数应为 `order + 1`。

        Returns:
            `torch.Tensor`:
                当前时间步的校正后样本张量。
        """
        this_timestep = args[0] if len(args) > 0 else kwargs.pop(
            "this_timestep", None)
        if last_sample is None:
            if len(args) > 1:
                last_sample = args[1]
            else:
                raise ValueError(
                    " missing`last_sample` as a required keyward argument")
        if this_sample is None:
            if len(args) > 2:
                this_sample = args[2]
            else:
                raise ValueError(
                    " missing`this_sample` as a required keyward argument")
        if order is None:
            if len(args) > 3:
                order = args[3]
            else:
                raise ValueError(
                    " missing`order` as a required keyward argument")
        if this_timestep is not None:
            deprecate(
                "this_timestep",
                "1.0.0",
                "Passing `this_timestep` is deprecated and has no effect as model output conversion is now handled via an internal counter `self.step_index`",
            )

        model_output_list = self.model_outputs

        m0 = model_output_list[-1]
        x = last_sample
        x_t = this_sample
        model_t = this_model_output

        sigma_t, sigma_s0 = self.sigmas[self.step_index], self.sigmas[
            self.step_index - 1]  # pyright: ignore
        alpha_t, sigma_t = self._sigma_to_alpha_sigma_t(sigma_t)
        alpha_s0, sigma_s0 = self._sigma_to_alpha_sigma_t(sigma_s0)

        lambda_t = torch.log(alpha_t) - torch.log(sigma_t)
        lambda_s0 = torch.log(alpha_s0) - torch.log(sigma_s0)

        h = lambda_t - lambda_s0
        device = this_sample.device

        rks = []
        D1s = []
        for i in range(1, order):
            si = self.step_index - (i + 1)  # pyright: ignore
            mi = model_output_list[-(i + 1)]
            alpha_si, sigma_si = self._sigma_to_alpha_sigma_t(self.sigmas[si])
            lambda_si = torch.log(alpha_si) - torch.log(sigma_si)
            rk = (lambda_si - lambda_s0) / h
            rks.append(rk)
            D1s.append((mi - m0) / rk)  # pyright: ignore

        rks.append(1.0)
        rks = torch.tensor(rks, device=device)

        R = []
        b = []

        hh = -h if self.predict_x0 else h
        h_phi_1 = torch.expm1(hh)  # h\phi_1(h) = e^h - 1
        h_phi_k = h_phi_1 / hh - 1

        factorial_i = 1

        if self.config.solver_type == "bh1":
            B_h = hh
        elif self.config.solver_type == "bh2":
            B_h = torch.expm1(hh)
        else:
            raise NotImplementedError()

        for i in range(1, order + 1):
            R.append(torch.pow(rks, i - 1))
            b.append(h_phi_k * factorial_i / B_h)
            factorial_i *= i + 1
            h_phi_k = h_phi_k / hh - 1 / factorial_i

        R = torch.stack(R)
        b = torch.tensor(b, device=device)

        if len(D1s) > 0:
            D1s = torch.stack(D1s, dim=1)
        else:
            D1s = None

        # for order 1, we use a simplified version
        if order == 1:
            rhos_c = torch.tensor([0.5], dtype=x.dtype, device=device)
        else:
            rhos_c = torch.linalg.solve(R, b).to(device).to(x.dtype)

        if self.predict_x0:
            x_t_ = sigma_t / sigma_s0 * x - alpha_t * h_phi_1 * m0
            if D1s is not None:
                corr_res = torch.einsum("k,bkc...->bc...", rhos_c[:-1], D1s)
            else:
                corr_res = 0
            D1_t = model_t - m0
            x_t = x_t_ - alpha_t * B_h * (corr_res + rhos_c[-1] * D1_t)
        else:
            x_t_ = alpha_t / alpha_s0 * x - sigma_t * h_phi_1 * m0
            if D1s is not None:
                corr_res = torch.einsum("k,bkc...->bc...", rhos_c[:-1], D1s)
            else:
                corr_res = 0
            D1_t = model_t - m0
            x_t = x_t_ - sigma_t * B_h * (corr_res + rhos_c[-1] * D1_t)
        x_t = x_t.to(x.dtype)
        return x_t

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

    # Copied from diffusers.schedulers.scheduling_dpmsolver_multistep.DPMSolverMultistepScheduler._init_step_index
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

    def step(self,
             model_output: torch.Tensor,
             timestep: Union[int, torch.Tensor],
             sample: torch.Tensor,
             return_dict: bool = True,
             generator=None) -> Union[SchedulerOutput, Tuple]:
        """
        通过反转 SDE 预测上一个时间步的样本。此函数使用多步 UniPC 传播样本。

        Args:
            model_output (`torch.Tensor`):
                学习到的扩散模型的直接输出。
            timestep (`int`):
                扩散链中的当前离散时间步。
            sample (`torch.Tensor`):
                扩散过程创建的当前样本实例。
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

        use_corrector = (
            self.step_index > 0 and
            self.step_index - 1 not in self.disable_corrector and
            self.last_sample is not None  # pyright: ignore
        )

        model_output_convert = self.convert_model_output(
            model_output, sample=sample)
        if use_corrector:
            sample = self.multistep_uni_c_bh_update(
                this_model_output=model_output_convert,
                last_sample=self.last_sample,
                this_sample=sample,
                order=self.this_order,
            )

        for i in range(self.config.solver_order - 1):
            self.model_outputs[i] = self.model_outputs[i + 1]
            self.timestep_list[i] = self.timestep_list[i + 1]

        self.model_outputs[-1] = model_output_convert
        self.timestep_list[-1] = timestep  # pyright: ignore

        if self.config.lower_order_final:
            this_order = min(self.config.solver_order,
                             len(self.timesteps) -
                             self.step_index)  # pyright: ignore
        else:
            this_order = self.config.solver_order

        self.this_order = min(this_order,
                              self.lower_order_nums + 1)  # warmup for multistep
        assert self.this_order > 0

        self.last_sample = sample
        prev_sample = self.multistep_uni_p_bh_update(
            model_output=model_output,  # pass the original non-converted model output, in case solver-p is used
            sample=sample,
            order=self.this_order,
        )

        if self.lower_order_nums < self.config.solver_order:
            self.lower_order_nums += 1

        # upon completion increase step index by one
        self._step_index += 1  # pyright: ignore

        if not return_dict:
            return (prev_sample,)

        return SchedulerOutput(prev_sample=prev_sample)

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

    # Copied from diffusers.schedulers.scheduling_dpmsolver_multistep.DPMSolverMultistepScheduler.add_noise
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
