from abc import ABC, abstractmethod

import numpy as np

from slick_dnn import variable
from slick_dnn.autograd.tensor_modifications import Img2Col
from slick_dnn.variable import Variable


class Module(ABC):
    def __init__(self):
        self.variables_list = []

    def register_variable(self, var: Variable):
        self.variables_list.append(var)

    def register_variables(self, *var_iterable):
        self.variables_list.extend(var_iterable)

    def get_variables_list(self) -> list:
        return self.variables_list

    @abstractmethod
    def forward(self, *input_variables) -> Variable:
        raise NotImplementedError

    def __call__(self, *input_variables) -> Variable:
        return self.forward(*input_variables)


class Sequential(Module):
    def __init__(self, *sequences):
        super().__init__()

        self.sequences_list = list(sequences)
        for seq in self.sequences_list:
            try:
                var_list = seq.get_variables_list()

                self.register_variables(*var_list)
            except AttributeError:
                pass

    def forward(self, *input_variables):
        out = self.sequences_list[0](*input_variables)
        for seq in self.sequences_list[1:]:
            out = seq(out)
        return out


class Linear(Module):
    def __init__(self, num_input, num_output):
        super().__init__()

        self.num_input = num_input
        self.num_output = num_output

        self.weights = Variable(np.random.normal(0, 0.05, (self.num_input, self.num_output)))
        self.biases = variable.zeros(self.num_output, np.float32)

        self.register_variables(self.weights, self.biases)

    def forward(self, in_var):
        return (in_var @ self.weights) + self.biases


class Conv2d(Module):
    def __init__(self, input_channels, output_channels, kernel_size, stride=1, padding=0, add_bias=True):
        super().__init__()

        if isinstance(kernel_size, int):
            kernel_size = (kernel_size, kernel_size)

        if isinstance(stride, int):
            stride = (stride, stride)

        if isinstance(padding, int):
            padding = (padding, padding)

        self.input_channels = input_channels
        self.output_channels = output_channels
        self.kernel_size = kernel_size
        self.padding = padding
        self.stride = stride

        self.weights = Variable(
            np.random.normal(0, 0.05, (
                self.output_channels,
                self.input_channels,
                self.kernel_size[0],
                self.kernel_size[1]
            ))
        )

        self.add_bias = add_bias
        if self.add_bias:
            self.biases = variable.zeros(output_channels)
            self.register_variables(self.weights, self.biases)
        else:
            self.register_variables(self.weights)

        self.img2col = Img2Col(self.kernel_size, self.stride)

    # https://leonardoaraujosantos.gitbooks.io/artificial-inteligence/content/making_faster.html
    def forward(self, input_variable: Variable) -> Variable:
        """
        Performs 2D convolution on input_variable.
        Args:
            input_variable (np.array): input image allowed shapes:
                                [N, C, H, W], [C, H, W]
                                N - batches,
                                C - channels,
                                H - height,
                                W - width
        """

        img2col = self.img2col(input_variable)
        unformed_res = self.weights.reshape(self.weights.shape[0], -1) @ img2col

        img_w = input_variable.shape[-1]
        img_h = input_variable.shape[-2]
        # new image width
        new_w = (img_w - self.kernel_size[0]) // self.stride[0] + 1

        # new image height
        new_h = (img_h - self.kernel_size[1]) // self.stride[1] + 1

        batch_input = len(input_variable.shape) == 4

        if batch_input:
            output_shape = (input_variable.shape[0], self.output_channels, new_h, new_w)
        else:
            output_shape = (self.output_channels, new_h, new_w)

        if self.add_bias:
            unformed_res = (unformed_res.swap_axes(-1, -2) + self.biases).swap_axes(-1, -2)

        return unformed_res.reshape(*output_shape)
