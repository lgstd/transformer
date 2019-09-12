#encoding: utf-8

import torch
from torch import nn
from modules.base import *
from math import sqrt, inf

from transformer.TA.Encoder import Encoder as EncoderBase

class Encoder(EncoderBase):

	def __init__(self, isize, nwd, num_layer, fhsize=None, dropout=0.0, attn_drop=0.0, num_head=8, xseql=512, ahsize=None, norm_output=True, num_layer_dec=6):

		_ahsize = isize if ahsize is None else ahsize

		_fhsize = _ahsize * 4 if fhsize is None else fhsize

		super(Encoder, self).__init__(isize, nwd, num_layer, _fhsize, dropout, attn_drop, num_head, xseql, _ahsize, norm_output, num_layer_dec)

		self.attns = nn.ModuleList([CrossAttn(isize, _ahsize, isize, num_head, dropout=attn_drop) for i in range(num_layer)])

		self.sc_tattn_w = nn.Parameter(torch.Tensor(num_layer + 1, num_layer_dec).uniform_(- sqrt(2.0 / (num_layer + num_layer_dec + 1)), sqrt(2.0 / (num_layer + num_layer_dec + 1))))
		self.sc_tattn_drop = Dropout(dropout) if dropout > 0.0 else None

	# inputs: (bsize, seql)
	# mask: (bsize, 1, seql), generated with:
	#	mask = inputs.eq(0).unsqueeze(1)

	def forward(self, inputs, mask=None):

		def transform(lin, w, drop):

			_tmp = torch.stack(lin, -1)
			_osize = _tmp.size()
			_tmp = _tmp.view(-1, _osize[-1]).mm(w.softmax(dim=0) if drop is None else drop(w).softmax(dim=0))
			_osize = list(_osize)
			_osize[-1] = -1

			return _tmp.view(_osize)

		bsize, seql = inputs.size()
		out = self.wemb(inputs)
		out = out * sqrt(out.size(-1)) + self.pemb(inputs, expand=False)

		if self.drop is not None:
			out = self.drop(out)

		out = self.out_normer(out)
		outs = [out]

		_h0 = out.max(dim=1, keepdim=True)[0] if mask is None else out.masked_fill(mask.squeeze(1).unsqueeze(-1), -inf).max(dim=1, keepdim=True)[0]
		hl = [_h0]

		for net, attn in zip(self.nets, self.attns):
			out = net(out, mask)
			outs.append(out)
			hl.append(attn(_h0, out, mask=mask))

		out = transform(outs, self.tattn_w, self.tattn_drop)

		# hl: (bsize, 1, isize, num_layer + 1)
		hl = transform(hl, self.sc_tattn_w, self.sc_tattn_drop)

		return out, hl
