from torch import nn
from torch.nn import functional as F
import torch

from base import Conv2dBnRelu, DecoderBlock
from encoders import get_encoder_channel_nr

"""
This script has been taken (and modified) from :
https://github.com/ternaus/TernausNet

@ARTICLE{arXiv:1801.05746,
         author = {V. Iglovikov and A. Shvets},
          title = {TernausNet: U-Net with VGG11 Encoder Pre-Trained on ImageNet for Image Segmentation},
        journal = {ArXiv e-prints},
         eprint = {1801.05746}, 
           year = 2018
        }
"""


class UNet(nn.Module):
    def __init__(self, encoder, num_classes, dropout_2d=0.0, use_hypercolumn=False, pool0=False):
        super().__init__()
        self.num_classes = num_classes
        self.dropout_2d = dropout_2d
        self.use_hypercolumn = use_hypercolumn
        self.pool0 = pool0

        self.encoder = encoder
        encoder_channel_nr = get_encoder_channel_nr(self.encoder)

        self.center = nn.Sequential(Conv2dBnRelu(encoder_channel_nr[3], encoder_channel_nr[3]),
                                    Conv2dBnRelu(encoder_channel_nr[3], encoder_channel_nr[2]),
                                    nn.AvgPool2d(kernel_size=2, stride=2)
                                    )

        self.dec5 = DecoderBlock(encoder_channel_nr[3] + encoder_channel_nr[2],
                                 encoder_channel_nr[3],
                                 encoder_channel_nr[3] // 8)

        self.dec4 = DecoderBlock(encoder_channel_nr[2] + encoder_channel_nr[3] // 8,
                                 encoder_channel_nr[3] // 2,
                                 encoder_channel_nr[3] // 8)
        self.dec3 = DecoderBlock(encoder_channel_nr[1] + encoder_channel_nr[3] // 8,
                                 encoder_channel_nr[3] // 4,
                                 encoder_channel_nr[3] // 8)
        self.dec2 = DecoderBlock(encoder_channel_nr[0] + encoder_channel_nr[3] // 8,
                                 encoder_channel_nr[3] // 8,
                                 encoder_channel_nr[3] // 8)
        self.dec1 = DecoderBlock(encoder_channel_nr[3] // 8,
                                 encoder_channel_nr[3] // 16,
                                 encoder_channel_nr[3] // 8)

        self.dec0 = DecoderBlock(encoder_channel_nr[3] // 8,
                                 encoder_channel_nr[3] // 16,
                                 encoder_channel_nr[3] // 8)

        if self.use_hypercolumn:
            self.dec0 = DecoderBlock(5 * encoder_channel_nr[3] // 8,
                                     encoder_channel_nr[3] // 8,
                                     5 * encoder_channel_nr[3] // 8)
            self.final = nn.Sequential(Conv2dBnRelu(5 * encoder_channel_nr[3] // 8, encoder_channel_nr[3] // 8),
                                       nn.Conv2d(encoder_channel_nr[3] // 8, num_classes, kernel_size=1, padding=0))
        else:
            self.dec0 = DecoderBlock(encoder_channel_nr[3] // 8,
                                     encoder_channel_nr[3] // 8,
                                     encoder_channel_nr[3] // 8)
            self.final = nn.Sequential(Conv2dBnRelu(encoder_channel_nr[3] // 8, encoder_channel_nr[3] // 8),
                                       nn.Conv2d(encoder_channel_nr[3] // 8, num_classes, kernel_size=1, padding=0))

    def forward(self, x):
        encoder2, encoder3, encoder4, encoder5 = self.encoder(x)
        encoder5 = F.dropout2d(encoder5, p=self.dropout_2d)

        center = self.center(encoder5)

        dec5 = self.dec5(center, encoder5)
        dec4 = self.dec4(dec5, encoder4)
        dec3 = self.dec3(dec4, encoder3)
        dec2 = self.dec2(dec3, encoder2)
        dec1 = self.dec1(dec2)

        if self.use_hypercolumn:
            dec1 = torch.cat([dec1,
                              F.upsample(dec2, scale_factor=2, mode='bilinear'),
                              F.upsample(dec3, scale_factor=4, mode='bilinear'),
                              F.upsample(dec4, scale_factor=8, mode='bilinear'),
                              F.upsample(dec5, scale_factor=16, mode='bilinear'),
                              ], 1)

        if self.pool0:
            dec1 = self.dec0(dec1)

        return self.final(dec1)
