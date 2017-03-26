import pickle
import numpy as np
import os
import tensorflow as tf
import functools as fn
'''
todo:
	normalization
	batch_normalize

'''

class CNN_autoencoder:
	def __init__(self, input_x, **network_para):
		print('input_x shape:{}'.format(input_x.shape))
		X_data = input_x[0:-1]
		Y_data = input_x[1:]
		self.training_X = X_data[0:int(9*X_data.shape[0]/10)]
		self.training_Y = Y_data[0:int(9*X_data.shape[0]/10)]
		self.testing_X =  X_data[int(9*X_data.shape[0]/10):]
		self.testing_Y =  Y_data[int(9*X_data.shape[0]/10):]
	
		self.learning_rate = 0.003
		self.training_iters = 5000
		self.batch_size = 30
		self.display_step = 10
		self.dropout = 0.6
		# self.n_input = 100*100

		# network parameter
		self.conv1 = network_para.get('conv1')
		self.conv2 = network_para.get('conv2')
		self.pooling_times = 0
		# self.deconv1 = network_para.get('deconv1')
		# self.deconv2 = network_para.get('deconv2')
		self.training_data_number = self.training_X.shape[0]
		self.input_temporal = self.training_X.shape[1]
		self.input_vertical = self.training_X.shape[2]
		self.input_horizontal = self.training_X.shape[3]
		self.input_channel = self.training_X.shape[4]

		# placeholder
		with tf.device('/cpu:0'):
			self.Xs = tf.placeholder(tf.float32, shape=[
									 None, self.input_temporal, self.input_vertical, self.input_horizontal, self.input_channel])
			self.Ys = tf.placeholder(tf.float32, shape=[
									 None, self.input_temporal, self.input_vertical, self.input_horizontal, self.input_channel])
			self.keep_prob = tf.placeholder(tf.float32)
			self.norm = tf.placeholder(tf.bool, name='norm')
			
			# variable control filter size
			self.weights = {
				'conv1': self.weight_variable([3, 3, 3, self.input_channel, self.conv1], 'conv1_w'),
				'conv2': self.weight_variable([3, 3, 3, self.conv1, self.conv2], 'conv2_w'),
				'deconv1': self.weight_variable([3, 3, 3, self.conv1, self.conv2], 'deconv1_w'),
				'deconv2': self.weight_variable([3, 3, 3, self.input_channel, self.conv1], 'deconv1_w')
			}
			self.bias = {
				'conv1': self.bias_variable([self.conv1], 'conv1_b'),
				'conv2': self.bias_variable([self.conv2], 'conv2_b'),
				'deconv1': self.bias_variable([self.conv1], 'deconv1_b'),
				'deconv2': self.bias_variable([self.input_channel], 'deconv2_b')
			}

		# operation
	
		self.encoder_OP, self.endecoder_OP = self.net_layer(
			self.Xs, self.weights, self.bias, self.keep_prob, self.norm)
		self.cost_OP = self.MSE_loss()
		
		self.optimizer_OP = tf.train.AdamOptimizer(
			learning_rate=self.learning_rate).minimize(self.cost_OP)

		self.init_OP = tf.global_variables_initializer()
		self.saver = tf.train.Saver()

	def MSE_loss(self):
		with tf.variable_scope('loss'):
			loss = tf.reduce_mean(tf.pow(self.endecoder_OP - self.Ys, 2))
			loss = tf.div(loss, 2)
		return loss

	def net_layer(self, x, weights, bias, dropout, norm=0):

		k_size = {'temporal': 2, 'vertical': 2, 'horizontal': 2}
		strides_size = {'temporal': 2, 'vertical': 2, 'horizontal': 2}
		# layer 1
		conv1 = self.conv3d(x, weights['conv1'], bias['conv1'])
		conv1 = tf.nn.relu(conv1)
		# conv1 = self.maxpool3d(conv1,**k_size,**strides_size)
		conv1 = tf.nn.dropout(conv1, dropout)

		# layer 2
		conv2 = self.conv3d(conv1, weights['conv2'], bias['conv2'])
		conv2 = tf.nn.relu(conv2)
		# conv2 = self.maxpool3d(conv2,**k_size,**strides_size)
		conv2 = tf.nn.dropout(conv2, dropout)

		encode_output = conv2
		print('encode layer shape:%s' % encode_output.get_shape())
		# layer 3
		output_shape_of_dconv1 = tf.pack([tf.shape(x)[0],
										  self.input_temporal,
										  self.input_vertical,
										  self.input_horizontal,
										  self.conv1])
		deconv1 = self.deconv3d(conv2, weights['deconv1'], bias[
								'deconv1'], output_shape_of_dconv1)
		deconv1 = tf.nn.relu(deconv1)
		# output_shape_of_dconv1_unpool = tf.pack([tf.shape(x)[0],
		#	self.input_temporal/(2**(self.pooling_times-1)),
		#	self.input_vertical/(2**(self.pooling_times-1)),
		#	self.input_horizontal/(2**(self.pooling_times-1)),
		#	self.conv2])
		# deconv1 = self.maxpool3d(deconv1,output_shape_of_dconv1_unpool)

		# layer 4
		output_shape_of_dconv2 = tf.pack([tf.shape(x)[0],
										  self.input_temporal,
										  self.input_vertical,
										  self.input_horizontal,
										  self.input_channel])
		deconv2 = self.deconv3d(deconv1, weights['deconv2'], bias[
								'deconv2'], output_shape_of_dconv2)
		deconv2 = tf.nn.relu(deconv2)

		endecoder_output = deconv2
		print('endecoder_output output shape :%s' %
			  endecoder_output.get_shape())

		return encode_output, endecoder_output

	def weight_variable(self, shape, name):
		initial = tf.truncated_normal(shape, stddev=0.1)
		return tf.Variable(initial, dtype=tf.float32, name=name)

	def bias_variable(self, shape, name):
		initial = tf.random_normal(shape)
		return tf.Variable(initial, dtype=tf.float32, name=name)

	def conv3d(self, x, W, b, strides=1):
		x = tf.nn.conv3d(
			x, W, strides=[1, strides, strides, strides, 1], padding='SAME')
		x = tf.nn.bias_add(x, b)
		return x

	def deconv3d(self, x, W, b, output_shape, strides=1):
		'''
				filter shape:[depth, height, width, output_channels, in_channels]
		'''
		print('input shape:{} filter shape:{} output_shape:{}'.format(
			x.get_shape(), W.get_shape(), output_shape.get_shape()))
		x = tf.nn.conv3d_transpose(x, W, output_shape, strides=[
								   1, strides, strides, strides, 1], padding='SAME')
		x = tf.nn.bias_add(x, b)
		return x

	def maxpool3d(self, x, k_size, strides_size):
		x = tf.nn.max_pool3d(x, k=[1, k['temporal'], k['vertical'], k['horizontal'], 1], strides=[
							 1, strides_size['temporal'], strides_size['vertical'], strides_size['horizontal'], 1], padding='SAME')
		pooling_times += 1
		return x

	def maxunpool3d(self, x, shape):
		pooling_times -= 1
		return x
	def _save_model(self,sess):
		print('saving model.....')
		if not os.path.isdir('./output_model'):
			os.makedirs('./output_model')
		try:
				save_path = self.saver.save(sess, './output_model/CNN_autoencoder.ckpt')
		except:
				save_path = self.saver.save(sess, './output_model/temp.ckpt')
		finally:
			print('save_path{}'.format(save_path))
	def testing_data(self,sess,input_x,input_y):
		batch_num = int(input_x.shape[0]/self.batch_size)
		   
		if self.training_data_number % self.batch_size is not 0:
			batch_len = batch_num + 1
		else:
			batch_len = batch_num

		with tf.device('/cpu:0'):
			loss =0.
			for batch_index in range(batch_len):
				loss += sess.run(self.cost_OP,feed_dict={
						self.Xs:input_x[batch_index*self.batch_size:(batch_index+1)*self.batch_size],
						self.Ys:input_y[batch_index*self.batch_size:(batch_index+1)*self.batch_size],
						self.keep_prob:1,
						self.norm:0
				})
			return loss/batch_num
	def training_data(self,restore=False):
		def shuffle_data(input_X,input_Y):
			#print('input_X:',input_X.shape,'input_Y:',input_Y.shape)
			z = list(zip(input_X,input_Y))
			np.random.shuffle(z)
			output_x,output_y = zip(*z)
			output_x=np.array(output_x)
			output_y=np.array(output_y) 
			#print('output_x:',output_x.shape,'output_y:',output_y.shape)
			return output_x,output_y
		with tf.Session() as sess:
			sess.run(self.init_OP)
			batch_num = int(self.training_data_number/self.batch_size)
		   
			if self.training_data_number % self.batch_size is not 0:
				batch_len = batch_num + 1
			else:
				batch_len = batch_num

			epoch = 1
			while epoch < self.training_iters:
				#self.training_X,self.training_Y = shuffle_data(self.training_X,self.training_Y)
				for batch_index in range(batch_len):
					loss = 0.
					with tf.device('/gpu:0'):
						_ = sess.run([self.optimizer_OP], feed_dict={
										   self.Xs: self.training_X[batch_index * self.batch_size:batch_index * self.batch_size + self.batch_size],
										   self.Ys: self.training_Y[batch_index * self.batch_size:batch_index * self.batch_size + self.batch_size], 
										   self.keep_prob: self.dropout, 
										   self.norm: 1})
					with tf.device('/cpu:0'):
						loss = sess.run(self.cost_OP, feed_dict={
										   self.Xs: self.training_X[batch_index * self.batch_size:batch_index * self.batch_size + self.batch_size],
										   self.Ys: self.training_Y[batch_index * self.batch_size:batch_index * self.batch_size + self.batch_size], 
										   self.keep_prob: self.dropout, 
										   self.norm: 1})
					print('Epoch:%d batch_index:%d cost:%g'%(epoch, batch_index,loss))
				if epoch % display_steppython== 0 and epoch != 0:
					testing_loss = self.testing_data(sess,self.testing_X,self.testing_Y)
					print('testing_loss:{}'.format(testing_loss))
					self._save_model(sess)
				epoch += 1
			print('training finished!')
			_save_model(sess)
def list_all_input_file(input_dir):
	onlyfile = [f for f in os.listdir(input_dir) if (os.path.isfile(
		os.path.join(input_dir, f)) and os.path.splitext(f)[1] == ".npy")]
	return onlyfile


def load_data_format(filelist):
	def load_array(input_file):
		print('loading file from {}...'.format(input_file))
		X = np.load(input_file)
		return X

	def split_array(data_array):
		#print('data_array shape :', data_array.shape)
		split_block_size = 6  # one hour
		data_array_depth = data_array.shape[0]
		split_block_num = int(data_array_depth / split_block_size)

		# new_data_array_size = [split_block_num,data_array.shape[1:]]
		# print('new_data_array_size:',new_data_array_size)

		split_data_list = np.split(data_array, split_block_num)
		new_data_array = np.stack(split_data_list, axis=0)
		#print('new_data_array shape:', new_data_array.shape)

		return new_data_array

	def array_concatenate(x, y):
		return np.concatenate((x, y), axis=0)

	array_list = []
	for file_name in filelist:
		data_array = load_array(input_dir + file_name)
		array_list.append(split_array(data_array))

	X = fn.reduce(array_concatenate, array_list)
	print('data format shape:', X.shape)
	return X

if __name__ == '__main__':
	input_dir_list = [
		"/home/mldp/big_data/openbigdata/milano/SMS/11/data_preproccessing_10/",
		"/home/mldp/big_data/openbigdata/milano/SMS/12/data_preproccessing_10/"
		]
	network_parameter = {'conv1': 16, 'conv2': 32}
	X_array = None
	for input_dir in input_dir_list:
		filelist = list_all_input_file(input_dir)
		filelist.sort()
		temp = load_data_format(filelist)
		try:
			X_array = np.concatenate((X_array,temp),axis=0)
		except:
			X_array = temp

	train_CNN = CNN_autoencoder(X_array, **network_parameter)
	del X_array
	train_CNN.training_data(restore=True)
