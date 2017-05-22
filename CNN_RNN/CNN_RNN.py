import tensorflow as tf
import tensorlayer as tl
import matplotlib.pyplot as plt
import numpy as np
from math import sqrt
import os


class CNN_RNN:
	def __init__(self, input_data_shape, output_data_shape):

		self.batch_size = 100
		self.shuffle_min_after_dequeue = 600
		self.shuffle_capacity = self.shuffle_min_after_dequeue + 3 * self.batch_size
		self.learning_rate = 0.001
		self.weight_decay = 0.01
		self.keep_rate = 0.75
		beta_1 = 0.9
		beta_2 = 0.999
		self.input_temporal = input_data_shape[0]
		self.input_vertical = input_data_shape[1]
		self.input_horizontal = input_data_shape[2]
		self.input_channel = input_data_shape[3]

		self.output_temporal = output_data_shape[0]
		self.output_vertical = output_data_shape[1]
		self.output_horizontal = output_data_shape[2]
		self.output_channel = 1
		self.predictor_output = self.output_temporal * self.output_vertical * self.output_horizontal * self.output_channel

		self.RNN_num_layers = 3
		self.RNN_num_step = 6
		self.RNN_hidden_node_size = 150

		# placeholder
		# with tf.device('/cpu:0'):
		self.Xs = tf.placeholder(tf.float32, shape=[
			None, self.input_temporal, self.input_vertical, self.input_horizontal, self.input_channel], name='Input_x')
		self.Ys = tf.placeholder(tf.float32, shape=[
			None, self.output_temporal, self.output_vertical, self.output_horizontal, 1], name='Input_y')
		self.keep_prob = tf.placeholder(tf.float32, name='keep_prob')
		self.norm = tf.placeholder(tf.bool, name='norm')
		self.RNN_init_state = tf.placeholder(tf.float32, [self.RNN_num_layers, 2, None, self.RNN_hidden_node_size])  # 2: hidden state and cell state

		# operation
		'''
		self.RNN_states_series, self.RNN_current_state = self._build_RNN_network_tf(network, self.keep_prob)
		RNN_last_output = tf.unpack(tf.transpose(self.RNN_states_series, [1, 0, 2]))  # a (batch_size, state_size) list with len num_step
		output_layer = tf.add(tf.matmul(RNN_last_output[-1], self.weights['output_layer']), self.bias['output_layer'])
		'''
		# network = tl.layers.DenseLayer(self.tl_RNN_output, n_units=200, act=tf.nn.relu, name='dense_layer')
		# network = tl.layers.DropoutLayer(network, keep=0.7, name='drop_1')

		network = self._build_CNN_RNN(self.Xs)
		flat_tl = tl.layers.FlattenLayer(network, name='flatten_layer')
		self.tl_share_output = flat_tl
		self.multi_task_dic = {}
		self.multi_task_dic['normal'] = self._create_MTL_output(self.tl_share_output, self.Ys, 'normal')
		self.multi_task_dic['max_traffic'] = self._create_MTL_output(self.tl_share_output, self.Ys, 'max_traffic')
		self.multi_task_dic['avg_traffic'] = self._create_MTL_output(self.tl_share_output, self.Ys, 'avg_traffic')
		self.multi_task_dic['min_traffic'] = self._create_MTL_output(self.tl_share_output, self.Ys, 'min_traffic')
		self.saver = tf.train.Saver()

	def _build_RNN(self, Xs):
		def build_RNN_network(input_X, is_training=1):
			with tf.variable_scope('RNN'):
				network = tl.layers.FlattenLayer(input_X, name='flatten_layer_1')
				print('rnn input {}'.format(network.outputs.get_shape().as_list()))
				network = tl.layers.ReshapeLayer(network, shape=[-1, self.RNN_num_step, self.input_channel * self.input_vertical * self.input_vertical], name='reshape_layer_1')
				network = tl.layers.BatchNormLayer(network, name='batchnorm_layer_1')
				print('rnn input {}'.format(network.outputs.get_shape().as_list()))
				network = tl.layers.BiRNNLayer(
					network,
					cell_fn=tf.nn.rnn_cell.LSTMCell,
					n_hidden=self.RNN_hidden_node_size,
					initializer=tf.random_uniform_initializer(-0.1, 0.1),
					n_steps=self.RNN_num_step,
					fw_initial_state=None,
					bw_initial_state=None,
					return_last=True,
					return_seq_2d=False,
					n_layer=self.RNN_num_layers,
					dropout=(self.keep_rate, self.keep_rate),
					name='layer_1')
				# print('rnn output {}'.format(network.outputs.get_shape().as_list()))
			return network

		tl_input = tl.layers.InputLayer(Xs, name='input_layer')
		RNN_tl_output = build_RNN_network(tl_input)
		return RNN_tl_output

	def _build_3D_CNN(self, Xs):
		def build_CNN_network(input_X, is_training=1):
			with tf.variable_scope('CNN'):
				CNN_input = tf.reshape(input_X, [-1, self.input_temporal, self.input_vertical, self.input_horizontal, self.input_channel])
				# print('CNN_input shape:{}'.format(CNN_input))
				network = tl.layers.InputLayer(CNN_input, name='input_layer')
				network = tl.layers.BatchNormLayer(network, name='batchnorm_layer_1')
				network = tl.layers.Conv3dLayer(
					network,
					act=tf.nn.relu,
					shape=[3, 5, 5, 1, 32],
					strides=[1, 2, 2, 2, 1],
					padding='SAME',
					name='Con3d_layer_1')
				network = tl.layers.PoolLayer(
					network,
					ksize=[1, 2, 2, 2, 1],
					strides=[1, 1, 2, 2, 1],
					padding='SAME',
					pool=tf.nn.max_pool3d,
					name='pooling_layer_1')

				network = tl.layers.Conv3dLayer(
					network,
					act=tf.nn.relu,
					shape=[3, 5, 5, 32, 64],
					strides=[1, 2, 2, 2, 1],
					padding='SAME',
					name='Con3d_layer_2')
				network = tl.layers.DropoutLayer(network, keep=self.keep_rate, name='drop_1')
				network = tl.layers.PoolLayer(
					network,
					ksize=[1, 2, 2, 2, 1],
					strides=[1, 1, 1, 1, 1],
					padding='SAME',
					pool=tf.nn.avg_pool3d,
					name='pooling_layer_2')
				network = tl.layers.BatchNormLayer(network, name='batchnorm_layer_2')

				network = tl.layers.Conv3dLayer(
					network,
					act=tf.nn.relu,
					shape=[3, 5, 5, 64, 64],
					strides=[1, 2, 2, 2, 1],
					padding='SAME',
					name='Con3d_layer_3')
				network = tl.layers.PoolLayer(
					network,
					ksize=[1, 2, 2, 2, 1],
					strides=[1, 1, 1, 1, 1],
					padding='SAME',
					pool=tf.nn.avg_pool3d,
					name='pooling_layer_3')
				network = tl.layers.DropoutLayer(network, keep=self.keep_rate, name='drop_2')
			return network

		tl_3D_CNN_output = build_CNN_network(Xs)
		return tl_3D_CNN_output
	
	def _build_CNN_RNN(self, Xs):

		def build_CNN_network(input_X, is_training=1):
			with tf.variable_scope('CNN'):
				CNN_input = tf.reshape(input_X, [-1, self.input_vertical, self.input_horizontal, self.input_channel])
				# print('CNN_input shape:{}'.format(CNN_input))
				network = tl.layers.InputLayer(CNN_input, name='input_layer')
				network = tl.layers.BatchNormLayer(network, name='batchnorm_layer_1')
				network = tl.layers.Conv2dLayer(
					network,
					act=tf.nn.relu,
					shape=[5, 5, 1, 64],
					strides=[1, 1, 1, 1],
					padding='SAME',
					name='cnn_layer_1')

				network = tl.layers.PoolLayer(
					network,
					ksize=[1, 2, 2, 1],
					strides=[1, 2, 2, 1],
					padding='SAME',
					pool=tf.nn.max_pool,
					name='pool_layer_1')
				network = tl.layers.DropoutLayer(network, keep=self.keep_rate, name='drop_1')
				network = tl.layers.Conv2dLayer(
					network,
					act=tf.nn.relu,
					shape=[5, 5, 64, 64],
					strides=[1, 1, 1, 1],
					padding='SAME',
					name='cnn_layer_2')

				network = tl.layers.PoolLayer(
					network,
					ksize=[1, 2, 2, 1],
					strides=[1, 1, 1, 1],
					padding='SAME',
					pool=tf.nn.avg_pool,
					name='pool_layer_2')
				network = tl.layers.DropoutLayer(network, keep=self.keep_rate, name='drop_2')
				# network = tl.layers.FlattenLayer(network, name='flatten_layer')

				# network = tl.layers.DenseLayer(network, n_units=512, act=tf.nn.relu, name='fc_1')
				# network = tl.layers.DropoutLayer(network, keep=0.7, name='drop_3')
				print('network output shape:{}'.format(network.outputs.get_shape()))
				return network

		def build_bi_RBB_network(input_X, is_training=1):
			# print('rnn network input shape :{}'.format(input_X.outputs.get_shape()))
			with tf.variable_scope('BI_RNN'):
				input_X = tl.layers.BatchNormLayer(input_X, name='batchnorm_layer_1')
				network = tl.layers.ReshapeLayer(input_X, shape=[-1, self.RNN_num_step, int(input_X.outputs._shape[-1])], name='reshape_layer_1')

				network = tl.layers.BiRNNLayer(
					network,
					cell_fn=tf.nn.rnn_cell.LSTMCell,
					n_hidden=self.RNN_hidden_node_size,
					initializer=tf.random_uniform_initializer(-0.1, 0.1),
					n_steps=self.RNN_num_step,
					fw_initial_state=None,
					bw_initial_state=None,
					return_last=True,
					return_seq_2d=False,
					n_layer=self.RNN_num_layers,
					dropout=(self.keep_rate, self.keep_rate),
					name='layer_1')
				'''
				if is_training:
					network = tl.layers.DropoutLayer(network, keep=self.keep_rate, name='drop_1')
				network = tl.layers.BiRNNLayer(
					network,
					cell_fn=tf.nn.rnn_cell.LSTMCell,
					n_hidden=self.RNN_hidden_node_size,
					initializer=tf.random_uniform_initializer(-0.1, 0.1),
					n_steps=self.RNN_num_step,
					fw_initial_state=None,
					bw_initial_state=None,
					return_last=False,
					return_seq_2d=False,
					name='layer_2')
				if is_training:
					network = tl.layers.DropoutLayer(network, keep=self.keep_rate, name='drop_2')

				network = tl.layers.BiRNNLayer(
					network,
					cell_fn=tf.nn.rnn_cell.LSTMCell,
					n_hidden=self.RNN_hidden_node_size,
					initializer=tf.random_uniform_initializer(-0.1, 0.1),
					n_steps=self.RNN_num_step,
					fw_initial_state=None,
					bw_initial_state=None,
					return_last=True,
					return_seq_2d=False,
					name='layer_3')
				if is_training:
					network = tl.layers.DropoutLayer(network, keep=self.keep_rate, name='drop_3')
				'''
				return network

		def build_RNN_network(input_X, is_training=1):
			print('rnn network input shape :{}'.format(input_X.outputs.get_shape()))
			# network = tl.layers.FlattenLayer(input_X, name='flatten_layer')  # [batch_size, mask_row, mask_col, n_mask] —> [batch_size, mask_row * mask_col * n_mask]
			with tf.variable_scope('RNN'):
				input_X = tl.layers.BatchNormLayer(input_X, name='batchnorm_layer_1')
				network = tl.layers.ReshapeLayer(input_X, shape=[-1, self.RNN_num_step, int(input_X.outputs._shape[-1])], name='reshape_layer_1')
				network = tl.layers.RNNLayer(
					network,
					cell_fn=tf.nn.rnn_cell.GRUCell,
					# cell_init_args={'forget_bias': 0.0},
					n_hidden=self.RNN_hidden_node_size,
					initializer=tf.random_uniform_initializer(-0.1, 0.1),
					n_steps=self.RNN_num_step,
					initial_state=None,
					return_last=False,
					return_seq_2d=False,  # trigger with return_last is False. if True, return shape: (?, 200); if False, return shape: (?, 6, 200)
					name='layer_1')
				if is_training:
					network = tl.layers.DropoutLayer(network, keep=self.keep_rate, name='drop_1')
				network = tl.layers.RNNLayer(
					network,
					cell_fn=tf.nn.rnn_cell.GRUCell,
					# cell_init_args={'forget_bias': 0.0},
					n_hidden=self.RNN_hidden_node_size,
					initializer=tf.random_uniform_initializer(-0.1, 0.1),
					n_steps=self.RNN_num_step,
					initial_state=None,
					return_last=False,
					return_seq_2d=False,  # trigger with return_last is False. if True, return shape: (?, 200); if False, return shape: (?, 6, 200)
					name='layer_2')
				if is_training:
					network = tl.layers.DropoutLayer(network, keep=self.keep_rate, name='drop_2')
				'''
				network = tl.layers.RNNLayer(
					network,
					cell_fn=tf.nn.rnn_cell.GRUCell,
					# cell_init_args={'forget_bias': 0.0},
					n_hidden=self.RNN_hidden_node_size,
					initializer=tf.random_uniform_initializer(-0.1, 0.1),
					n_steps=self.RNN_num_step,
					initial_state=None,
					return_last=False,
					return_seq_2d=False,  # trigger with return_last is False. if True, return shape: (?, 200); if False, return shape: (?, 6, 200)
					name='basic_lstm_layer_3')
				if is_training:
					network = tl.layers.DropoutLayer(network, keep=self.keep_rate, name='drop_3')
				'''
				network = tl.layers.RNNLayer(
					network,
					cell_fn=tf.nn.rnn_cell.GRUCell,
					# cell_init_args={'forget_bias': 0.0},
					n_hidden=self.RNN_hidden_node_size,
					initializer=tf.random_uniform_initializer(-0.1, 0.1),
					n_steps=self.RNN_num_step,
					initial_state=None,
					return_last=True,
					return_seq_2d=False,  # trigger with return_last is False. if True, return shape: (?, 200); if False, return shape: (?, 6, 200)
					name='layer_3')
				if is_training:
					network = tl.layers.DropoutLayer(network, keep=self.keep_rate, name='drop_3')
			'''
			network = tl.layers.DynamicRNNLayer(
				network,
				cell_fn=tf.nn.rnn_cell.BasicLSTMCell,
				n_hidden=64,
				initializer=tf.random_uniform_initializer(-0.1, 0.1),
				n_steps=num_step,
				return_last=False,
				return_seq_2d=True,
				name='basic_lstm_layer_2')
			'''
			return network		

		def build_inception_CNN_network(input_X, is_training=1):
			filter_map_1 = 32
			filter_map_2 = 32
			reduce1x1 = 16

			def create_inception(input_tl, filter_map_size, reduce_size, scope_name):
				input_shape = input_tl.outputs.get_shape().as_list()
				input_channel = input_shape[-1]
				with tf.variable_scope(scope_name):
					conv1_1x1_1 = tl.layers.Conv2dLayer(
						input_tl,
						act=tf.nn.relu,
						shape=[1, 1, input_channel, filter_map_size],
						strides=[1, 1, 1, 1],
						name='inception_1x1_1')
					conv1_1x1_1 = tl.layers.DropoutLayer(conv1_1x1_1, keep=self.keep_rate, name='drop_1')

					conv1_1x1_2 = tl.layers.Conv2dLayer(
						input_tl,
						act=tf.nn.relu,
						shape=[1, 1, input_channel, reduce_size],
						strides=[1, 1, 1, 1],
						name='inception_1x1_2')
					conv1_1x1_2 = tl.layers.DropoutLayer(conv1_1x1_2, keep=self.keep_rate, name='drop_2')

					conv1_1x1_3 = tl.layers.Conv2dLayer(
						input_tl,
						act=tf.nn.relu,
						shape=[1, 1, input_channel, reduce_size],
						strides=[1, 1, 1, 1],
						name='inception_1x1_3')
					conv1_1x1_3 = tl.layers.DropoutLayer(conv1_1x1_3, keep=self.keep_rate, name='drop_3')

					conv1_3x3 = tl.layers.Conv2dLayer(
						conv1_1x1_2,
						act=tf.nn.relu,
						shape=[3, 3, reduce_size, filter_map_size],
						strides=[1, 1, 1, 1],
						name='inception_3x3')
					conv1_3x3 = tl.layers.DropoutLayer(conv1_3x3, keep=self.keep_rate, name='drop_4')

					conv1_5x5 = tl.layers.Conv2dLayer(
						conv1_1x1_3,
						act=tf.nn.relu,
						shape=[5, 5, reduce_size, filter_map_size],
						strides=[1, 1, 1, 1],
						name='inception_5x5')
					conv1_5x5 = tl.layers.DropoutLayer(conv1_5x5, keep=self.keep_rate, name='drop_5')
					max_pool1 = tl.layers.PoolLayer(
						input_tl,
						ksize=[1, 3, 3, 1],
						strides=[1, 1, 1, 1],
						padding='SAME',
						pool=tf.nn.max_pool,
						name='inception_pool_layer_1')

					conv1_1x1_4 = tl.layers.Conv2dLayer(
						max_pool1,
						act=tf.nn.relu,
						shape=[1, 1, input_channel, filter_map_size],
						strides=[1, 1, 1, 1],
						name='inception1_1x1_4')
					conv1_1x1_4 = tl.layers.DropoutLayer(conv1_1x1_4, keep=self.keep_rate, name='drop_8')
					inception = tl.layers.ConcatLayer(layer=[conv1_1x1_1, conv1_3x3, conv1_5x5, conv1_1x1_4], concat_dim=3, name='concate_layer1')
					return inception

			with tf.variable_scope('CNN'):
				CNN_input = tf.reshape(input_X, [-1, self.input_vertical, self.input_horizontal, self.input_channel])
				print('CNN_input shape:{}'.format(CNN_input))
				network = tl.layers.InputLayer(CNN_input, name='input_layer')
				network = tl.layers.BatchNormLayer(network, name='batchnorm_layer_1')
				'''
				network_5x5 = tl.layers.Conv2dLayer(
					network,
					act=tf.nn.relu,
					shape=[5, 5, 1, 32],
					strides=[1, 1, 1, 1],
					padding='SAME',
					name='cnn_layer_5x5')
				network_5x5 = tl.layers.PoolLayer(
					network_5x5,
					ksize=[1, 2, 2, 1],
					strides=[1, 2, 2, 1],
					padding='SAME',
					pool=tf.nn.avg_pool,
					name='pool_layer_5x5')

				network_3x3 = tl.layers.Conv2dLayer(
					network,
					act=tf.nn.relu,
					shape=[3, 3, 1, 32],
					strides=[1, 1, 1, 1],
					padding='SAME',
					name='cnn_layer_3x3')
				network_3x3 = tl.layers.PoolLayer(
					network_3x3,
					ksize=[1, 2, 2, 1],
					strides=[1, 2, 2, 1],
					padding='SAME',
					pool=tf.nn.avg_pool,
					name='pool_layer_3x3')
				network = tl.layers.ConcatLayer(layer=[network_5x5, network_3x3], concat_dim=3, name='concate_layer1')
				network = tl.layers.DropoutLayer(network, keep=self.keep_rate, name='drop_1')
				'''
				inception = create_inception(network, filter_map_1, reduce1x1, 'inception_1')
				# inception1 = tl.layers.DropoutLayer(inception1, keep=self.keep_rate, name='drop_2')
				inception = tl.layers.PoolLayer(
					inception,
					ksize=[1, 2, 2, 1],
					strides=[1, 2, 2, 1],
					padding='SAME',
					pool=tf.nn.max_pool,
					name='pool_layer_1')
				print('network output shape:{}'.format(inception.outputs.get_shape()))
				return inception

		with tf.variable_scope('CNN_RNN'):
			tl_CNN_output = build_CNN_network(Xs, is_training=1)

			network = tl.layers.FlattenLayer(tl_CNN_output, name='flatten_layer')
			network = tl.layers.BatchNormLayer(network, name='batchnorm_layer_1')

			tl_RNN_output = build_bi_RBB_network(network, is_training=1)

		return tl_RNN_output

	def _create_Non_MTL_output(self):
		# non MTL
		'''
		self.tl_output_layer = tl.layers.DenseLayer(self.tl_RNN_output, n_units=predictor_output, act=tl.activation.identity, name='output_layer_op')
		output_layer = self.tl_output_layer.outputs

		self.output_layer = tf.reshape(output_layer, [-1, self.output_temporal, self.output_vertical, self.output_horizontal, self.output_channel], name='self.output_layer')

		MSE = tf.reduce_mean(tf.pow(self.output_layer - self.Ys, 2), name='MSE_op')
		RMSE = tf.sqrt(tf.reduce_mean(tf.pow(self.output_layer - self.Ys, 2)))
		MAE = tf.reduce_mean(tf.abs(self.output_layer - self.Ys))
		# MAPE = tf.reduce_mean(tf.divide(tf.abs(self.Ys - self.output_layer), self.Ys))
		L2 = self._L2_norm(tf.trainable_variables())
		cost_op = tf.add(MSE, L2 * self.weight_decay, name='cost_op')
		self.loss_dic = {
			'cost': cost_op,
			'L2_loss': L2,
			'AE_loss': MAE,
			'RMSE': RMSE,
			'MSE': MSE}

		optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate, beta1=beta_1, beta2=beta_2)
		opt_vars = tf.trainable_variables()
		gvs = optimizer.compute_gradients(cost_op, var_list=opt_vars)
		capped_gvs = [(tf.clip_by_norm(grad, 5), var) for grad, var in gvs if grad is not None]
		self.optimizer_op = optimizer.apply_gradients(capped_gvs)
		'''

	def create_MTL_task(self):
		pass

	def _create_MTL_output(self, tl_input, y, scope_name):
		def get_l2_list():
			# print('get_l2_list:')
			var_list = []
			exclude_list = ['LSTMCell/B', 'regression_op/b', 'b_conv2d']
			for v in tf.trainable_variables():
				if any(x in v.name for x in exclude_list):
					continue
				if 'prediction_layer' in v.name and scope_name not in v.name:
					continue
				# print(v)
				var_list.append(v)
			return var_list

		def get_trainable_var():
			# print('get_trainable_var:')
			var_list = []
			for v in tf.trainable_variables():
				if 'prediction_layer' in v.name:
					if scope_name not in v.name:
						continue
				# print(v)
				var_list.append(v)
			return var_list

		def get_prediction_layer_var():
			var_list = []
			for v in tf.trainable_variables():
				if 'prediction_layer' in v.name:
					if scope_name in v.name:
						var_list.append(v)
						# print(v)
			return var_list

		with tf.variable_scope('prediction_layer'):
			with tf.variable_scope(scope_name):
				tl_regression = tl.layers.DenseLayer(tl_input, n_units=self.predictor_output, act=tl.activation.identity, name='regression_op')
				tl_regression = tl.layers.DropoutLayer(tl_regression, keep=0.8, name='drop_1')
				tl_output = tl_regression
				regression_output = tl_output.outputs
				# print('regression_output shape {}'.format(regression_output.get_shape().as_list()))
				output = tf.reshape(regression_output, [-1, self.output_temporal, self.output_vertical, self.output_horizontal, self.output_channel], name='output_layer')

				MSE = tf.reduce_mean(tf.pow(output - y, 2), name='MSE_op')
				RMSE = tf.sqrt(tf.reduce_mean(tf.pow(output - y, 2)))
				MAE = tf.reduce_mean(tf.abs(output - y))
				MAPE = tf.reduce_mean(tf.divide(tf.abs(y - output), tf.reduce_mean(y)), name='MAPE_OP')
				L2_list = get_l2_list()
				L2_loss = self._L2_norm(L2_list)
				cost = tf.add(MSE, L2_loss * self.weight_decay, name='cost_op')

				optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate)

				opt_vars = get_trainable_var()
				gvs = optimizer.compute_gradients(cost, var_list=opt_vars)
				capped_gvs = [(tf.clip_by_norm(grad, 5), var) for grad, var in gvs if grad is not None]
				optimizer_op = optimizer.apply_gradients(capped_gvs)

				optimizer_predict = tf.train.AdamOptimizer(learning_rate=self.learning_rate)
				only_prediction_opt_vars = get_prediction_layer_var()
				gvs_predict = optimizer_predict.compute_gradients(MAE, var_list=only_prediction_opt_vars)
				capped_gvs_predict = [(tf.clip_by_norm(grad, 5), var) for grad, var in gvs_predict if grad is not None]
				optimizer_op_predict = optimizer.apply_gradients(capped_gvs_predict)
				task_dic = {
					'output': output,
					'optomizer': optimizer_op,
					'prediction_optimizer': optimizer_op_predict,
					'tl_output': tl_output,
					'cost': cost,
					'L2_loss': L2_loss,
					'MSE': MSE,
					'MAE': MAE,
					'MAPE': MAPE,
					'RMSE': RMSE,
					'training_cost_history': [],
					'testing_cost_history': []
				}
				return task_dic

	def _L2_norm(self, var_list):
		L2_loss = tf.add_n([tf.nn.l2_loss(v) for v in var_list])
		return L2_loss

	def _build_RNN_network_tf(self, input_X, keep_rate):
		def _get_states():
			state_per_layer_list = tf.unpack(self.RNN_init_state, axis=0)
			rnn_tuple_state = tuple(
				[tf.nn.rnn_cell.LSTMStateTuple(state_per_layer_list[idx][0], state_per_layer_list[idx][1]) for idx in range(self.RNN_num_layers)])
			return rnn_tuple_state
		with tf.variable_scope('RNN'):
			input_X = input_X.outputs
			print('rnn network input shape :{}'.format(input_X.get_shape()))
			input_X = tf.reshape(input_X, [-1, self.RNN_num_step, input_X.get_shape().as_list()[-1]])
			print('rnn reshape input shape :{}'.format(input_X.get_shape()))
			RNN_cell = tf.nn.rnn_cell.BasicLSTMCell(self.RNN_hidden_node_size, state_is_tuple=True)
			RNN_cell = tf.nn.rnn_cell.DropoutWrapper(RNN_cell, output_keep_prob=keep_rate)
			RNN_cell = tf.nn.rnn_cell.MultiRNNCell([RNN_cell] * self.RNN_num_layers, state_is_tuple=True)

			status_tuple = _get_states()
			states_series, current_state = tf.nn.dynamic_rnn(RNN_cell, input_X, initial_state=status_tuple, time_major=False)

		return states_series, current_state

	def _weight_variable(self, shape, name):
		# initial = tf.truncated_normal(shape, stddev=0.1)
		initial = np.random.randn(*shape) * sqrt(2.0 / np.prod(shape))
		return tf.Variable(initial, dtype=tf.float32, name=name)

	def _bias_variable(self, shape, name):
		# initial = tf.random_normal(shape)
		initial = np.random.randn(*shape) * sqrt(2.0 / np.prod(shape))
		return tf.Variable(initial, dtype=tf.float32, name=name)

	def _write_to_Tfrecord(self, X_array, Y_array, filename):
		writer = tf.python_io.TFRecordWriter(filename)
		for index, each_record in enumerate(X_array):
			tensor_record = each_record.astype(np.float32).tobytes()
			tensor_result = Y_array[index].astype(np.float32).tobytes()
			# print('in _write_to_Tfrecord',X_array.shape,Y_array.shape)
			example = tf.train.Example(features=tf.train.Features(feature={
				'index': tf.train.Feature(int64_list=tf.train.Int64List(value=[index])),
				'record': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tensor_record])),
				'result': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tensor_result]))
			}))

			writer.write(example.SerializeToString())
		writer.close()

	def _read_data_from_Tfrecord(self, filename):
		filename_queue = tf.train.string_input_producer([filename])
		reader = tf.TFRecordReader()
		_, serialized_example = reader.read(filename_queue)
		features = tf.parse_single_example(
			serialized_example,
			features={
				'index': tf.FixedLenFeature([], tf.int64),
				'record': tf.FixedLenFeature([], tf.string),
				'result': tf.FixedLenFeature([], tf.string)
			})
		index = features['index']
		record = tf.decode_raw(features['record'], tf.float32)
		result = tf.decode_raw(features['result'], tf.float32)
		record = tf.reshape(record, [
			self.input_temporal,
			self.input_vertical,
			self.input_horizontal,
			self.input_channel])
		result = tf.reshape(result, [
			self.Y_temporal,
			self.Y_vertical,
			self.Y_horizontal,
			self.Y_channel])

		return index, record, result

	def _read_all_data_from_Tfreoced(self, filename):
		record_iterator = tf.python_io.tf_record_iterator(path=filename)
		record_list = []
		result_list = []
		for string_record in record_iterator:
			example = tf.train.Example()
			example.ParseFromString(string_record)
			index = example.features.feature['index'].int64_list.value[0]
			record = example.features.feature['record'].bytes_list.value[0]
			result = example.features.feature['result'].bytes_list.value[0]
			record = np.fromstring(record, dtype=np.float32)
			record = record.reshape((
				self.input_temporal,
				self.input_vertical,
				self.input_horizontal,
				self.input_channel))

			result = np.fromstring(result, dtype=np.float32)
			result = result.reshape((
				self.Y_temporal,
				self.Y_vertical,
				self.Y_horizontal,
				self.Y_channel))
			record_list.append(record)
			result_list.append(result)

		record = np.stack(record_list)
		result = np.stack(result_list)
		return index, record, result

	def _save_model(self, sess, model_path):
		# model_path = './output_model/CNN_RNN.ckpt'
		print('saving model.....')
		try:
			save_path = self.saver.save(sess, model_path)
			# self.pre_train_saver.save(sess, model_path + '_part')
		except Exception:
			save_path = self.saver.save(sess, './output_model/temp.ckpt')
		finally:
			print('save_path{}'.format(save_path))

	def _reload_model(self, sess, model_path):
		print('reloading model {}.....'.format(model_path))
		self.saver.restore(sess, model_path)

	def _print_all_tensor(self):
		graph = tf.get_default_graph()
		all_vars = [n.name for n in graph.as_graph_def().node]
		for var_s in all_vars:
			print(var_s)

	def _print_all_trainable_var(self):
		vars_list = tf.trainable_variables()
		for var_s in vars_list:
			print(var_s)

	def print_all_layers(self):
		self.tl_share_output.print_layers()

	def print_all_variables(self):
		self.tl_share_output.print_params()

	def set_training_data(self, input_x, input_y):

		print('input_x shape:{}'.format(input_x.shape))
		print('input_y shape:{}'.format(input_y.shape))
		self.Y_temporal = input_y.shape[1]
		self.Y_vertical = input_y.shape[2]
		self.Y_horizontal = input_y.shape[3]
		self.Y_channel = input_y.shape[4]
		# input_x, self.mean, self.std = self.feature_normalize_input_data(input_x)
		self.mean = 0
		self.std = 1
		X_data = input_x
		Y_data = input_y

		# Y_data = Y_data[:,np.newaxis]
		# print(X_data[1,0,0,0,-1],Y_data[0,0,0,0,-1])
		training_X = X_data[0:int(9 * X_data.shape[0] / 10)]
		training_Y = Y_data[0:int(9 * Y_data.shape[0] / 10)]
		self.testing_X = X_data[int(9 * X_data.shape[0] / 10):]
		self.testing_Y = Y_data[int(9 * Y_data.shape[0] / 10):]
		self.training_file = 'training.tfrecoeds'
		self.testing_file = 'testing.tfrecoeds'
		print('training X shape:{}, training Y shape:{}'.format(
			training_X.shape, training_Y.shape))
		self._write_to_Tfrecord(training_X, training_Y, self.training_file)
		self._write_to_Tfrecord(self.testing_X, self.testing_Y, self.testing_file)
		self.training_data_number = training_X.shape[0]

	def _testing_data(self, sess, test_x, test_y):
		predict_list = []
		cum_loss = 0
		batch_num = test_x.shape[0] // self.batch_size
		# _current_state = np.zeros([self.RNN_num_layers, 2, self.batch_size, self.RNN_hidden_node_size])
		# print('batch_num:', batch_num)
		for batch_index in range(batch_num):
			dp_dict = tl.utils.dict_to_one(self.tl_output_layer.all_drop)
			batch_x = test_x[batch_index * self.batch_size: (batch_index + 1) * self.batch_size]
			batch_y = test_y[batch_index * self.batch_size: (batch_index + 1) * self.batch_size]
			feed_dict = {
				self.Xs: batch_x,
				self.Ys: batch_y,
				self.keep_prob: 1,
				self.norm: 0}
			feed_dict.update(dp_dict)
			with tf.device('/gpu:0'):
				loss, predict = sess.run([self.loss_dic['MSE'], self.output_layer], feed_dict=feed_dict)
			'''
			for i in range(10, 15):
				for j in range(predict.shape[1]):
					print('batch index: {} predict:{:.4f} real:{:.4f}'.format(batch_index, predict[i, j, 0, 0, 0], batch_y[i, j, 0, 0, 0]))
			print()
			'''
			for predict_element in predict:
				predict_list.append(predict_element)
			cum_loss += loss
		return cum_loss / batch_num, np.stack(predict_list)

	def _MTL_testing_data(self, sess, test_x, test_y, task_name):
		task_dic = self.multi_task_dic[task_name]
		predict_list = []
		cum_MSE = 0
		cum_MAPE = 0
		batch_num = test_x.shape[0] // self.batch_size
		for batch_index in range(batch_num):
			dp_dict = tl.utils.dict_to_one(task_dic['tl_output'].all_drop)
			batch_x = test_x[batch_index * self.batch_size: (batch_index + 1) * self.batch_size]
			batch_y = test_y[batch_index * self.batch_size: (batch_index + 1) * self.batch_size]
			feed_dict = {
				self.Xs: batch_x,
				self.Ys: batch_y,
				self.keep_prob: 1,
				self.norm: 0}
			feed_dict.update(dp_dict)
			with tf.device('/gpu:0'):
				MSE, MAPE, predict = sess.run([task_dic['MSE'], task_dic['MAPE'], task_dic['output']], feed_dict=feed_dict)
			'''
			for i in range(10, 15):
				for j in range(predict.shape[1]):
					print('batch index: {} predict:{:.4f} real:{:.4f}'.format(batch_index, predict[i, j, 0, 0, 0], batch_y[i, j, 0, 0, 0]))
			print()
			'''
			for predict_element in predict:
				predict_list.append(predict_element)
			cum_MSE += MSE
			cum_MAPE += MAPE
		return cum_MSE / batch_num, 1 - (cum_MAPE / batch_num), np.stack(predict_list)

	def start_predict(self, testing_x, testing_y, model_path):
		print('input_x shape {}'.format(testing_x.shape))
		print('input_y shape {}'.format(testing_y.shape))
		# tf.reset_default_graph()
		# tf.train.import_meta_graph(model_path['reload_path'] + '.meta')
		self.print_all_layers()
		with tf.Session() as sess:
			loss = 0
			self._reload_model(sess, model_path['reload_path'])
			# self.print_all_variables()
			loss, predict = self._testing_data(sess, testing_x, testing_y)
		print('preddict finished!')
		print('prediction loss:{} predict array shape:{}'.format(loss, predict.shape))
		return loss, predict

	def start_train(self, model_path, reload=False):
		training_loss = 0
		display_step = 10
		train_his = {
			'epoch': [],
			'training_cost': [],
			'testing_cost': []
		}
		plt.ion()
		fig_1 = plt.figure(1)
		fig_2 = plt.figure(2)

		def _plot_loss_rate(history_data):
			# plt.subplot(1, 1, 1)
			ax = fig_1.add_subplot(1, 1, 1)
			ax.cla()
			ax.plot(history_data['epoch'], history_data['training_cost'], 'g-', label='training losses')
			ax.plot(history_data['epoch'], history_data['testing_cost'], 'b-', label='testing losses')

			# plt.plot(test_cost, 'r-', label='testing losses')
			ax.legend()
			# ax.draw()
			plt.pause(0.001)

		def _plot_predict_vs_real(testing_y, predict_y, training_x, predict_x):
			# print('real shape:{} predict shape:{}'.format(real.shape, predict.shape))
			ax1 = fig_2.add_subplot(2, 1, 1)
			ax2 = fig_2.add_subplot(2, 1, 2)
			ax1.cla()
			ax2.cla()
			ax1.plot(testing_y, label='real', marker='.')
			ax1.plot(predict_y, label='predict', marker='.')
			ax1.set_title('testing date')
			ax1.grid()
			ax1.legend()

			ax2.plot(training_x, label='real', marker='.')
			ax2.plot(predict_x, label='predict', marker='.')
			ax2.set_title('training date')
			ax2.grid()
			ax2.legend()
			# ax.draw()
			plt.pause(0.001)

		data = self._read_data_from_Tfrecord(self.training_file)
		batch_tuple_OP = tf.train.shuffle_batch(
			data,
			batch_size=self.batch_size,
			capacity=self.shuffle_capacity,
			min_after_dequeue=self.shuffle_min_after_dequeue)
		with tf.Session() as sess:
			coord = tf.train.Coordinator()
			treads = tf.train.start_queue_runners(sess=sess, coord=coord)
			tf.summary.FileWriter('logs/', sess.graph)
			if reload:
				self._reload_model(sess, model_path['reload_path'])
			else:
				sess.run(tf.global_variables_initializer())
			'''get batch sample'''
			_, batch_x_sample, batch_y_sample = sess.run(batch_tuple_OP)
			# _current_state = np.zeros([self.RNN_num_layers, 2, self.batch_size, self.RNN_hidden_node_size])
			with tf.device('/gpu:0'):
				for epoch in range(20000):
					index, batch_x, batch_y = sess.run(batch_tuple_OP)
					feed_dict = {
						self.Xs: batch_x,
						self.Ys: batch_y,
						self.keep_prob: 0.7,
						self.norm: 1}
					feed_dict.update(self.tl_output_layer.all_drop)
					_, cost, L2_loss = sess.run([self.optimizer_op, self.loss_dic['cost'], self.loss_dic['L2_loss']], feed_dict=feed_dict)
					training_loss += cost
					if epoch % display_step == 0 and epoch is not 0:
						'''testing'''
						index, testing_X, testing_Y = self._read_all_data_from_Tfreoced(self.testing_file)
						testing_loss, prediction = self._testing_data(sess, testing_X, testing_Y)
						training_loss = training_loss / display_step
						train_his['training_cost'].append(training_loss)
						train_his['epoch'].append(epoch)
						train_his['testing_cost'].append(testing_loss)

						training_loss_nodrop, train_prediction = self._testing_data(sess, batch_x_sample, batch_y_sample)
						print('epoch:{}, training cost:{:.4f}, L2_loss:{:.4f} training_MSE(nodrop):{:.4f} testing_MSE(nodrop):{:.4f}'.format(
							epoch,
							training_loss,
							L2_loss,
							training_loss_nodrop,
							testing_loss))

						_plot_loss_rate(train_his)
						_plot_predict_vs_real(
							testing_Y[:100, 0, 0, 0, 0],
							prediction[:100, 0, 0, 0, 0],
							batch_y_sample[:100, 0, 0, 0, 0],
							train_prediction[:100, 0, 0, 0, 0])
						training_loss = 0
					if epoch % 500 == 0 and epoch is not 0:
						self._save_model(sess, model_path['save_path'])
				coord.request_stop()
				coord.join(treads)
				print('training finished!')
			plt.ioff()
			plt.show()

	def start_MTL_predict(self, testing_x, testing_y, model_path):
		def get_multi_task_batch(batch_x, batch_y):
			batch_y = np.transpose(batch_y, [4, 0, 1, 2, 3])
			batch_y = np.expand_dims(batch_y, axis=5)
			return batch_x, batch_y
		print('input_x shape {}'.format(testing_x.shape))
		print('input_y shape {}'.format(testing_y.shape))
		testing_x, testing_y = get_multi_task_batch(testing_x, testing_y)
		# tf.reset_default_graph()
		# tf.train.import_meta_graph(model_path['reload_path'] + '.meta')

		self.print_all_layers()
		with tf.Session() as sess:
			self._reload_model(sess, model_path['reload_path'])
			testing_loss_min, testing_accu_min, prediction_min = self._MTL_testing_data(sess, testing_x, testing_y[0], 'min_traffic')
			testing_loss_avg, testing_accu_avg, prediction_avg = self._MTL_testing_data(sess, testing_x, testing_y[1], 'avg_traffic')
			testing_loss_max, testing_accu_max, prediction_max = self._MTL_testing_data(sess, testing_x, testing_y[2], 'max_traffic')
		print('preddict finished!')
		print('task Min: accu:{} MSE:{}'.format(testing_accu_min, testing_loss_min))
		print('task avg: accu:{} MSE:{}'.format(testing_accu_avg, testing_loss_avg))
		print('task Max: accu:{} MSE:{}'.format(testing_accu_max, testing_loss_max))

		return [prediction_min, prediction_avg, prediction_max]

	def start_MTL_train(self, model_path, reload=False):
		training_min_loss = 0
		training_max_loss = 0
		training_avg_loss = 0
		training_accu_min = 0
		training_accu_avg = 0
		training_accu_max = 0
		display_step = 50
		epoch_his = []
		plt.ion()
		loss_fig = plt.figure(0)
		min_fig = plt.figure(1)
		avg_fig = plt.figure(2)
		max_fig = plt.figure(3)

		def get_multi_task_batch(batch_x, batch_y):
			batch_y = np.transpose(batch_y, [4, 0, 1, 2, 3])
			batch_y = np.expand_dims(batch_y, axis=5)
			return batch_x, batch_y

		def run_task_optimizer(sess, batch_x, batch_y, task_name, optimizer='optomizer'):
			task_dic = self.multi_task_dic[task_name]
			feed_dict = {
				self.Xs: batch_x,
				self.Ys: batch_y,
				self.keep_prob: 0.7,
				self.norm: 1}
			feed_dict.update(task_dic['tl_output'].all_drop)
			_, cost, L2_loss = sess.run([task_dic[optimizer], task_dic['cost'], task_dic['L2_loss']], feed_dict=feed_dict)

			return cost, L2_loss

		def _plot_predict_vs_real(fig_instance, task_name, testing_y, testing_predict_y, training_y, training_predict_y):

			ax_1 = fig_instance.add_subplot(2, 1, 1)
			ax_2 = fig_instance.add_subplot(2, 1, 2)
			ax_1.cla()
			ax_2.cla()
			ax_1.plot(testing_y, label='real', marker='.')
			ax_1.plot(testing_predict_y, label='predict', marker='.')
			ax_1.set_title(task_name + ' testing data')
			ax_1.grid()
			ax_1.legend()

			ax_2.plot(training_y, label='real', marker='.')
			ax_2.plot(training_predict_y, label='predict', marker='.')
			ax_2.set_title(task_name + ' training data')
			ax_2.grid()
			ax_2.legend()
			# ax.draw()
			plt.pause(0.001)

		def _plot_loss_rate(epoch_his):
			ax_1 = loss_fig.add_subplot(3, 1, 1)
			ax_2 = loss_fig.add_subplot(3, 1, 2)
			ax_3 = loss_fig.add_subplot(3, 1, 3)
			ax_1.cla()
			ax_2.cla()
			ax_3.cla()
			ax_1.plot(epoch_his, self.multi_task_dic['min_traffic']['training_cost_history'], 'g-', label='min training losses')
			ax_1.plot(epoch_his, self.multi_task_dic['min_traffic']['testing_cost_history'], 'b-', label='min testing losses')
			ax_1.legend()
			ax_2.plot(epoch_his, self.multi_task_dic['avg_traffic']['training_cost_history'], 'g-', label='avg training losses')
			ax_2.plot(epoch_his, self.multi_task_dic['avg_traffic']['testing_cost_history'], 'b-', label='avg testing losses')
			ax_2.legend()
			ax_3.plot(epoch_his, self.multi_task_dic['max_traffic']['training_cost_history'], 'g-', label='max training losses')
			ax_3.plot(epoch_his, self.multi_task_dic['max_traffic']['testing_cost_history'], 'b-', label='max testing losses')
			ax_3.legend()
			plt.pause(0.001)
		data = self._read_data_from_Tfrecord(self.training_file)
		batch_tuple_OP = tf.train.shuffle_batch(
			data,
			batch_size=self.batch_size,
			capacity=self.shuffle_capacity,
			min_after_dequeue=self.shuffle_min_after_dequeue)
		batch_without_batch_OP = tf.train.batch(
			data,
			batch_size=self.batch_size)
		with tf.Session() as sess:
			coord = tf.train.Coordinator()
			treads = tf.train.start_queue_runners(sess=sess, coord=coord)
			tf.summary.FileWriter('logs/', sess.graph)
			if reload:
				self._reload_model(sess, model_path['reload_path'])
			else:
				sess.run(tf.global_variables_initializer())
			'''get batch sample'''
			_, batch_x_sample, batch_y_sample = sess.run(batch_without_batch_OP)
			batch_x_sample, batch_y_sample = get_multi_task_batch(batch_x_sample, batch_y_sample)
			with tf.device('/gpu:0'):
				for epoch in range(20000):
					index, batch_x, batch_y = sess.run(batch_tuple_OP)
					batch_x, batch_y = get_multi_task_batch(batch_x, batch_y)
					if training_accu_min < 1:
						cost_min, L2_min = run_task_optimizer(sess, batch_x, batch_y[0], 'min_traffic')
					else:
						cost_min, L2_min = run_task_optimizer(sess, batch_x, batch_y[0], 'min_traffic', 'prediction_optimizer')
					training_min_loss += cost_min
					if training_accu_avg < 1:
						cost_avg, L2_avg = run_task_optimizer(sess, batch_x, batch_y[1], 'avg_traffic')
					else:
						cost_avg, L2_avg = run_task_optimizer(sess, batch_x, batch_y[1], 'avg_traffic', 'prediction_optimizer')
					training_avg_loss += cost_avg

					if training_accu_max < 1:
						cost_max, L2_max = run_task_optimizer(sess, batch_x, batch_y[2], 'max_traffic')
					else:
						cost_max, L2_max = run_task_optimizer(sess, batch_x, batch_y[2], 'max_traffic', 'prediction_optimizer')
					training_max_loss += cost_max

					if epoch % display_step == 0 and epoch is not 0:
						index, testing_X, testing_Y = self._read_all_data_from_Tfreoced(self.testing_file)
						testing_X, testing_Y = get_multi_task_batch(testing_X, testing_Y)
						testing_loss_min, testing_accu_min, prediction_min = self._MTL_testing_data(sess, testing_X, testing_Y[0], 'min_traffic')
						testing_loss_avg, testing_accu_avg, prediction_avg = self._MTL_testing_data(sess, testing_X, testing_Y[1], 'avg_traffic')
						testing_loss_max, testing_accu_max, prediction_max = self._MTL_testing_data(sess, testing_X, testing_Y[2], 'max_traffic')

						training_loss_min_nodrop, training_accu_min, train_prediction_min = self._MTL_testing_data(sess, batch_x_sample, batch_y_sample[0], 'min_traffic')
						training_loss_avg_nodrop, training_accu_avg, train_prediction_avg = self._MTL_testing_data(sess, batch_x_sample, batch_y_sample[1], 'avg_traffic')
						training_loss_max_nodrop, training_accu_max, train_prediction_max = self._MTL_testing_data(sess, batch_x_sample, batch_y_sample[2], 'max_traffic')

						training_min_loss /= display_step
						training_avg_loss /= display_step
						training_max_loss /= display_step
						epoch_his.append(epoch)
						self.multi_task_dic['min_traffic']['testing_cost_history'].append(testing_loss_min)
						self.multi_task_dic['avg_traffic']['testing_cost_history'].append(testing_loss_avg)
						self.multi_task_dic['max_traffic']['testing_cost_history'].append(testing_loss_max)

						self.multi_task_dic['min_traffic']['training_cost_history'].append(training_min_loss)
						self.multi_task_dic['avg_traffic']['training_cost_history'].append(training_avg_loss)
						self.multi_task_dic['max_traffic']['training_cost_history'].append(training_max_loss)

						print('Min task: epoch:{} training_cost:{:.4f} L2_loss:{:.4f} trainin_MSE(nodrop):{:.4f} training_accu:{:.4f} testing_MSE(nodrop):{:.4f} testing_accu:{:.4f}'.format(
							epoch,
							training_min_loss,
							L2_min,
							training_loss_min_nodrop,
							training_accu_min,
							testing_loss_min,
							testing_accu_min))

						print('Avg task: epoch:{} training_cost:{:.4f} L2_loss:{:.4f} trainin_MSE(nodrop):{:.4f} training_accu:{:.4f} testing_MSE(nodrop):{:.4f} testing_accu:{:.4f}'.format(
							epoch,
							training_avg_loss,
							L2_avg,
							training_loss_avg_nodrop,
							training_accu_avg,
							testing_loss_avg,
							testing_accu_avg))

						print('Max task: epoch:{} training_cost:{:.4f} L2_loss:{:.4f} trainin_MSE(nodrop):{:.4f} training_accu:{:.4f} testing_MSE(nodrop):{:.4f} testing_accu:{:.4f}'.format(
							epoch,
							training_max_loss,
							L2_max,
							training_loss_max_nodrop,
							training_accu_max,
							testing_loss_max,
							testing_accu_max))
						print()
						_plot_loss_rate(epoch_his)
						_plot_predict_vs_real(min_fig, 'Min task', testing_Y[0][:100, 0, 0, 0, 0], prediction_min[:100, 0, 0, 0, 0], batch_y_sample[0][:100, 0, 0, 0, 0], train_prediction_min[:100, 0, 0, 0, 0])
						_plot_predict_vs_real(avg_fig, 'Avg task', testing_Y[1][:100, 0, 0, 0, 0], prediction_avg[:100, 0, 0, 0, 0], batch_y_sample[1][:100, 0, 0, 0, 0], train_prediction_avg[:100, 0, 0, 0, 0])
						_plot_predict_vs_real(max_fig, 'Max task', testing_Y[2][:100, 0, 0, 0, 0], prediction_max[:100, 0, 0, 0, 0], batch_y_sample[2][:100, 0, 0, 0, 0], train_prediction_max[:100, 0, 0, 0, 0])
						training_min_loss = 0
						training_avg_loss = 0
						training_max_loss = 0
					if epoch % 500 == 0 and epoch is not 0:
						self._save_model(sess, model_path['save_path'])
			coord.request_stop()
			coord.join(treads)
			print('training finished!')
			self._save_model(sess, model_path['save_path'])
		plt.ioff()
		plt.show()

if __name__ == '__main__':
	X_data_shape = [6, 25, 25, 1]
	Y_data_shape = [1, 5, 5, 1]
	cnn_rnn = CNN_RNN(X_data_shape, Y_data_shape)
