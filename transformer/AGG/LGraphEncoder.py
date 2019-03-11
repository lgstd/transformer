#encoding: utf-8

from torch import nn
from modules import *
from math import sqrt

from transformer.Encoder import EncoderLayer as EncoderLayerUnit
from transformer.Encoder import Encoder as EncoderBase

# vocabulary:
#	<pad>:0
#	<unk>:1
#	<eos>:2
#	<sos>:3
#	...
# for the classier of the decoder, <sos> is omitted

class EncoderLayerBase(nn.Module):

	# isize: input size
	# fhsize: hidden size of PositionwiseFeedForward
	# attn_drop: dropout for MultiHeadAttention
	# num_head: number of heads in MultiHeadAttention
	# ahsize: hidden size of MultiHeadAttention

	def __init__(self, isize, fhsize=None, dropout=0.0, attn_drop=0.0, num_head=8, ahsize=None, num_sub=1):

		_ahsize = isize if ahsize is None else ahsize

		_fhsize = _ahsize * 4 if fhsize is None else fhsize

		super(EncoderLayerBase, self).__init__()

		self.nets = nn.ModuleList([EncoderLayerUnit(isize, _fhsize, dropout, attn_drop, num_head, _ahsize) for i in range(num_sub)])

		self.combiner = ResidueCombiner(isize, num_sub, _fhsize)

	# inputs: input of this layer (bsize, seql, isize)

	def forward(self, inputs, mask=None):

		out = inputs
		outs = []
		for net in self.nets:
			out = net(out, mask)
			outs.append(out)

		return self.combiner(*outs)

class EncoderLayerStack(nn.Module):

	# isize: input size
	# fhsize: hidden size of PositionwiseFeedForward
	# attn_drop: dropout for MultiHeadAttention
	# num_head: number of heads in MultiHeadAttention
	# ahsize: hidden size of MultiHeadAttention

	def __init__(self, isize, fhsize=None, dropout=0.0, attn_drop=0.0, num_head=8, ahsize=None, num_sub=1):

		_ahsize = isize if ahsize is None else ahsize

		_fhsize = _ahsize * 4 if fhsize is None else fhsize

		super(EncoderLayerStack, self).__init__()

		self.nets = nn.ModuleList([EncoderLayerUnit(isize, _fhsize, dropout, attn_drop, num_head, _ahsize) for i in range(num_sub)])

	# inputs: input of this layer (bsize, seql, isize)

	def forward(self, inputs, mask=None):

		out = inputs
		for net in self.nets:
			out = net(out, mask)

		return out

class EncoderLayer(nn.Module):

	# isize: input size
	# fhsize: hidden size of PositionwiseFeedForward
	# attn_drop: dropout for MultiHeadAttention
	# num_head: number of heads in MultiHeadAttention
	# ahsize: hidden size of MultiHeadAttention

	def __init__(self, isize, fhsize=None, dropout=0.0, attn_drop=0.0, num_head=8, ahsize=None, num_sub=1, num_unit=1):

		_ahsize = isize if ahsize is None else ahsize

		_fhsize = _ahsize * 4 if fhsize is None else fhsize

		super(EncoderLayer, self).__init__()

		self.nets = nn.ModuleList([EncoderLayerBase(isize, _fhsize, dropout, attn_drop, num_head, _ahsize, num_unit) for i in range(num_sub)])

		self.combiner = ResidueCombiner(isize, num_sub, _fhsize)

	# inputs: input of this layer (bsize, seql, isize)

	def forward(self, inputs, mask=None):

		out = inputs
		outs = []
		for net in self.nets:
			out = net(out, mask)
			outs.append(out)

		return self.combiner(*outs)


class Encoder(EncoderBase):

	# isize: size of word embedding
	# nwd: number of words
	# num_layer: number of encoder layers
	# fhsize: number of hidden units for PositionwiseFeedForward
	# attn_drop: dropout for MultiHeadAttention
	# num_head: number of heads in MultiHeadAttention
	# xseql: maxmimum length of sequence
	# ahsize: number of hidden units for MultiHeadAttention

	def __init__(self, isize, nwd, num_layer, fhsize=None, dropout=0.0, attn_drop=0.0, num_head=8, xseql=512, ahsize=None, norm_output=False, num_sub=1, num_unit=1):

		_ahsize = isize if ahsize is None else ahsize

		_fhsize = _ahsize * 4 if fhsize is None else fhsize

		super(Encoder, self).__init__(isize, nwd, num_layer, _fhsize, dropout, attn_drop, num_head, xseql, _ahsize, norm_output)

		self.nets = nn.ModuleList([EncoderLayer(isize, _fhsize, dropout, attn_drop, num_head, _ahsize, num_sub, num_unit), EncoderLayerStack(isize, _fhsize, dropout, attn_drop, num_head, _ahsize, num_layer - num_sub * num_unit)])

	def load_base(self, base_encoder):

		self.drop = base_encoder.drop

		self.wemb = base_encoder.wemb

		self.pemb = base_encoder.pemb

		_nets = base_encoder.nets

		net = list(self.nets.modules())
		net[0].nets[0].nets = nn.ModuleList(_nets[:2])
		net[0].nets[1].nets = nn.ModuleList(_nets[2:4])
		net[1].nets = nn.ModuleList(_nets[4:])

		self.out_normer = None if self.out_normer is None else base_encoder.out_normer
		self.nets[-1].combiner.out_normer = base_encoder.out_normer