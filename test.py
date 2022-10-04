#!/usr/bin/env python

import unittest
import numpy as np
from nearest_neighbour import Cifar10Dataset, ManhattanModel, train, evaluate
from ml_lib import SVMLossVectorized, WeightMultiplication, BiasAddition,\
    LinearLayer, MathematicalFunc, Model, StochasticGradientDecent, Layer
from linear_classification import ExperimentalModel, LinearClassifier


def gradient_check(m_func: MathematicalFunc, x: np.ndarray, d: float = 1e-4) -> list:
    m_func.forward(x)  # Forward pass just in case so all params are in place.
    gradients = []
    for idx, param in enumerate(m_func.parameters):  # gradients for all internal parameters
        grad_numerical = np.zeros_like(m_func.parameters[idx])
        with np.nditer(grad_numerical, flags=["multi_index"], op_flags=["readwrite"]) as it:
            for element in it:
                m_func.parameters[idx][it.multi_index] += d
                fxd = m_func.forward(x)
                m_func.parameters[idx][it.multi_index] -= d  # the '=' operator would destroy the reference!
                fx = m_func.forward(x)
                dw = (fxd - fx) / d
                element[...] = np.sum(dw)
        gradients.append(grad_numerical)
    return gradients


def gradient_check_model(model: Model, x: np.ndarray, d: float = 1e-4) -> list:
    model.forward(x)  # Forward pass just in case so all params are in place.
    gradients = []
    for layer in reversed(model.layers):
        for idx, param in enumerate(layer.parameters):
            grad_numerical = np.zeros_like(layer.parameters[idx])
            with np.nditer(grad_numerical, flags=["multi_index"], op_flags=["readwrite"]) as it:
                for element in it:
                    layer.parameters[idx][it.multi_index] += d
                    fxd = model.forward(x)
                    layer.parameters[idx][it.multi_index] -= d  # the '=' operator would destroy the reference!
                    fx = model.forward(x)
                    dw = (fxd - fx) / d
                    element[...] = np.sum(dw)
                gradients.append(grad_numerical)
    return gradients


class TestMyDataset(unittest.TestCase):
    def setUp(self):
        self.dataset = Cifar10Dataset()

    def test_num_classes(self):
        self.assertEqual(self.dataset.num_classes, 10)

    def test___iter__(self):
        for batch in self.dataset:
            self.assertIsInstance(batch[b"batch_label"], bytes)
            self.assertIsInstance(batch[b"labels"], list)
            self.assertIsInstance(batch[b"data"], np.ndarray)
            self.assertIsInstance(batch[b"filenames"], list)


class TestTrain(unittest.TestCase):
    def test_train(self):
        train_dataset = Cifar10Dataset()
        model = ManhattanModel()
        train(model=model, dataset=train_dataset)

        # check data
        d_samples = 0
        l_samples = 0
        for batch in train_dataset:
            d_samples += len(batch[b"data"])
            l_samples += len(batch[b"labels"])
        self.assertEqual(len(model.data), d_samples)
        self.assertEqual(len(model.labels), l_samples)


class TestManhattanModel(unittest.TestCase):
    def test___call__(self):
        model: ManhattanModel = ManhattanModel()
        dataset: Cifar10Dataset = Cifar10Dataset(batches=slice(0, 1))
        train(model, dataset)

        for batch in dataset:
            for img, lbl in zip(batch[b"data"][0:20], batch[b"labels"][0:20]):
                target = dataset.labels[lbl].decode()
                prediction = dataset.labels[model(img)].decode()

                self.assertEqual(prediction, target)


class TestEvaluate(unittest.TestCase):
    def test_evaluate(self):
        model = ManhattanModel()
        dataset = Cifar10Dataset(batches=slice(0, 1))
        train(model, dataset)
        self.assertEqual(evaluate(model, dataset, images=slice(0, 60)), 100.00)


class TestSVMLossVectorized(unittest.TestCase):
    def setUp(self):
        self.loss_func = SVMLossVectorized()

    def test_forward(self):
        scores = np.array([
            [3.2, 5.1, -1.7],  # 5.1-3.2+1 = 2.9
            [1.3, 4.9, 2.0],   # 0 = 0
            [2.2, 2.5, -3.1]   # 2.2-(-3.1)+1 + 2.5-(-3.1)+1 = 12.9
        ])
        targets = [0, 1, 2]
        loss = self.loss_func.forward(x=scores, y=targets)
        self.assertEqual(5.26667, np.round(loss, 5).tolist())

    def test_backward(self):
        scores = np.array([
            [3.2, 5.1, -1.7],
            [1.3, 4.9, 2.0],
            [2.2, 2.5, -3.1]
        ])
        targets = [0, 1, 2]
        losses = self.loss_func.forward(x=scores, y=targets)
        grads = self.loss_func.backward()

        self.assertEqual([[-1.0, 1.0, 0.0], [0.0, 0.0, 0.0], [1.0, 1.0, -2.0]], np.round(grads, 1).tolist())
        self.assertEqual(scores.shape, grads.shape)

    def test_gradient_check(self):
        scores = np.random.randint(-10, 10, size=(15, 10)).astype("float64")
        scores_backup = scores.copy()
        targets = [0 for _ in range(len(scores))]
        d = 1e-6

        # calculate numerical gradient
        grad_numerical = np.zeros_like(scores)
        with np.nditer(grad_numerical, flags=['multi_index'], op_flags=['readwrite']) as it:
            for element in it:
                scores[it.multi_index] += d
                fxd = self.loss_func.forward(scores, targets)
                scores = scores_backup.copy()
                fx = self.loss_func.forward(scores, targets)

                ds = (fxd - fx) / d
                element[...] = ds  # No sum due to single float value being the output.

        # calculate analytical gradient
        loss = self.loss_func.forward(scores, targets)
        grad_analytical = self.loss_func.backward()

        # compare gradients
        self.assertEqual(np.round(grad_numerical, 6).tolist(), np.round(grad_analytical, 6).tolist())


class TestWeightMultiplication(unittest.TestCase):
    def test_forward(self):
        x = np.array([[8, 6],
                      [1, 5],
                      [2, 6]])
        w = np.array([[5, 9],
                      [7, 2]])
        f = WeightMultiplication(w)
        s = f.forward(x)
        self.assertEqual([[82, 84],
                          [40, 19],
                          [52, 30]], s.tolist())

    def test_backward(self):
        w = np.array([[.2],
                      [.4]])
        x = np.array([[.1, .5],
                      [-.3, .8]])
        f = WeightMultiplication(w)
        s = f.forward(x)
        dx, dw = f.backward(np.array([[.44], [.52]]))
        dw = dw[0]

        self.assertEqual([[-0.11199999999999999],
                          [0.636]], dw.tolist())
        self.assertEqual([[0.08800000000000001, 0.17600000000000002],
                          [0.10400000000000001, 0.20800000000000002]], dx.tolist())
        self.assertEqual(w.shape, dw.shape)
        self.assertEqual(x.shape, dx.shape)

        x = np.array([[6, 5, 2, 8],                     # [[x11, x12, x13, x14],
                      [4, 7, 8, 2]]).astype("float64")  #  [x21, x22, x23, x24]]
        w = np.array([[7, 8, 2],                        # [[w11, w12, w13],
                      [1, 0, 5],                        #  [w21, w22, w23],
                      [1, 3, 3],                        #  [w31, w32, w33],
                      [9, 8, 1]]).astype("float64")     #  [w41, w42, w43]]
        f = WeightMultiplication(w)
        s = f.forward(x)  # [[(x11*w11+x12*w21+x13*w31+x14*w41), (x11*w12+x12*w22+x13*w32+x14*w42), (x11*w13+x12*w23+x13*w33+x14*w43)],
        #                    [(x21*w11+x22*w21+x23*w31+x24*w41), (x21*w12+x22*w22+x13*w32+x14*w42), (x21*w13+x22*w23+x23*w33+x24*w43)]]

        ds = np.ones_like(s)
        dx_anl, dw_anl = f.backward(prev_grad=ds)
        dw_anl = dw_anl[0]
        dw_num = gradient_check(f, x)[0]

        self.assertEqual(x.shape, dx_anl.shape)
        self.assertEqual(w.shape, dw_anl.shape)
        self.assertEqual(w.shape, dw_num.shape)
        self.assertEqual(np.round(dw_num, 3).tolist(), np.round(dw_anl, 3).tolist())


class TestBiasAddition(unittest.TestCase):
    """This thing is vectorized!!"""
    def test_forward(self):
        x = np.array([[2, 3],
                      [4, 9]])
        b = np.array([[1, 7],
                      [2, 4]])
        addition = BiasAddition(b)
        _sum = addition.forward(x)
        self.assertEqual([[3, 10],
                          [6, 13]], _sum.tolist())

    def test_backward(self):
        x = np.random.randint(-10, 10, size=(10, 3)).astype("float64")
        b = np.random.randint(-10, 10, size=(3, )).astype("float64")
        f = BiasAddition(b)
        s = f.forward(x)

        ds = np.ones_like(s)
        dx_anl, db_anl = f.backward(prev_grad=ds)
        db_anl = db_anl[0]
        db_num = gradient_check(f, x)[0]

        self.assertEqual(x.shape, dx_anl.shape)
        self.assertEqual(b.shape, db_anl.shape)
        self.assertEqual(b.shape, db_num.shape)
        self.assertEqual(np.round(db_num, 3).tolist(), np.round(db_anl, 3).tolist())


# class TestL2Regularization(unittest.TestCase):
#     def setUp(self):
#         self.reg_func = L2Regularization()
#         self.model = LinearClassifier(num_pixels=25, num_classes=3)
#         self.model.layers[0].parameters["weights"] *= 1e2
#
#     def test_forward(self):
#         penalty = self.reg_func.forward(self.model.layers[0].parameters["weights"])
#         self.assertIsInstance(penalty, float)
#
#     def test_backward(self):
#         self.test_forward()
#         grad = self.reg_func.backward()
#         self.assertEqual(self.model.layers[0].parameters["weights"].shape, grad.shape)
#
#     def test_grad_check(self):
#         d = 1e-5
#
#         # numerically calculate gradient
#         numerical_grad = np.zeros_like(self.model.layers[0].parameters["weights"])
#         with np.nditer(numerical_grad, flags=['multi_index'], op_flags=['readwrite']) as it:
#             weights_backup = self.model.layers[0].parameters["weights"].copy()
#             for element in it:
#                 self.model.layers[0].parameters["weights"][it.multi_index] += d
#                 fxd = self.reg_func.forward(self.model.layers[0].parameters["weights"])
#                 self.model.layers[0].parameters["weights"] = weights_backup.copy()
#                 fx = self.reg_func.forward(self.model.layers[0].parameters["weights"])
#
#                 db = (fxd - fx) / d
#                 element[...] = db
#
#         # analytically calculate gradient
#         analytical_grad = self.reg_func.backward()
#
#         self.assertEqual(np.round(numerical_grad).tolist(), np.round(analytical_grad).tolist())


class TestLayer(unittest.TestCase):
    def setUp(self):
        self.layers = [LinearLayer()]
                       # SigmoidLayer()]

    def test_backward(self):
        data = np.random.randint(0, 255, (2, 3072)).astype("float64")
        data /= 255  # Normalize data to fit between 0 and 1.

        for layer in self.layers:
            numerical_grads: list = gradient_check(layer, data, d=1e-6)
            analytical_grads = layer.backward(np.ones_like(layer.forward(data)))[1]

            # compare gradients
            for num_grad, anl_grad, param in zip(numerical_grads, analytical_grads, layer.parameters):
                self.assertEqual(param.shape, num_grad.shape)
                self.assertEqual(param.shape, anl_grad.shape)
                self.assertEqual(np.round(num_grad, 2).tolist(), np.round(anl_grad, 2).tolist())


class TestModel(unittest.TestCase):
    def setUp(self):
        self.criterion = SVMLossVectorized()
        self.models = [
            LinearClassifier(),
            ExperimentalModel()
        ]

    def test_forward(self):
        data = np.random.randint(0, 255, size=(9, 3072))
        for model in self.models:
            scores = model.forward(data)
            self.assertIsInstance(scores, np.ndarray)
            self.assertEqual((9, 10), scores.shape)

    def test_backward(self):
        data = np.random.randint(0, 255, size=(9, 3072))
        for model in self.models:
            scores = model.forward(data)
            loss_grad = np.ones_like(scores)

            numerical_grads = gradient_check_model(model, data, d=1e-4)
            analytical_grads = []
            grad = loss_grad
            for layer in reversed(model.layers):
                grad, parameter_grads = layer.backward(grad)
                analytical_grads += parameter_grads

            # compare gradients
            for num_grad, anl_grad in zip(numerical_grads, analytical_grads):
                self.assertEqual(np.round(num_grad, 2).tolist(), np.round(anl_grad, 2).tolist())


class DummyLayer(Layer):
    def __init__(self, num_pixels: int = 3072, num_classes: int = 10):
        super().__init__()
        self.parameters = [np.ones(shape=(num_pixels, num_classes)),
                           np.ones(shape=(num_classes,))]
        self.operations = [WeightMultiplication(weight=self.parameters[0]), BiasAddition(bias=self.parameters[1])]

    def forward(self, x) -> np.ndarray:
        self.x = x
        for operation in self.operations:
            x = operation.forward(x)
        return x

    def backward(self, grad: np.ndarray) -> tuple[np.ndarray, list]:
        return np.ones_like(self.x), [np.ones_like(self.parameters[0]), np.ones_like(self.parameters[1])]


class TestDummyLayer(unittest.TestCase):
    def setUp(self):
        self.layer1 = DummyLayer(num_pixels=4, num_classes=3)

    def test_forward(self):
        x = np.ones(shape=(5, 4))
        s = self.layer1.forward(x)
        self.assertEqual((5, 3), s.shape)
        self.assertEqual(np.full(shape=(5, 3), fill_value=5.).tolist(), s.tolist())

    def test_backward(self):
        x = np.ones(shape=(5, 4))
        s = self.layer1.forward(x)

        ds = np.ones_like(s)
        dx = self.layer1.backward(ds)[0]
        dw, db = self.layer1.backward(ds)[1]

        self.assertEqual(x.shape, dx.shape)
        self.assertEqual(self.layer1.parameters[0].shape, dw.shape)
        self.assertEqual(self.layer1.parameters[1].shape, db.shape)

        self.assertEqual(np.ones_like(x).tolist(), dx.tolist())
        self.assertEqual(np.ones_like(self.layer1.parameters[0]).tolist(), dw.tolist())
        self.assertEqual(np.ones_like(self.layer1.parameters[1]).tolist(), db.tolist())


class DummyModel(Model):
    def __init__(self):
        super().__init__()
        self.layers = [DummyLayer(num_pixels=3072, num_classes=10),
                       DummyLayer(num_pixels=10, num_classes=10)]


class TestDummyModel(unittest.TestCase):
    def setUp(self):
        self.model = DummyModel()

    def test_forward(self):
        x = np.random.randint(0, 255, size=(9, 3072))
        s = self.model.forward(x)
        self.assertEqual((9, 10), s.shape)
        # Values are not (!) ones!

    def test_backward(self):
        x = np.random.randint(0, 255, size=(9, 3072))
        s = self.model.forward(x)

        ds = np.ones_like(s)
        ds, dwb = self.model.layers[1].backward(ds)
        dw1, db1 = dwb[0], dwb[1]
        _, dwb = self.model.layers[0].backward(ds)
        dw0, db0 = dwb[0], dwb[1]

        self.assertEqual(np.ones_like(self.model.layers[1].parameters[0]).tolist(), dw1.tolist())
        self.assertEqual(np.ones_like(self.model.layers[1].parameters[1]).tolist(), db1.tolist())
        self.assertEqual(np.ones_like(self.model.layers[0].parameters[0]).tolist(), dw0.tolist())
        self.assertEqual(np.ones_like(self.model.layers[0].parameters[1]).tolist(), db0.tolist())


class TestOptimizer(unittest.TestCase):
    def setUp(self):
        self.model = DummyModel()
        self.lr = 0.001
        self.optim = StochasticGradientDecent(model_layers=self.model.layers, lr=self.lr)

    def test_step(self):
        data = np.random.randint(0, 255, size=(9, 3072))
        scores = self.model.forward(data)
        d_scores = np.ones_like(scores)
        self.optim.step(grad=d_scores)

        self.assertEqual(np.full(shape=(3072, 10), fill_value=1-self.lr).tolist(),
                         self.model.layers[0].parameters[0].tolist())
        self.assertEqual(np.full(shape=(10, ), fill_value=1-self.lr).tolist(),
                         self.model.layers[0].parameters[1].tolist())
        self.assertEqual(np.full(shape=(10, 10), fill_value=1-self.lr).tolist(),
                         self.model.layers[1].parameters[0].tolist())
        self.assertEqual(np.full(shape=(10, ), fill_value=1-self.lr).tolist(),
                         self.model.layers[1].parameters[1].tolist())


if __name__ == '__main__':
    unittest.main()