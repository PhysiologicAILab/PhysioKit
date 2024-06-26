
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn.modules.batchnorm import _BatchNorm

import numpy as np

# num_filters
nf = [8, 16, 32, 64]

model_config = {
    "MD_FSAM": True,
    "MD_TYPE": "NMF",
    "MD_R": 5,
    "MD_S": 1,
    "MD_STEPS": 5,
    "INV_T": 1,
    "ETA": 0.9,
    "RAND_INIT": True,
    "in_channels": 1,
    "data_channels": 1,
    "align_channels": nf[3]//2,
    "batch_size": 2,
    "samples": 300,
    "debug": True,
    "assess_latency": False,
    "num_trials": 20,
    "visualize": False,
    "ckpt_path": "",
    "data_path": "",
    "label_path": ""
}

class _MatrixDecompositionBase(nn.Module):
    def __init__(self, device, md_config, debug=False, dim="3D"):
        super().__init__()

        self.dim = dim
        self.md_type = md_config["model_params"]["MD_TYPE"]
        self.S = md_config["model_params"]["MD_S"]
        self.R = md_config["model_params"]["MD_R"]
        self.debug = debug

        self.train_steps = md_config["model_params"]["MD_STEPS"]
        self.eval_steps = md_config["model_params"]["MD_STEPS"]

        self.inv_t = model_config["INV_T"]
        self.eta = model_config["ETA"]

        self.rand_init = model_config["RAND_INIT"]
        self.device = device

        # print('Dimension:', self.dim)
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

        if self.debug:
            print("Org x.shape", x.shape)

        if self.dim == "3D":        # (B, C, T, H, W) -> (B * S, D, N)
            B, C, T, H, W = x.shape

            # # dimension of vector of our interest is T (rPPG signal as T dimension), so forming this as vector
            # # From spatial and channel dimension, which are features, only 2-4 shall be enough to generate the approximated attention matrix
            D = T // self.S
            N = C * H * W 

            x = x.view(B * self.S, D, N)

        elif self.dim == "2D":      # (B, C, H, W) -> (B * S, D, N)
            B, C, H, W = x.shape
            D = C // self.S
            N = H * W
            x = x.view(B * self.S, D, N)

        elif self.dim == "1D":                       # (B, C, L) -> (B * S, D, N)
            B, C, L = x.shape
            D = L // self.S
            N = C
            x = x.view(B * self.S, D, N)

        else:
            print("Dimension not supported")
            exit()

        if self.debug:
            print("MD_Type", self.md_type)
            print("MD_S", self.S)
            print("MD_D", D)
            print("MD_N", N)
            print("MD_R", self.R)
            print("MD_TRAIN_STEPS", self.train_steps)
            print("MD_EVAL_STEPS", self.eval_steps)
            print("x.view(B * self.S, D, N)", x.shape)

        if not self.rand_init and not hasattr(self, 'bases'):
            bases = self._build_bases(1, self.S, D, self.R)
            self.register_buffer('bases', bases)

        # (S, D, R) -> (B * S, D, R)
        if self.rand_init:
            bases = self._build_bases(B, self.S, D, self.R)
        else:
            bases = self.bases.repeat(B, 1, 1).to(self.device)

        bases, coef = self.local_inference(x, bases)

        # (B * S, N, R)
        coef = self.compute_coef(x, bases, coef)

        # (B * S, D, R) @ (B * S, N, R)^T -> (B * S, D, N)
        x = torch.bmm(bases, coef.transpose(1, 2))

        if self.dim == "3D":
            # (B * S, D, N) -> (B, C, H, W)
            x = x.view(B, C, T, H, W)
        elif self.dim == "2D":
            # (B * S, D, N) -> (B, C, H, W)
            x = x.view(B, C, H, W)
        else:
            # (B * S, D, N) -> (B, C, L)
            x = x.view(B, C, L)

            # # smoothening the temporal dimension
            # # print("Intermediate-1 x", x.shape)
            # sample_1 = x[:, :, 0].unsqueeze(2)
            # sample_2 = x[:, :, -1].unsqueeze(2)
            # x = torch.cat([sample_1, x, sample_2], dim=2)
            # kernels = torch.FloatTensor([[[1, 1, 1]]]).repeat(N, N, 1).to(self.device)            
            # bias = torch.FloatTensor(torch.zeros(N)).to(self.device)
            # x = F.conv1d(x, kernels, bias=bias, padding="valid")
            # x = (x - x.min())/x.std()

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


class NMF(_MatrixDecompositionBase):
    def __init__(self, device, md_config, debug=False, dim="3D"):
        super().__init__(device, md_config, debug=debug, dim=dim)
        self.device = device
        self.inv_t = 1

    def _build_bases(self, B, S, D, R):
        bases = torch.rand((B * S, D, R)).to(self.device)
        # bases = torch.ones((B * S, D, R)).to(self.device)
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


class VQ(_MatrixDecompositionBase):
    def __init__(self, device, md_config, debug=False, dim="3D"):
        super().__init__(device, md_config, debug=debug, dim=dim)
        self.device = device

    def _build_bases(self, B, S, D, R):
        bases = torch.randn((B * S, D, R)).to(self.device)
        # bases = torch.ones((B * S, D, R)).to(self.device)
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


class ConvBNReLU(nn.Module):
    @classmethod
    def _same_paddings(cls, kernel_size, dim):
        if dim == "3D":
            if kernel_size == (1, 1, 1):
                return (0, 0, 0)
            elif kernel_size == (3, 3, 3):
                return (1, 1, 1)
        elif dim == "2D":
            if kernel_size == (1, 1):
                return (0, 0)
            elif kernel_size == (3, 3):
                return (1, 1)
        else:
            if kernel_size == 1:
                return 0
            elif kernel_size == 3:
                return 1

    def __init__(self, in_c, out_c, dim,
                 kernel_size=1, stride=1, padding='same',
                 dilation=1, groups=1, act='relu', apply_bn=True, apply_act=True):
        super().__init__()

        self.apply_bn = apply_bn
        self.apply_act = apply_act
        self.dim = dim
        if dilation == 1:
            if self.dim == "3D":
                dilation = (1, 1, 1)
            elif self.dim == "2D":
                dilation = (1, 1)
            else:
                dilation = 1

        if kernel_size == 1:
            if self.dim == "3D":
                kernel_size = (1, 1, 1)
            elif self.dim == "2D":
                kernel_size = (1, 1)
            else:
                kernel_size = 1

        if stride == 1:
            if self.dim == "3D":
                stride = (1, 1, 1)
            elif self.dim == "2D":
                stride = (1, 1)
            else:
                stride = 1

        if padding == 'same':
            padding = self._same_paddings(kernel_size, dim)

        if self.dim == "3D":
            self.conv = nn.Conv3d(in_c, out_c,
                                  kernel_size=kernel_size, stride=stride,
                                  padding=padding, dilation=dilation,
                                  groups=groups,
                                  bias=False)
        elif self.dim == "2D":
            self.conv = nn.Conv2d(in_c, out_c,
                                  kernel_size=kernel_size, stride=stride,
                                  padding=padding, dilation=dilation,
                                  groups=groups,
                                  bias=False)
        else:
            self.conv = nn.Conv1d(in_c, out_c,
                                  kernel_size=kernel_size, stride=stride,
                                  padding=padding, dilation=dilation,
                                  groups=groups,
                                  bias=False)

        if act == "sigmoid":
            self.act = nn.Sigmoid()
        else:
            self.act = nn.ReLU(inplace=True)

        if self.apply_bn:
            if self.dim == "3D":
                self.bn = nn.BatchNorm3d(out_c)
            elif self.dim == "2D":
                self.bn = nn.BatchNorm2d(out_c)
            else:
                self.bn = nn.BatchNorm1d(out_c)

    def forward(self, x):
        x = self.conv(x)
        if self.apply_bn:
            x = self.bn(x)
        if self.apply_act:
            x = self.act(x)
        return x


class FeaturesFactorizationModule(nn.Module):
    def __init__(self, inC, device, md_config, dim="3D", debug=False):
        super().__init__()

        self.device = device
        self.dim = dim
        md_type = md_config["model_params"]["MD_TYPE"]
        align_C = model_config["align_channels"]      #inC // 4  # // 2 #// 8

        if self.dim == "3D":
            if "nmf" in md_type.lower():
                self.pre_conv_block = nn.Sequential(
                    nn.Conv3d(inC, align_C, (1, 1, 1)), 
                    nn.ReLU(inplace=True)
                    )
            else:
                self.pre_conv_block = nn.Conv3d(inC, align_C, (1, 1, 1))
        elif self.dim == "2D":
            if "nmf" in md_type.lower():
                self.pre_conv_block = nn.Sequential(
                    nn.Conv2d(inC, align_C, (1, 1)),
                    nn.ReLU(inplace=True)
                    )
            else:
                self.pre_conv_block = nn.Conv2d(inC, align_C, (1, 1))
        elif self.dim == "1D":
            if "nmf" in md_type.lower():
                self.pre_conv_block = nn.Sequential(
                    nn.Conv1d(inC, align_C, 1), 
                    nn.ReLU(inplace=True)
                    )
            else:
                self.pre_conv_block = nn.Conv1d(inC, align_C, 1)
        else:
            print("Dimension not supported")

        if "nmf" in md_type.lower():
            self.md_block = NMF(self.device, md_config, dim=self.dim, debug=debug)
        elif "vq" in md_type.lower():
            self.md_block = VQ(self.device, md_config, dim=self.dim, debug=debug)
        else:
            print("Unknown type specified for MD_TYPE:", md_type)
            exit()

        if self.dim == "3D":
            if "nmf" in md_type.lower():
                self.post_conv_block = nn.Sequential(
                    ConvBNReLU(align_C, align_C, dim=self.dim, kernel_size=1),
                    nn.Conv3d(align_C, inC, 1, bias=False))
            else:
                self.post_conv_block = nn.Sequential(
                    ConvBNReLU(align_C, align_C, dim=self.dim, kernel_size=1, apply_act=False),
                    nn.Conv3d(align_C, inC, 1, bias=False))
        elif self.dim == "2D":
            if "nmf" in md_type.lower():
                self.post_conv_block = nn.Sequential(
                    ConvBNReLU(align_C, align_C, dim=self.dim, kernel_size=1),
                    nn.Conv2d(align_C, inC, 1, bias=False))
            else:
                self.post_conv_block = nn.Sequential(
                    ConvBNReLU(align_C, align_C, dim=self.dim, kernel_size=1, apply_act=False),
                    nn.Conv2d(align_C, inC, 1, bias=False))
        else:
            if "nmf" in md_type.lower():
                self.post_conv_block = nn.Sequential(
                    ConvBNReLU(align_C, align_C, dim=self.dim, kernel_size=1),
                    nn.Conv1d(align_C, inC, 1, bias=False))
            else:
                self.post_conv_block = nn.Sequential(
                    ConvBNReLU(align_C, align_C, dim=self.dim, kernel_size=1, apply_act=False),
                    nn.Conv1d(align_C, inC, 1, bias=False))

        self._init_weight()

    def _init_weight(self):
        for m in self.modules():
            if isinstance(m, nn.Conv3d):
                N = m.kernel_size[0] * m.kernel_size[1] * m.kernel_size[2] * m.out_channels
                m.weight.data.normal_(0, np.sqrt(2. / N))
            elif isinstance(m, nn.Conv2d):
                N = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, np.sqrt(2. / N))
            elif isinstance(m, nn.Conv1d):
                N = m.kernel_size[0] * m.out_channels
                m.weight.data.normal_(0, np.sqrt(2. / N))
            elif isinstance(m, _BatchNorm):
                m.weight.data.fill_(1)
                if m.bias is not None:
                    m.bias.data.zero_()

    def forward(self, x):
        x = self.pre_conv_block(x)
        att = self.md_block(x)
        dist = torch.dist(x, att)
        att = self.post_conv_block(att)

        return att, dist

    def online_update(self, bases):
        if hasattr(self.md_block, 'online_update'):
            self.md_block.online_update(bases)


class encoder_block(nn.Module):
    def __init__(self, inCh, dropout_rate=0.1, debug=False):
        super(encoder_block, self).__init__()
        # inCh, out_channel, kernel_size, stride, padding

        self.debug = debug

        self.encoder = nn.Sequential(
            nn.Conv1d(inCh, nf[0], 21, 1, 10),
            nn.Conv1d(nf[0], nf[0], 21, 1, 10),
            nn.BatchNorm1d(nf[0]),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=2, stride=2),
            # nn.Dropout1d(p=dropout_rate),

            nn.Conv1d(nf[0], nf[0], 11, 1, 5),
            nn.Conv1d(nf[0], nf[1], 11, 1, 5),
            nn.BatchNorm1d(nf[1]),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=2, stride=2),
            # nn.Dropout1d(p=dropout_rate),

            nn.Conv1d(nf[1], nf[1], 11, 1, 5),
            nn.Conv1d(nf[1], nf[2], 5, 1, 2),
            nn.BatchNorm1d(nf[2]),
            nn.ReLU(inplace=True),
            nn.Dropout1d(p=dropout_rate),

            nn.Conv1d(nf[2], nf[2], 5, 1, 2),
            nn.Conv1d(nf[2], nf[3], 3, 1, 1),
            nn.BatchNorm1d(nf[3]),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        x = self.encoder(x)
        if self.debug:
            print("Encoder")
            print("     x.shape", x.shape)
        return x


class ASPP(nn.Module):
    def __init__(self, in_channel=nf[3], depth=1):
        super(ASPP,self).__init__()
        self.atrous_block1 = nn.Conv1d(in_channel, depth, 3, 1, padding=1, dilation=1)
        self.atrous_block2 = nn.Conv1d(in_channel, depth, 3, 1, padding=2, dilation=2)
        self.atrous_block3 = nn.Conv1d(in_channel, depth, 5, 1, padding=6, dilation=3)
        self.atrous_block4 = nn.Conv1d(in_channel, depth, 7, 1, padding=12, dilation=4)
        self.conv_1x1_output = nn.Conv1d(depth * 4, depth, 1, 1)
 
    def forward(self, x):
        atrous_block1 = self.atrous_block1(x)
        atrous_block2 = self.atrous_block2(x)
        atrous_block3 = self.atrous_block3(x)
        atrous_block4 = self.atrous_block4(x)
        net = self.conv_1x1_output(
            torch.cat([atrous_block1, atrous_block2, atrous_block3, atrous_block4], dim=1))
        return net

class SQ_Head(nn.Module):
    def __init__(self, md_config, vec_len, device, dropout_rate=0.1, debug=False):
        super(SQ_Head, self).__init__()
        self.debug = debug

        self.use_fsam = md_config["model_params"]["MD_FSAM"]
        self.md_type = md_config["model_params"]["MD_TYPE"]

        if self.use_fsam:
            inC = nf[3]
            self.fsam = FeaturesFactorizationModule(inC, device, md_config, dim="1D", debug=debug)
            self.fsam_norm = nn.InstanceNorm1d(inC)
            self.bias1 = nn.Parameter(torch.tensor(1.0), requires_grad=False).to(device)
            # self.bias2 = nn.Parameter(torch.tensor(2.0), requires_grad=False).to(device)
        else:
            inC = nf[3]

        self.conv_decoder = nn.Sequential(
            nn.Upsample(size=vec_len),
            ASPP(nf[3]),
            nn.Conv1d(1, 1, 3, 1, 1),
            nn.Sigmoid()
        )

    def forward(self, signal_embeddings):

        if self.debug:
            print("Decoder")
            print("     signal_embeddings.shape", signal_embeddings.shape)

        if self.use_fsam:
            att_mask, appx_error = self.fsam(signal_embeddings - signal_embeddings.min())

            if self.debug:
                print("att_mask.shape", att_mask.shape)

            # # directly use att_mask   ---> difficult to converge without Residual connection. Needs high rank
            # factorized_embeddings = self.fsam_norm(att_mask)

            # # Residual connection: 
            # # factorized_embeddings = signal_embeddings + self.fsam_norm(att_mask)
            # factorized_embeddings = signal_embeddings + att_mask

            # # # Multiplication
            # x = torch.mul(signal_embeddings - signal_embeddings.min() + self.bias1, att_mask - att_mask.min() + self.bias1)
            # factorized_embeddings = self.fsam_norm(x)

            # # Multiplication with Residual connection
            x = torch.mul(signal_embeddings - signal_embeddings.min() + self.bias1, att_mask - att_mask.min() + self.bias1)
            factorized_embeddings = signal_embeddings + self.fsam_norm(x)

            # # # Concatenate
            # x = torch.mul(signal_embeddings + self.bias2, att_mask + self.bias1)
            # factorized_embeddings = torch.cat([signal_embeddings, self.fsam_norm(x)], dim=1)

            x = self.conv_decoder(factorized_embeddings)
        
        else:
            x = self.conv_decoder(signal_embeddings)
        
        if self.debug:
            print("     conv_decoder_x.shape", x.shape)
        
        if self.use_fsam:
            return x, factorized_embeddings, att_mask, appx_error
        else:
            return x


class Model(nn.Module):
    def __init__(self, device, model_config, vec_len=-1, dropout=0.1, debug=False):
        super(Model, self).__init__()
        self.device = device
        if vec_len == -1:
            fs = int(model_config["data"]["target_fs"])
            window_len = int(model_config["data"]["window_len_sec"])
            self.vec_len = fs * window_len
        else:
            self.vec_len = vec_len

        self.debug = debug

        self.use_fsam = model_config["model_params"]["MD_FSAM"]

        if self.debug:
            print("nf:", nf)

        self.encoder = encoder_block(1, dropout_rate=dropout, debug=debug)
        self.sqa_head = SQ_Head(model_config, self.vec_len, device=device, dropout_rate=dropout, debug=debug)

        
    def forward(self, x): # [batch, channels=1, length=30*10]
        
        [batch, channel, length] = x.shape

        if self.debug:
            print("Input.shape", x.shape)
        
        # x = self.input_norm(x)
        embeddings = self.encoder(x)

        if self.debug:
            print("embeddings.shape", embeddings.shape)

        if self.use_fsam:
            sq_vec, embeddings, att_mask, appx_error = self.sqa_head(embeddings)
        else:
            sq_vec = self.sqa_head(embeddings)

        if self.debug:
            print("sq_vec.shape", sq_vec.shape)

        return (embeddings, sq_vec)


def test_model():
    from pathlib import Path
    import json
    from torch.utils.tensorboard import SummaryWriter

    runs_dir = Path('runs/test/SQAPhysMD')
    runs_dir.mkdir(parents=True, exist_ok=True)
    writer = SummaryWriter(str(runs_dir))

    config_path = Path("configs").joinpath("SQAPhysMD_Aug_CL.json")
    # config_path = Path("configs").joinpath("SQAPhys_Aug_CL.json")
    if config_path.exists():
        with open(str(config_path)) as json_file:
            model_config = json.load(json_file)
        json_file.close()
    else:
        print("Model config file not found")
        exit()

    num_channels = 1
    sampling_rate = model_config["data"]["target_fs"]
    seq_len = model_config["data"]["window_len_sec"]
    seq_samples = seq_len * sampling_rate
    batch_size = 1

    device = ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using {device} device")
    sqPPG_model = Model(device, model_config, debug=True).to(device)
    sqPPG_model.eval()

    sig_vec = torch.rand((batch_size, num_channels, seq_samples)).to(device)
    # print(sig_vec.shape)

    embedding, seg = sqPPG_model(sig_vec)
    print("Embeddings shape:", embedding.shape)
    print("SQvec shape:", seg.shape)
    # print(sig_out)

    pytorch_total_params = sum(p.numel() for p in sqPPG_model.parameters())
    print("Total parameters = ", pytorch_total_params)

    pytorch_trainable_params = sum(p.numel() for p in sqPPG_model.parameters() if p.requires_grad)
    print("Trainable parameters = ", pytorch_trainable_params)

    # writer.add_graph(sqPPG_model, sig_vec)
    # writer.close()

if __name__ == "__main__":

    test_model()