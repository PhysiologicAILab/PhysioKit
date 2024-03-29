import numpy as np
from torch import nn
import torch.nn.functional as F
import torch
from torch.nn.modules.batchnorm import _BatchNorm


class _MatrixDecomposition1DBase(nn.Module):
    def __init__(self, device, model_config):
        super().__init__()

        self.S = model_config["model_params"]["MD_S"]
        self.D = model_config["model_params"]["MD_D"]
        self.R = model_config["model_params"]["MD_R"]

        self.train_steps = model_config["model_params"]["TRAIN_STEPS"]
        self.eval_steps = model_config["model_params"]["EVAL_STEPS"]

        self.inv_t = model_config["model_params"]["INV_T"]
        self.eta = model_config["model_params"]["ETA"]

        self.rand_init = model_config["model_params"]["RAND_INIT"]
        self.device = device

        # print('spatial', self.spatial)
        # print('S', self.S)
        # print('D', self.D)
        # print('R', self.R)
        # print('train_steps', self.train_steps)
        # print('eval_steps', self.eval_steps)
        # print('inv_t', self.inv_t)
        # print('eta', self.eta)
        # print('rand_init', self.rand_init)

    def _build_bases(self, B, S, D, R):
        raise NotImplementedError

    def local_step(self, x, bases, coef):
        raise NotImplementedError

    @torch.no_grad()
    def local_inference(self, x, bases):
        # (B * S, D, N)^T @ (B * S, D, R) -> (B * S, N, R)
        coef = torch.bmm(x.transpose(1, 2), bases)
        coef = F.softmax(self.inv_t * coef, dim=-1)

        steps = self.train_steps if self.training else self.eval_steps
        for _ in range(steps):
            bases, coef = self.local_step(x, bases, coef)

        return bases, coef

    def compute_coef(self, x, bases, coef):
        raise NotImplementedError

    def forward(self, x, return_bases=False):
        B, C, L = x.shape

        # (B, C, L) -> (B * S, D, N)
        D = C // self.S
        N = L
        x = x.view(B * self.S, D, N)

        if not self.rand_init and not hasattr(self, 'bases'):
            bases = self._build_bases(1, self.S, D, self.R)
            self.register_buffer('bases', bases)

        # (S, D, R) -> (B * S, D, R)
        if self.rand_init:
            bases = self._build_bases(B, self.S, D, self.R)
        else:
            bases = self.bases.repeat(B, 1, 1)

        bases, coef = self.local_inference(x, bases)

        # (B * S, N, R)
        coef = self.compute_coef(x, bases, coef)

        # (B * S, D, R) @ (B * S, N, R)^T -> (B * S, D, N)
        x = torch.bmm(bases, coef.transpose(1, 2))

        # (B * S, D, N) -> (B, C, L)
        x = x.view(B, C, L)

        # (B * L, D, R) -> (B, L, N, D)
        bases = bases.view(B, self.S, D, self.R)

        if not self.rand_init and not self.training and not return_bases:
            self.online_update(bases)

        # if not self.rand_init or return_bases:
        #     return x, bases
        # else:
        return x

    @torch.no_grad()
    def online_update(self, bases):
        # (B, S, D, R) -> (S, D, R)
        update = bases.mean(dim=0)
        self.bases += self.eta * (update - self.bases)
        self.bases = F.normalize(self.bases, dim=1)


class NMF1D(_MatrixDecomposition1DBase):
    def __init__(self, device, model_config):
        super().__init__(device, model_config)
        self.device = device
        self.inv_t = 1

    def _build_bases(self, B, S, D, R):
        bases = torch.rand((B * S, D, R)).to(self.device)
        bases = F.normalize(bases, dim=1)

        return bases

    @torch.no_grad()
    def local_step(self, x, bases, coef):
        # (B * S, D, N)^T @ (B * S, D, R) -> (B * S, N, R)
        numerator = torch.bmm(x.transpose(1, 2), bases)
        # (B * S, N, R) @ [(B * S, D, R)^T @ (B * S, D, R)] -> (B * S, N, R)
        denominator = coef.bmm(bases.transpose(1, 2).bmm(bases))
        # Multiplicative Update
        coef = coef * numerator / (denominator + 1e-6)

        # (B * S, D, N) @ (B * S, N, R) -> (B * S, D, R)
        numerator = torch.bmm(x, coef)
        # (B * S, D, R) @ [(B * S, N, R)^T @ (B * S, N, R)] -> (B * S, D, R)
        denominator = bases.bmm(coef.transpose(1, 2).bmm(coef))
        # Multiplicative Update
        bases = bases * numerator / (denominator + 1e-6)

        return bases, coef

    def compute_coef(self, x, bases, coef):
        # (B * S, D, N)^T @ (B * S, D, R) -> (B * S, N, R)
        numerator = torch.bmm(x.transpose(1, 2), bases)
        # (B * S, N, R) @ (B * S, D, R)^T @ (B * S, D, R) -> (B * S, N, R)
        denominator = coef.bmm(bases.transpose(1, 2).bmm(bases))
        # multiplication update
        coef = coef * numerator / (denominator + 1e-6)

        return coef


class VQ1D(_MatrixDecomposition1DBase):
    def __init__(self, device, model_config):
        super().__init__(device, model_config)
        self.device = device

    def _build_bases(self, B, S, D, R):
        bases = torch.randn((B * S, D, R)).to(self.device)
        bases = F.normalize(bases, dim=1)

        return bases

    @torch.no_grad()
    def local_step(self, x, bases, _):
        # (B * S, D, N), normalize x along D (for cosine similarity)
        std_x = F.normalize(x, dim=1)

        # (B * S, D, R), normalize bases along D (for cosine similarity)
        std_bases = F.normalize(bases, dim=1, eps=1e-6)

        # (B * S, D, N)^T @ (B * S, D, R) -> (B * S, N, R)
        coef = torch.bmm(std_x.transpose(1, 2), std_bases)

        # softmax along R
        coef = F.softmax(self.inv_t * coef, dim=-1)

        # normalize along N
        coef = coef / (1e-6 + coef.sum(dim=1, keepdim=True))

        # (B * S, D, N) @ (B * S, N, R) -> (B * S, D, R)
        bases = torch.bmm(x, coef)

        return bases, coef


    def compute_coef(self, x, bases, _):
        with torch.no_grad():
            # (B * S, D, N) -> (B * S, 1, N)
            x_norm = x.norm(dim=1, keepdim=True)

        # (B * S, D, N) / (B * S, 1, N) -> (B * S, D, N)
        std_x = x / (1e-6 + x_norm)

        # (B * S, D, R), normalize bases along D (for cosine similarity)
        std_bases = F.normalize(bases, dim=1, eps=1e-6)

        # (B * S, N, D)^T @ (B * S, D, R) -> (B * S, N, R)
        coef = torch.bmm(std_x.transpose(1, 2), std_bases)

        # softmax along R
        coef = F.softmax(self.inv_t * coef, dim=-1)

        return coef



class HamburgerV2(nn.Module):
    def __init__(self, device, in_c, model_config):
        super().__init__()

        self.device = device
        C = model_config["model_params"]["MD_D"]

        self.lower_bread = nn.Sequential(
            nn.Conv1d(in_c, C, 1),
            nn.ReLU(inplace=True)
            )

        ham_type = model_config["model_params"]["HAM_TYPE"]

        if "nmf" in ham_type.lower():
            self.lower_bread = nn.Sequential(
                nn.Conv1d(in_c, C, 1),
                nn.ReLU(inplace=True)
                )
        else:
            self.lower_bread = nn.Conv1d(in_c, C, 1)

        if "nmf" in ham_type.lower():
            self.ham = NMF1D(self.device, model_config)
        elif "vq" in ham_type.lower():
            self.ham = VQ1D(self.device, model_config)
        else:
            print("Unknown type specified for HAM_TYPE:", ham_type)
            exit()

        self.cheese = ConvBNReLU(C, C)
        self.upper_bread = nn.Conv1d(C, in_c, 1, bias=False)

        self.shortcut = nn.Sequential()

        self._init_weight()

        # print('ham', HAM)

    def _init_weight(self):
        for m in self.modules():
            if isinstance(m, nn.Conv1d):
                N = m.kernel_size[0] * m.out_channels
                m.weight.data.normal_(0, np.sqrt(2. / N))
            elif isinstance(m, _BatchNorm):
                m.weight.data.fill_(1)
                if m.bias is not None:
                    m.bias.data.zero_()

    def forward(self, x):
        shortcut = self.shortcut(x)

        x = self.lower_bread(x)
        x = self.ham(x)
        x = self.cheese(x)
        x = self.upper_bread(x)

        x = F.relu(x + shortcut, inplace=True)

        return x

    def online_update(self, bases):
        if hasattr(self.ham, 'online_update'):
            self.ham.online_update(bases)



class ConvBNReLU(nn.Module):
    @classmethod
    def _same_paddings(cls, kernel_size):
        if kernel_size == 1:
            return 0
        elif kernel_size == 3:
            return 1

    def __init__(self, in_c, out_c,
                 kernel_size=1, stride=1, padding='same',
                 dilation=1, groups=1, act='relu', apply_bn = True):
        super().__init__()

        self.apply_bn = apply_bn
        if padding == 'same':
            padding = self._same_paddings(kernel_size)

        self.conv = nn.Conv1d(in_c, out_c,
                              kernel_size=kernel_size, stride=stride,
                              padding=padding, dilation=dilation,
                              groups=groups,
                              bias=False)
        if self.apply_bn:
            self.bn = nn.BatchNorm1d(out_c)
        if act == "sigmoid":
            self.act = nn.Sigmoid()
        else:
            self.act = nn.ReLU(inplace=True)

    def forward(self, x):
        x = self.conv(x)
        if self.apply_bn:
            x = self.bn(x)
        x = self.act(x)
        
        return x


class depthwise_separable_conv(nn.Module):
    def __init__(self, nin, nout, kernel_size = 3, stride=2, padding=1, bias=False):
        super(depthwise_separable_conv, self).__init__()
        self.depthwise = nn.Conv1d(nin, nin, kernel_size=kernel_size, padding="same", groups=nin, bias=bias)
        if stride == 2:
            self.pointwise = nn.Conv1d(nin, nout, kernel_size=3, stride=2, padding=padding, bias=bias)
        else:
            self.pointwise = nn.Conv1d(nin, nout, kernel_size=1, padding=padding, bias=bias)
        self.bn = nn.BatchNorm1d(nout)
        self.relu = nn.ReLU()

    def forward(self, x):
        out = self.depthwise(x)
        out = self.pointwise(out)
        out = self.bn(out)
        out = self.relu(out)
        return out
    

class Model(nn.Module):
    def __init__(self, device, model_config, filter_size=8):
        super(Model, self).__init__()
        self.device = device
        kernel_sizes = model_config["train_params"]["kernel_size"]
        fs = int(model_config["data"]["target_fs"])
        window_len = int(model_config["data"]["window_len_sec"])
        self.vec_len = fs * window_len

        self.depthwise_separable_conv_1 = depthwise_separable_conv(nin=1,nout=filter_size * (2 ** 0),kernel_size=kernel_sizes[0], stride=2, padding=1)
        self.depthwise_separable_conv_2 = depthwise_separable_conv(nin=filter_size * (2 ** 0),nout=filter_size * (2 ** 1),kernel_size=kernel_sizes[1], stride=2, padding=1)
        self.depthwise_separable_conv_3 = depthwise_separable_conv(nin=filter_size * (2 ** 1),nout=filter_size * (2 ** 2),kernel_size=kernel_sizes[2], stride=2, padding=1)
        self.depthwise_separable_conv_4 = depthwise_separable_conv(nin=filter_size * (2 ** 2),nout=filter_size * (2 ** 3),kernel_size=7, stride=1, padding=0)

        C = model_config["model_params"]["MD_D"]        
        self.squeeze = ConvBNReLU(filter_size * ((2**3) + (2**2)), C, 3, 1)
        self.hamburger = HamburgerV2(self.device, C, model_config)

        self.align = ConvBNReLU(C, 3, 1)
        self.upsample1D = nn.Upsample(size=self.vec_len)

        self.seg_out = nn.Sequential(
            nn.Conv1d(in_channels=3,out_channels=3,kernel_size=5, padding="same"),
            nn.ReLU(),
            nn.Conv1d(in_channels=3,out_channels=1,kernel_size=1),
            nn.Sigmoid()
        )

    def forward(self, x):
        x = self.depthwise_separable_conv_1(x)
        x = self.depthwise_separable_conv_2(x)      
        x1 = self.depthwise_separable_conv_3(x)
        x = self.depthwise_separable_conv_4(x1)
        x = torch.concat([x, x1], dim=1)
        x = self.squeeze(x)
        x = self.hamburger(x)        
        x = self.align(x)
        x = self.upsample1D(x)
        x = self.seg_out(x)
        return x


def test_model():
    import os
    import json
    from torch.utils.tensorboard import SummaryWriter
    writer = SummaryWriter('test_run/Model')

    config_path = os.path.join("utils", "sqa", "config", "sqa_bvp.json")
    if os.path.exists(config_path):
        with open(config_path) as json_file:
            model_config = json.load(json_file)
        json_file.close()
    else:
        print("Model config file not found")
        exit()

    num_channels = model_config["model_params"]["INPUT_CHANNELS"]
    sampling_rate = model_config["data"]["target_fs"]
    seq_len = model_config["data"]["window_len_sec"]
    seq_samples = seq_len * sampling_rate
    batch_size = 1

    device = ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using {device} device")
    sqPPG_model = Model(device, model_config).to(device)
    sqPPG_model.eval()

    sig_vec = torch.rand((batch_size, num_channels, seq_samples)).to(device)
    # print(sig_vec.shape)

    sig_out = sqPPG_model(sig_vec)
    print(sig_out.shape)
    # print(sig_out)

    writer.add_graph(sqPPG_model, sig_vec)
    writer.close()

if __name__ == "__main__":

    test_model()
