import math
from einops import rearrange

import torch
import torch.nn as nn
import torch.nn.functional as torch_F
from diffusers.configuration_utils import ConfigMixin, register_to_config
from diffusers.models.modeling_utils import ModelMixin

from .attention import attention

__all__ = ['WanModel']


def sinusoidal_embedding_1d(dim, position):
    # 预处理
    assert dim % 2 == 0
    half = dim // 2
    position = position.type(torch.float64)

    # 计算
    sinusoid = torch.outer(
        position, torch.pow(10000, -torch.arange(half).to(position).div(half)))
    x = torch.cat([torch.cos(sinusoid), torch.sin(sinusoid)], dim=1)
    return x


@torch.amp.autocast('cuda', enabled=False)
def rope_params(max_seq_len, dim, theta=10000):
    assert dim % 2 == 0
    freqs = torch.outer(
        torch.arange(max_seq_len),
        1.0 / torch.pow(theta,
                        torch.arange(0, dim, 2).to(torch.float64).div(dim)))
    freqs = torch.polar(torch.ones_like(freqs), freqs)
    return freqs


@torch.amp.autocast('cuda', enabled=False)
def rope_apply(x, grid_sizes, freqs):
    n, c = x.size(2), x.size(3) // 2

    # 分割频率
    freqs = freqs.split([c - 2 * (c // 3), c // 3, c // 3], dim=1)

    # 遍历样本
    output = []
    for i, (f, h, w) in enumerate(grid_sizes.tolist()):
        seq_len = f * h * w

        # 预计算乘数
        x_i = torch.view_as_complex(x[i, :seq_len].to(torch.float64).reshape(
            seq_len, n, -1, 2))
        freqs_i = torch.cat([
            freqs[0][:f].view(f, 1, 1, -1).expand(f, h, w, -1),
            freqs[1][:h].view(1, h, 1, -1).expand(f, h, w, -1),
            freqs[2][:w].view(1, 1, w, -1).expand(f, h, w, -1)
        ],
                            dim=-1).reshape(seq_len, 1, -1)

        # 应用旋转位置编码 (RoPE)
        x_i = torch.view_as_real(x_i * freqs_i).flatten(2)
        x_i = torch.cat([x_i, x[i, seq_len:]])

        # 添加到集合
        output.append(x_i)
    return torch.stack(output).float()


class WanRMSNorm(nn.Module):

    def __init__(self, dim, eps=1e-5):
        super().__init__()
        self.dim = dim
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x):
        r"""
        Args:
            x(Tensor): 形状 [B, L, C]
        """
        return self._norm(x.float()).type_as(x) * self.weight

    def _norm(self, x):
        return x * torch.rsqrt(x.pow(2).mean(dim=-1, keepdim=True) + self.eps)


class WanLayerNorm(nn.LayerNorm):

    def __init__(self, dim, eps=1e-6, elementwise_affine=False):
        super().__init__(dim, elementwise_affine=elementwise_affine, eps=eps)

    def forward(self, x):
        r"""
        Args:
            x(Tensor): 形状 [B, L, C]
        """
        return super().forward(x.float()).type_as(x)


class WanSelfAttention(nn.Module):

    def __init__(self,
                 dim,
                 num_heads,
                 window_size=(-1, -1),
                 qk_norm=True,
                 eps=1e-6):
        assert dim % num_heads == 0
        super().__init__()
        self.dim = dim
        self.num_heads = num_heads
        self.head_dim = dim // num_heads
        self.window_size = window_size
        self.qk_norm = qk_norm
        self.eps = eps

        # 层
        self.q = nn.Linear(dim, dim)
        self.k = nn.Linear(dim, dim)
        self.v = nn.Linear(dim, dim)
        self.o = nn.Linear(dim, dim)
        self.norm_q = WanRMSNorm(dim, eps=eps) if qk_norm else nn.Identity()
        self.norm_k = WanRMSNorm(dim, eps=eps) if qk_norm else nn.Identity()

    def forward(self, x, seq_lens, grid_sizes, freqs):
        r"""
        Args:
            x(Tensor): 形状 [B, L, num_heads, C / num_heads]
            seq_lens(Tensor): 形状 [B]
            grid_sizes(Tensor): 形状 [B, 3], 第二维包含 (F, H, W)
            freqs(Tensor): Rope 频率, 形状 [1024, C / num_heads / 2]
        """
        b, s, n, d = *x.shape[:2], self.num_heads, self.head_dim

        # QKV计算函数
        def qkv_fn(x):
            q = self.norm_q(self.q(x)).view(b, s, n, d)
            k = self.norm_k(self.k(x)).view(b, s, n, d)
            v = self.v(x).view(b, s, n, d)
            return q, k, v

        q, k, v = qkv_fn(x)

        x = attention(
            q=rope_apply(q, grid_sizes, freqs),
            k=rope_apply(k, grid_sizes, freqs),
            v=v,
            k_lens=seq_lens,
            window_size=self.window_size)

        # 输出
        x = x.flatten(2)
        x = self.o(x)
        return x


class WanCrossAttention(WanSelfAttention):

    def forward(self, x, context, context_lens):
        r"""
        Args:
            x(Tensor): 形状 [B, L1, C]
            context(Tensor): 形状 [B, L2, C]
            context_lens(Tensor): 形状 [B]
        """
        b, n, d = x.size(0), self.num_heads, self.head_dim

        # 计算Query, Key, Value
        q = self.norm_q(self.q(x)).view(b, -1, n, d)
        k = self.norm_k(self.k(context)).view(b, -1, n, d)
        v = self.v(context).view(b, -1, n, d)

        # 计算注意力
        x = attention(q, k, v, k_lens=context_lens)

        # 输出
        x = x.flatten(2)
        x = self.o(x)
        return x


class WanAttentionBlock(nn.Module):

    def __init__(self,
                 dim,
                 ffn_dim,
                 num_heads,
                 window_size=(-1, -1),
                 qk_norm=True,
                 cross_attn_norm=False,
                 eps=1e-6):
        super().__init__()
        self.dim = dim
        self.ffn_dim = ffn_dim
        self.num_heads = num_heads
        self.window_size = window_size
        self.qk_norm = qk_norm
        self.cross_attn_norm = cross_attn_norm
        self.eps = eps

        # 层
        self.norm1 = WanLayerNorm(dim, eps)
        self.self_attn = WanSelfAttention(dim, num_heads, window_size, qk_norm,
                                          eps)
        self.norm3 = WanLayerNorm(
            dim, eps,
            elementwise_affine=True) if cross_attn_norm else nn.Identity()
        self.cross_attn = WanCrossAttention(dim, num_heads, (-1, -1), qk_norm,
                                            eps)
        self.norm2 = WanLayerNorm(dim, eps)
        self.ffn = nn.Sequential(
            nn.Linear(dim, ffn_dim), nn.GELU(approximate='tanh'),
            nn.Linear(ffn_dim, dim))

        # 调制
        self.modulation = nn.Parameter(torch.randn(1, 6, dim) / dim**0.5)

        self.cam_injector_layer1 = nn.Linear(dim, dim)
        self.cam_injector_layer2 = nn.Linear(dim, dim)
        self.cam_scale_layer = nn.Linear(dim, dim)
        self.cam_shift_layer = nn.Linear(dim, dim)

    def forward(
        self,
        x,
        e,
        seq_lens,
        grid_sizes,
        freqs,
        context,
        context_lens,
        dit_cond_dict=None,
    ):
        r"""
        Args:
            x(Tensor): 形状 [B, L, C]
            e(Tensor): 形状 [B, L1, 6, C]
            seq_lens(Tensor): 形状 [B], 批次中每个序列的长度
            grid_sizes(Tensor): 形状 [B, 3], 第二维包含 (F, H, W)
            freqs(Tensor): Rope 频率, 形状 [1024, C / num_heads / 2]
        """
        assert e.dtype == torch.float32
        with torch.amp.autocast('cuda', dtype=torch.float32):
            e = (self.modulation.unsqueeze(0) + e).chunk(6, dim=2)
        assert e[0].dtype == torch.float32

        # 自注意力
        y = self.self_attn(
            self.norm1(x).float() * (1 + e[1].squeeze(2)) + e[0].squeeze(2),
            seq_lens, grid_sizes, freqs)
        with torch.amp.autocast('cuda', dtype=torch.float32):
            x = x + y * e[2].squeeze(2)

        # CAM注入 (仅当提供dit_cond_dict且包含c2ws_plucker_emb时)
        if dit_cond_dict is not None and "c2ws_plucker_emb" in dit_cond_dict:
            c2ws_plucker_emb = dit_cond_dict["c2ws_plucker_emb"]
            c2ws_hidden_states = self.cam_injector_layer2(torch_F.silu(self.cam_injector_layer1(c2ws_plucker_emb)))
            c2ws_hidden_states = c2ws_hidden_states + c2ws_plucker_emb
            cam_scale = self.cam_scale_layer(c2ws_hidden_states)
            cam_shift = self.cam_shift_layer(c2ws_hidden_states)
            x = (1.0 + cam_scale) * x + cam_shift

        # 交叉注意力与FFN函数
        def cross_attn_ffn(x, context, context_lens, e):
            x = x + self.cross_attn(self.norm3(x), context, context_lens)
            y = self.ffn(
                self.norm2(x).float() * (1 + e[4].squeeze(2)) + e[3].squeeze(2))
            with torch.amp.autocast('cuda', dtype=torch.float32):
                x = x + y * e[5].squeeze(2)
            return x

        x = cross_attn_ffn(x, context, context_lens, e)
        return x


class Head(nn.Module):

    def __init__(self, dim, out_dim, patch_size, eps=1e-6):
        super().__init__()
        self.dim = dim
        self.out_dim = out_dim
        self.patch_size = patch_size
        self.eps = eps

        # 层
        out_dim = math.prod(patch_size) * out_dim
        self.norm = WanLayerNorm(dim, eps)
        self.head = nn.Linear(dim, out_dim)

        # 调制
        self.modulation = nn.Parameter(torch.randn(1, 2, dim) / dim**0.5)

    def forward(self, x, e):
        r"""
        Args:
            x(Tensor): 形状 [B, L1, C]
            e(Tensor): 形状 [B, L1, C]
        """
        assert e.dtype == torch.float32
        with torch.amp.autocast('cuda', dtype=torch.float32):
            e = (self.modulation.unsqueeze(0) + e.unsqueeze(2)).chunk(2, dim=2)
            x = (
                self.head(
                    self.norm(x) * (1 + e[1].squeeze(2)) + e[0].squeeze(2)))
        return x


class WanModel(ModelMixin, ConfigMixin):
    r"""
    Wan扩散模型骨干网络，支持文生视频和图生视频。
    """

    ignore_for_config = [
        'patch_size', 'cross_attn_norm', 'qk_norm', 'text_dim', 'window_size'
    ]
    _no_split_modules = ['WanAttentionBlock']

    @register_to_config
    def __init__(self,
                 model_type='t2v',
                 patch_size=(1, 2, 2),
                 text_len=512,
                 in_dim=16,
                 dim=2048,
                 ffn_dim=8192,
                 freq_dim=256,
                 text_dim=4096,
                 out_dim=16,
                 num_heads=16,
                 num_layers=32,
                 window_size=(-1, -1),
                 qk_norm=True,
                 cross_attn_norm=True,
                 eps=1e-6):
        r"""
        初始化扩散模型骨干网络。

        Args:
            model_type (`str`, *optional*, defaults to 't2v'):
                模型变体 - 't2v' (文生视频) 或 'i2v' (图生视频)
            patch_size (`tuple`, *optional*, defaults to (1, 2, 2)):
                视频嵌入的3D Patch维度 (t_patch, h_patch, w_patch)
            text_len (`int`, *optional*, defaults to 512):
                文本嵌入的固定长度
            in_dim (`int`, *optional*, defaults to 16):
                输入视频通道数 (C_in)
            dim (`int`, *optional*, defaults to 2048):
                Transformer的隐藏层维度
            ffn_dim (`int`, *optional*, defaults to 8192):
                前馈网络中的中间维度
            freq_dim (`int`, *optional*, defaults to 256):
                正弦时间嵌入的维度
            text_dim (`int`, *optional*, defaults to 4096):
                文本嵌入的输入维度
            out_dim (`int`, *optional*, defaults to 16):
                输出视频通道数 (C_out)
            num_heads (`int`, *optional*, defaults to 16):
                注意力头的数量
            num_layers (`int`, *optional*, defaults to 32):
                Transformer块的数量
            window_size (`tuple`, *optional*, defaults to (-1, -1)):
                局部注意力的窗口大小 (-1 表示全局注意力)
            qk_norm (`bool`, *optional*, defaults to True):
                是否启用Query/Key归一化
            cross_attn_norm (`bool`, *optional*, defaults to False):
                是否启用交叉注意力归一化
            eps (`float`, *optional*, defaults to 1e-6):
                归一化层的epsilon值
        """

        super().__init__()

        assert model_type in ['t2v', 'i2v', 'ti2v', 's2v']
        self.model_type = model_type

        self.patch_size = patch_size
        self.text_len = text_len
        self.in_dim = in_dim
        self.dim = dim
        self.ffn_dim = ffn_dim
        self.freq_dim = freq_dim
        self.text_dim = text_dim
        self.out_dim = out_dim
        self.num_heads = num_heads
        self.num_layers = num_layers
        self.window_size = window_size
        self.qk_norm = qk_norm
        self.cross_attn_norm = cross_attn_norm
        self.eps = eps

        # 嵌入层
        self.patch_embedding = nn.Conv3d(
            in_dim, dim, kernel_size=patch_size, stride=patch_size)
        self.patch_embedding_wancamctrl = nn.Linear(
            6 * 64 * patch_size[0] * patch_size[1] * patch_size[2], dim)
        self.c2ws_hidden_states_layer1 = nn.Linear(dim, dim)
        self.c2ws_hidden_states_layer2 = nn.Linear(dim, dim)
        self.text_embedding = nn.Sequential(
            nn.Linear(text_dim, dim), nn.GELU(approximate='tanh'),
            nn.Linear(dim, dim))

        self.time_embedding = nn.Sequential(
            nn.Linear(freq_dim, dim), nn.SiLU(), nn.Linear(dim, dim))
        self.time_projection = nn.Sequential(nn.SiLU(), nn.Linear(dim, dim * 6))

        # 模块块
        self.blocks = nn.ModuleList([
            WanAttentionBlock(dim, ffn_dim, num_heads, window_size, qk_norm,
                              cross_attn_norm, eps) for _ in range(num_layers)
        ])

        # 输出头
        self.head = Head(dim, out_dim, patch_size, eps)

        # 缓冲区 (不要使用register_buffer，否则在to()时dtype会被改变)
        assert (dim % num_heads) == 0 and (dim // num_heads) % 2 == 0
        d = dim // num_heads
        self.freqs = torch.cat([
            rope_params(1024, d - 4 * (d // 6)),
            rope_params(1024, 2 * (d // 6)),
            rope_params(1024, 2 * (d // 6))
        ],
                               dim=1)

        # 初始化权重
        self.init_weights()

    def forward(
        self,
        x,
        t,
        context,
        seq_len,
        y=None,
        dit_cond_dict=None,
    ):
        r"""
        扩散模型的前向传播

        Args:
            x (List[Tensor]):
                输入视频张量列表，每个形状为 [C_in, F, H, W]
            t (Tensor):
                扩散时间步张量，形状为 [B]
            context (List[Tensor]):
                文本嵌入列表，每个形状为 [L, C]
            seq_len (`int`):
                位置编码的最大序列长度
            y (List[Tensor], *optional*):
                图生视频模式的条件视频输入，形状与 x 相同

        Returns:
            List[Tensor]:
                去噪后的视频张量列表，具有原始输入形状 [C_out, F, H / 8, W / 8]
        """
        if self.model_type == 'i2v':
            assert y is not None
        # 参数
        device = self.patch_embedding.weight.device
        if self.freqs.device != device:
            self.freqs = self.freqs.to(device)

        if y is not None:
            x = [torch.cat([u, v], dim=0) for u, v in zip(x, y)]

        # 嵌入层
        x = [self.patch_embedding(u.unsqueeze(0)) for u in x]
        grid_sizes = torch.stack(
            [torch.tensor(u.shape[2:], dtype=torch.long) for u in x])
        x = [u.flatten(2).transpose(1, 2) for u in x]
        seq_lens = torch.tensor([u.size(1) for u in x], dtype=torch.long)
        assert seq_lens.max() <= seq_len
        x = torch.cat([
            torch.cat([u, u.new_zeros(1, seq_len - u.size(1), u.size(2))],
                      dim=1) for u in x
        ])

        # 时间嵌入
        if t.dim() == 1:
            t = t.expand(t.size(0), seq_len)
        with torch.amp.autocast('cuda', dtype=torch.float32):
            bt = t.size(0)
            t = t.flatten()
            e = self.time_embedding(
                sinusoidal_embedding_1d(self.freq_dim,
                                        t).unflatten(0, (bt, seq_len)).float())
            e0 = self.time_projection(e).unflatten(2, (6, self.dim))
            assert e.dtype == torch.float32 and e0.dtype == torch.float32

        # 上下文
        context_lens = None
        context = self.text_embedding(
            torch.stack([
                torch.cat(
                    [u, u.new_zeros(self.text_len - u.size(0), u.size(1))])
                for u in context
            ]))
        
        # CAM (相机控制)
        if dit_cond_dict is not None and "c2ws_plucker_emb" in dit_cond_dict:
            c2ws_plucker_emb = dit_cond_dict["c2ws_plucker_emb"]
            c2ws_plucker_emb = [
                rearrange(
                    i,
                    '1 c (f c1) (h c2) (w c3) -> 1 (f h w) (c c1 c2 c3)',
                    c1=self.patch_size[0],
                    c2=self.patch_size[1],
                    c3=self.patch_size[2],
                ) for i in c2ws_plucker_emb
            ]
            c2ws_plucker_emb = torch.cat(
                c2ws_plucker_emb, dim=1)  # [1, (L1+...+Ln), C]
            c2ws_plucker_emb = self.patch_embedding_wancamctrl(
                c2ws_plucker_emb)
            c2ws_hidden_states = self.c2ws_hidden_states_layer2(
                torch_F.silu(self.c2ws_hidden_states_layer1(c2ws_plucker_emb)))
            dit_cond_dict = dict(dit_cond_dict)
            dit_cond_dict["c2ws_plucker_emb"] = (
                c2ws_plucker_emb + c2ws_hidden_states)

        # 参数字典
        kwargs = dict(
            e=e0,
            seq_lens=seq_lens,
            grid_sizes=grid_sizes,
            freqs=self.freqs,
            context=context,
            context_lens=context_lens,
            dit_cond_dict=dit_cond_dict)

        for block in self.blocks:
            x = block(x, **kwargs)

        # 输出头
        x = self.head(x, e)

        # 反Patch化
        x = self.unpatchify(x, grid_sizes)
        return [u.float() for u in x]

    def unpatchify(self, x, grid_sizes):
        r"""
        从Patch嵌入重建视频张量。

        Args:
            x (List[Tensor]):
                Patch化特征列表，每个形状为 [L, C_out * prod(patch_size)]
            grid_sizes (Tensor):
                Patch化前的原始时空网格维度，
                    形状 [B, 3] (3个维度分别对应 F_patches, H_patches, W_patches)

        Returns:
            List[Tensor]:
                重建的视频张量，形状 [C_out, F, H / 8, W / 8]
        """

        c = self.out_dim
        out = []
        for u, v in zip(x, grid_sizes.tolist()):
            u = u[:math.prod(v)].view(*v, *self.patch_size, c)
            u = torch.einsum('fhwpqrc->cfphqwr', u)
            u = u.reshape(c, *[i * j for i, j in zip(v, self.patch_size)])
            out.append(u)
        return out

    def init_weights(self):
        r"""
        使用Xavier初始化模型参数。
        """

        # 基础初始化
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

        # 初始化嵌入层
        nn.init.xavier_uniform_(self.patch_embedding.weight.flatten(1))
        for m in self.text_embedding.modules():
            if isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, std=.02)
        for m in self.time_embedding.modules():
            if isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, std=.02)

        # 初始化输出层
        nn.init.zeros_(self.head.head.weight)

        # 初始化CAM控制层
        nn.init.xavier_uniform_(self.patch_embedding_wancamctrl.weight)
        nn.init.zeros_(self.patch_embedding_wancamctrl.bias)
        nn.init.xavier_uniform_(self.c2ws_hidden_states_layer1.weight)
        nn.init.zeros_(self.c2ws_hidden_states_layer1.bias)
        nn.init.xavier_uniform_(self.c2ws_hidden_states_layer2.weight)
        nn.init.zeros_(self.c2ws_hidden_states_layer2.bias)

        # 初始化模块块中的CAM注入层
        for block in self.blocks:
            nn.init.xavier_uniform_(block.cam_injector_layer1.weight)
            nn.init.zeros_(block.cam_injector_layer1.bias)
            nn.init.xavier_uniform_(block.cam_injector_layer2.weight)
            nn.init.zeros_(block.cam_injector_layer2.bias)
            nn.init.xavier_uniform_(block.cam_scale_layer.weight)
            nn.init.zeros_(block.cam_scale_layer.bias)
            nn.init.xavier_uniform_(block.cam_shift_layer.weight)
            nn.init.zeros_(block.cam_shift_layer.bias)
