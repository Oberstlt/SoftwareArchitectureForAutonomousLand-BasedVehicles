#!/usr/bin/env python
import time

import matplotlib.pyplot as plt
from tqdm import tqdm
from time import sleep

import torch
import torch.nn as nn

from benchmark.nearest_neighbour import Cifar10Dataset
from init import Config


def evaluate(model,
             dataset: Cifar10Dataset,
             normalize: bool = False,
             images: slice = slice(None, None, None)) -> float:
    total = correct = 0
    for batch in dataset:
        for img, lbl in zip(batch[b"data"][images], batch[b"labels"][images]):
            img = img.astype("float64") / 255 if normalize else img.astype("float64")
            img = torch.from_numpy(img)
            target = dataset.labels[lbl].decode()
            scores = model(img).argmax().item()
            prediction = dataset.labels[scores].decode()

            total += 1
            if prediction == target:
                correct += 1

    print(f"{dataset.name+': ' if dataset.name else ''}{correct} of {total}"
          f" examples were correct resulting in an accuracy of {correct/total*100:.2f}%.")
    return correct/total*100


class ParentModel(nn.Module):
    def __init__(self, name: str = None):
        super().__init__()
        self.name = name


class TorchLinearClassifier(ParentModel):
    def __init__(self, num_pixels: int = 3072, num_classes: int = 10, name: str = None):
        super().__init__(name=name)
        self.linear1 = nn.Linear(in_features=num_pixels, out_features=num_classes)

    def forward(self, x):
        x = self.linear1(x)
        return x


class TorchExperimentalModel(ParentModel):
    def __init__(self, num_pixels: int = 3072, num_classes: int = 10, name: str = None):
        super().__init__(name=name)
        self.linear1 = nn.Linear(in_features=num_pixels, out_features=100)
        self.linear2 = nn.Linear(in_features=100, out_features=num_classes)

    def forward(self, x):
        x = self.linear1(x)
        x = self.linear2(x)
        return x


class TorchSigmoidModel(ParentModel):
    def __init__(self, num_pixels: int = 3072, num_classes: int = 10, name: str = None):
        super().__init__(name=name)
        self.linear1 = nn.Linear(in_features=num_pixels, out_features=100)
        self.sigmoid = nn.Sigmoid()
        self.linear2 = nn.Linear(in_features=100, out_features=num_classes)

    def forward(self, x):
        x = self.linear1(x)
        x = self.sigmoid(x)
        x = self.linear2(x)
        return x


def train(model: ParentModel,
          dataset: Cifar10Dataset,
          criterion,
          optimizer,
          epochs: int,
          completed_epochs: int = 0,
          normalize: bool = False,
          show_graphs: bool = True):
    avg_losses = []
    for _ in tqdm(range(completed_epochs, completed_epochs + epochs), desc=f"Training the model '{model.name}'"):
        batch_losses = []
        for batch in dataset:
            data = batch[b"data"].astype("float64") / 255 if normalize else batch[b"data"].astype("float64")
            targets = batch[b"labels"]
            data, targets = torch.from_numpy(data), torch.tensor(targets)

            scores = model.forward(data)
            loss = criterion(scores, targets)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            batch_losses.append(loss.item())
        avg_losses.append(sum(batch_losses)/len(batch_losses))

    if show_graphs:
        plt.plot(avg_losses)
        plt.title(f"Stats for Model '{model.name}'")
        plt.ylabel("Average Losses")
        plt.xlabel("Epochs")
        plt.show()


def main():
    config = Config("../config.json")

    datasets: list = [
        Cifar10Dataset(batches=slice(0, 1), root=config["cifar"], name="train"),
        Cifar10Dataset(batches=slice(4, 5), root=config["cifar"], name="eval"),
        Cifar10Dataset(batches=slice(5, 6), root=config["cifar"], name="test"),
        Cifar10Dataset(root=config["cifar"], name="total")
    ]

    models: list = [
        TorchLinearClassifier(name="linear").double(),
        TorchExperimentalModel(name="experimental").double(),
        TorchSigmoidModel(name="sigmoid").double()
    ]

    for model in models:
        criterion = nn.MultiMarginLoss()
        optimizer = torch.optim.SGD(model.parameters(), lr=1e-3)

        train(model, datasets[0], criterion, optimizer, epochs=int(1e2), show_graphs=False)
        for dataset in datasets:
            evaluate(model, dataset)
        sleep(.5)


if __name__ == "__main__":
    main()
