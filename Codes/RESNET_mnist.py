# -*- coding: utf-8 -*-
"""ResNet_MNIST.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1pjmWeOEeM0mZHTqDGO9XZs3DStPqvjBf
"""

from google.colab import drive
drive.mount('/content/drive')

# Commented out IPython magic to ensure Python compatibility.
import torch
import torch.nn as nn
from torchvision import transforms, datasets
import torchvision
import json
# %matplotlib inline
import matplotlib.pyplot as plt
import os
import torch.optim as optim
import time
import numpy as np
from torch.optim import lr_scheduler
from sklearn.metrics import confusion_matrix
import itertools
import random

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

classes = ('0','1','2','3','4','5','6','7','8','9')
kwargs = {'num_workers': 1, 'pin_memory': True} if device=='cuda' else {}

transforms_list =   transform=torchvision.transforms.Compose([                
                                                              torchvision.transforms.ToTensor(), 
                                                              transforms.Lambda(lambda x: x.repeat(3, 1, 1)),                    
                                                              transforms.Lambda(lambda x: nn.UpsamplingNearest2d(scale_factor=8)(x.view(1,3, 28, 28))[0]),
                                                              torchvision.transforms.Normalize( (0.1307,), (0.3081,)),  
                                                        ])

# train_dataset = torchvision.datasets.MNIST(root='../data',train=True,
#                                         download=True, transform=transforms_list)
# validate_dataset = torchvision.datasets.MNIST(root='../data',train=False,
#                                        download=True,transform=transforms_list)
batch_size = 256

train_dataset =   torchvision.datasets.MNIST('/content/drive/MyDrive/bhanu/files/', train=True, download=True, transform=transforms_list)
test_dataset = torchvision.datasets.MNIST('/content/drive/MyDrive/bhanu/files/', train=False, download=True, transform=transform)


train_data , validate_dataset = torch.utils.data.random_split(train_dataset, [52000, 8000],generator=torch.Generator().manual_seed(42))
train_loader = torch.utils.data.DataLoader(train_data,  batch_size=batch_size, **kwargs)
validate_loader = torch.utils.data.DataLoader(validate_dataset,  batch_size=batch_size, **kwargs)
test_loader = torch.utils.data.DataLoader(test_dataset,  batch_size=batch_size, **kwargs)

class BasicBlock(nn.Module):
    expansion = 1
    def __init__(self, in_channel, out_channel, stride=1, downsample=None):
        super(BasicBlock, self).__init__()
        self.conv1 = nn.Conv2d(in_channels=in_channel, out_channels=out_channel,
                               kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_channel)
        self.relu = nn.ReLU()

        self.conv2 = nn.Conv2d(in_channels=out_channel, out_channels=out_channel,
                               kernel_size=3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_channel)
        self.downsample = downsample


    def forward(self, x):
        identity = x
        if self.downsample is not None:
            identity = self.downsample(x)

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)


        out = self.conv2(out)
        out = self.bn2(out)

        out += identity
        out = self.relu(out)

        return out

class Bottleneck(nn.Module):
    expansion = 4

    def __init__(self, in_channel, out_channel, stride=1, downsample=None):
        super(Bottleneck, self).__init__()
        self.conv1 = nn.Conv2d(in_channels=in_channel, out_channels=out_channel,
                               kernel_size=1, stride=1, bias=False) 
        self.bn1 = nn.BatchNorm2d(out_channel)

        self.conv2 = nn.Conv2d(in_channels=out_channel, out_channels=out_channel,
                               kernel_size=3, stride=stride, bias=False, padding=1)
        self.bn2 = nn.BatchNorm2d(out_channel)

        self.conv3 = nn.Conv2d(in_channels=out_channel, out_channels=out_channel*self.expansion,
                               kernel_size=1, stride=1, bias=False)  
        self.bn3 = nn.BatchNorm2d(out_channel*self.expansion)
        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample


    def forward(self, x):
        identity = x
        if self.downsample is not None:
            identity = self.downsample(x)

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)

        out = self.conv3(out)
        out = self.bn3(out)

        out += identity
        out = self.relu(out)

        return out

class ResNet(nn.Module):

    def __init__(self, block, blocks_num, num_classes=10, include_top=True):
        super(ResNet, self).__init__()
        self.include_top = include_top
        self.in_channel = 64

        self.conv1 = nn.Conv2d(3, self.in_channel, kernel_size=7, stride=2,
                               padding=3, bias=False)
        self.bn1 = nn.BatchNorm2d(self.in_channel)
        self.relu = nn.ReLU(inplace=True)
        
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.layer1 = self._make_layer(block, 64, blocks_num[0])
        self.layer2 = self._make_layer(block, 128, blocks_num[1], stride=2)
        self.layer3 = self._make_layer(block, 256, blocks_num[2], stride=2)
        self.layer4 = self._make_layer(block, 512, blocks_num[3], stride=2)
        if self.include_top:
            self.avgpool = nn.AdaptiveAvgPool2d((1, 1))  
            self.fc = nn.Linear(512 * block.expansion, num_classes)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')


    def _make_layer(self, block, channel, block_num, stride=1):
        downsample = None
        if stride != 1 or self.in_channel != channel * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(self.in_channel, channel * block.expansion, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(channel * block.expansion))

        layers = []
        layers.append(block(self.in_channel, channel, downsample=downsample, stride=stride))
        self.in_channel = channel * block.expansion

        for _ in range(1, block_num):
            layers.append(block(self.in_channel, channel))

        return nn.Sequential(*layers)

  
    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)

        if self.include_top:
            x = self.avgpool(x)
            x = torch.flatten(x, 1)
            x = self.fc(x)

        return x

def config1(num_classes=10, include_top=True):
    return ResNet(BasicBlock, [3, 4, 6, 3], num_classes=num_classes, include_top=include_top)

# Trained for number of epochs:
epochs = 10


train_num = len(train_data)
val_num = len(validate_dataset)

train_acc = []
val_acc = []
train_loss = []
val_loss = []

"""**RESNET 34**"""

# Confusion matrix

def plot_confusion_matrix(cm, classes, normalize=False, title='Confusion matrix', cmap=plt.cm.Blues):
    plt.figure(figsize=(10, 10))
    if normalize:
        cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
        print("Normalized confusion matrix")
    else:
        print('Confusion matrix, without normalization')

    print(cm)
    plt.imshow(cm, interpolation='nearest', cmap=cmap)
    plt.title(title)
    plt.colorbar()
    tick_marks = np.arange(len(classes))
    plt.xticks(tick_marks, classes, rotation=45)
    plt.yticks(tick_marks, classes)
    
    fmt = '.2f' if normalize else 'd'
    thresh = cm.max() / 2.
    for i, j in itertools.product(range(cm.shape[0]), range(cm.shape[1])):
        plt.text(j, i, format(cm[i, j], fmt), horizontalalignment="center", color="white" if cm[i, j] > thresh else "black")

    plt.tight_layout()
    plt.ylabel('True label')
    plt.xlabel('Predicted label')
    plt.savefig("confusion_matrix")
    plt.title("ResNet")
    plt.clf()

@torch.no_grad()
def get_all_preds(model, loader):

    all_preds = torch.tensor([]).to(device)
    model.to(device)
    for batch in loader:
        images, labels = batch
        preds = model(images.to(device))
        all_preds = torch.cat((all_preds, preds),dim=0)
    return all_preds

def plot_misclf_imgs(candidates,gts_np,preds_np,classes):
    size_figure_grid = 5  
    fig, ax = plt.subplots(size_figure_grid, size_figure_grid, figsize=(20, 20))

    for i, j in itertools.product(range(size_figure_grid), range(size_figure_grid)):
        ax[i, j].get_xaxis().set_visible(False)
        ax[i, j].get_yaxis().set_visible(False)

    for k in range(5 * 5):  
        i = k // 5
        j = k % 5
        idx = candidates[k]
        img = validate_dataset[idx][0].numpy()
        img = img[0]
        ax[i, j].imshow((img), cmap='gray') 
        ax[i, j].set_title("Label:"+str(classes[gts_np[idx]]), loc='left')
        ax[i, j].set_title("Predict:"+str(classes[preds_np[idx]]), loc='right')
  
    plt.savefig("/content/drive/MyDrive/bhanu/resnet_output")
    plt.clf()

def plot_acc_curves(array1, array2):
    plt.figure(figsize=(10, 10))
    x = np.linspace(1, epochs, epochs, endpoint=True)
    plt.plot(x, array1, color='r', label='Train_accuracy')
    plt.plot(x, array2, color='b', label='Val_accuracy')
    plt.legend()
    plt.title('accuracy of train and val sets in different epoch')

    plt.xlabel('epoch')
    plt.ylabel('accuracy: ')
    plt.savefig("acc_curves")
    plt.show()
    plt.clf()

def plot_loss_curves(array1, array2):
    plt.figure(figsize=(10, 10))
    x = np.linspace(1, epochs, epochs, endpoint=True)
    plt.plot(x, array1, color='r', label='Train_loss')
    plt.plot(x, array2, color='b', label='Val_loss')
    plt.legend()
    plt.title('loss of train and val sets in different epoch')

    plt.xlabel('epoch')
    plt.ylabel('loss: ')
    plt.savefig("/content/drive/MyDrive/bhanu/loss_curves")
    plt.show()
    plt.clf()


print(device)

model = config1()
model.to(device)
loss_function = nn.CrossEntropyLoss()
optimizer = optim.AdamW(model.parameters(), lr=0.01)
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer,patience=4,factor=0.1)

# Training

best_acc = 0.0
save_path = '/content/drive/MyDrive/bhanu/resNetModel.pth'

since = time.time()
for epoch in range(epochs):
    
    model.train()
    running_loss = 0.0
    running_corrects = 0
    for step, data in enumerate(train_loader, start=0):
        images, labels = data
        optimizer.zero_grad()
        logits = model(images.to(device))
        loss = loss_function(logits, labels.to(device))
        _, predict_y = torch.max(logits, dim=1)
        loss.backward()
        optimizer.step()

        running_loss += loss.item()
        running_corrects += (predict_y == labels.to(device)).float().sum().item()
        rate = (step+1)/len(train_loader)
        a = "*" * int(rate * 50)
        b = "." * int((1 - rate) * 50)
        print("\rtrain loss: {:^3.0f}%[{}->{}]{:.4f}".format(int(rate*100), a, b, loss), end="")
    print()
    accurate_train = running_corrects / train_num
    train_loss.append(running_loss / len(train_loader))
    train_acc.append(accurate_train)

    model.eval()
    acc = 0.0  
    Loss_val = 0.0
    with torch.no_grad():
        for data_val in validate_loader:
            val_images, val_labels = data_val
            outputs = model(val_images.to(device))  
            loss_val = loss_function(outputs, val_labels.to(device))
            Loss_val += loss_val.item()
            predict_y = torch.max(outputs, dim=1)[1]
            acc += (predict_y == val_labels.to(device)).float().sum().item()
        val_accurate = acc / val_num
        val_acc.append(val_accurate)
        if val_accurate > best_acc:
            best_acc = val_accurate
            torch.save(model.state_dict(), save_path)
        print('[epoch %d] train_loss: %.3f  val_accuracy: %.3f train_accuracy: %.3f' %
              (epoch + 1, running_loss / step, val_accurate,accurate_train))
        val_loss.append(Loss_val / len(validate_loader))
    scheduler.step(loss_val)
time_elapsed = time.time() - since

valid_data_label=[]
for i, j in validate_dataset:
  valid_data_label.append(j)
valid_data_label_tensor= torch.FloatTensor(valid_data_label)
time_elapsed = time.time() - since

val_preds = get_all_preds(model, validate_loader).cpu()
gts = valid_data_label_tensor
preds = val_preds.argmax(dim=1)
gts_np = np.array(gts)
preds_np = np.array(preds)
mis_idxes = list(np.where(gts_np!= preds_np)[0])
candidates = random.sample(mis_idxes,25)
conf_matrix = confusion_matrix(valid_data_label_tensor, val_preds.argmax(dim=1))

plot_confusion_matrix(conf_matrix, classes)
print('Training complete in {:.0f}m {:.0f}s'.format(
        time_elapsed // 60, time_elapsed % 60))
print('Best val Acc: {:4f}'.format(best_acc))

test_np=gts_np.astype(int)

test_np=gts_np.astype(int)
plot_misclf_imgs(candidates,test_np,preds_np,classes)

plot_acc_curves(train_acc,val_acc)

plot_loss_curves(train_loss,val_loss)

import pandas as pd
import seaborn as sns
df_cm = pd.DataFrame(conf_matrix/np.sum(conf_matrix) *10, index = [i for i in classes],
                     columns = [i for i in classes])
plt.figure(figsize = (12,7))
sns.heatmap(df_cm, annot=True)
plt.title("ResNet34")
plt.savefig('output.png')

#model = torch.load('/content/resNetModel.pth')
model = config1()
model.load_state_dict(torch.load('/content/drive/MyDrive/bhanu/resNetModel.pth'))

num_test_samples = 10000
correct = 0 

model.eval().cuda()

with  torch.no_grad():
    for inputs, labels in test_loader:
        inputs, labels = inputs.to(device), labels.to(device)
        # Make predictions.
        prediction= model(inputs)

        # Retrieve predictions indexes.
        _, predicted_class = torch.max(prediction.data, 1)

        # Compute number of correct predictions.
        correct += (predicted_class == labels).float().sum().item()

test_accuracy = correct / num_test_samples

print('Test accuracy: {}'.format(test_accuracy))

"""RESNET 18"""

def config1(num_classes=10, include_top=True):
    return ResNet(BasicBlock, [2, 2, 2, 2], num_classes=num_classes, include_top=include_top)

# Trained for number of epochs:
epochs = 10


train_num = len(train_data)
val_num = len(validate_dataset)

train_acc = []
val_acc = []
train_loss = []
val_loss = []

model = config1()
model.to(device)
loss_function = nn.CrossEntropyLoss()
optimizer = optim.AdamW(model.parameters(), lr=0.01)
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer,patience=4,factor=0.1)

# Training

best_acc = 0.0
save_path = './resNetModel_18.pth'

"""**Training RESNET18**"""

since = time.time()
for epoch in range(epochs):
    
    model.train()
    running_loss = 0.0
    running_corrects = 0
    for step, data in enumerate(train_loader, start=0):
        images, labels = data
        images=images.to(device)
        labels=labels.to(device)
        optimizer.zero_grad()
        logits = model(images)
        loss = loss_function(logits, labels)
        _, predict_y = torch.max(logits, dim=1)
        loss.backward()
        optimizer.step()

        running_loss += loss.item()
        running_corrects += (predict_y == labels).float().sum().item()
        rate = (step+1)/len(train_loader)
        a = "*" * int(rate * 50)
        b = "." * int((1 - rate) * 50)
        print("\rtrain loss: {:^3.0f}%[{}->{}]{:.4f}".format(int(rate*100), a, b, loss), end="")
    print()
    accurate_train = running_corrects / train_num
    train_loss.append(running_loss / len(train_loader))
    train_acc.append(accurate_train)

    model.eval()
    acc = 0.0  
    Loss_val = 0.0
    with torch.no_grad():
        for data_val in validate_loader:
            val_images, val_labels = data_val
            val_images=val_images.to(device)
            val_labels=val_labels.to(device)
            outputs = model(val_images)  
            loss_val = loss_function(outputs, val_labels)
            Loss_val += loss_val.item()
            predict_y = torch.max(outputs, dim=1)[1]
            acc += (predict_y == val_labels).float().sum().item()
        val_accurate = acc / val_num
        val_acc.append(val_accurate)
        if val_accurate > best_acc:
            best_acc = val_accurate
            torch.save(model.state_dict(), save_path)
        print('[epoch %d] train_loss: %.3f  val_accuracy: %.3f train_accuracy: %.3f' %
              (epoch + 1, running_loss / step, val_accurate,accurate_train))
        val_loss.append(Loss_val / len(validate_loader))
    scheduler.step(loss_val)
time_elapsed = time.time() - since

valid_data_label=[]
for i, j in validate_dataset:
  valid_data_label.append(j)
valid_data_label_tensor= torch.FloatTensor(valid_data_label)
time_elapsed = time.time() - since

val_preds = get_all_preds(model, validate_loader).cpu()
gts = valid_data_label_tensor
preds = val_preds.argmax(dim=1)
gts_np = np.array(gts)
preds_np = np.array(preds)
mis_idxes = list(np.where(gts_np!= preds_np)[0])
candidates = random.sample(mis_idxes,25)
conf_matrix = confusion_matrix(valid_data_label_tensor, val_preds.argmax(dim=1))

plot_confusion_matrix(conf_matrix, classes)
print('Training complete in {:.0f}m {:.0f}s'.format(
        time_elapsed // 60, time_elapsed % 60))
print('Best val Acc: {:4f}'.format(best_acc))

test_np=gts_np.astype(int)
plot_misclf_imgs(candidates,test_np,preds_np,classes)

"""**Plotting accuracy **"""

plot_acc_curves(train_acc,val_acc)

"""**Plotting Loss**"""

plot_loss_curves(train_loss,val_loss)

import pandas as pd
import seaborn as sns
df_cm = pd.DataFrame(conf_matrix/np.sum(conf_matrix) *10, index = [i for i in classes],
                     columns = [i for i in classes])
plt.figure(figsize = (12,7))
sns.heatmap(df_cm, annot=True)
plt.title("ResNet18")
plt.savefig('/content/drive/MyDrive/bhanu/output.png')

num_test_samples = 10000
correct = 0 

model.eval().cuda()

with  torch.no_grad():
    for inputs, labels in test_loader:
        inputs, labels = inputs.to(device), labels.to(device)
        # Make predictions.
        prediction= model(inputs)

        # Retrieve predictions indexes.
        _, predicted_class = torch.max(prediction.data, 1)

        # Compute number of correct predictions.
        correct += (predicted_class == labels).float().sum().item()

test_accuracy = correct / num_test_samples

print('Test accuracy: {}'.format(test_accuracy))

!nvidia-smi
