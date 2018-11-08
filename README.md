# :warning: Fairing has moved!:warning: 
 
Fairing is now part of the Kubeflow organisation, the new repository for the project is https://github.com/kubeflow/fairing 


# Fairing

Easily train and serve ML models on Kubernetes, directly from your python code.  

This projects uses [Metaparticle](http://metaparticle.io/) behind the scene.

fairing allows you to express how you want your model to be trained and served using native python decorators.  


## Table of Contents

- [Requirements](#requirements)
- [Getting `fairing`](#getting-fairing)
- [Training](#training)
  - [Simple Training](#simple-training)
  - [Hyperparameters Tuning](#hyperparameters-tuning)
  - [Population Based Training](#population-based-training)
- [Usage with Kubeflow](#usage-with-kubeflow)
  - [Simple TfJob](#simple-tfjob)
  - [Distributed Training](#distributed-training)
  - [From a Jupyter Notebook](#from-a-jupyter-notebook)
- [Monitoring with TensorBoard](#tensorboard)

## Requirements

If you are going to use `fairing` on your local machine (as opposed to from a Jupyter Notebook deployed inside a Kubernetes cluster for example), you will need 
to have access to a deployed Kubernetes cluster, and have the `kubeconfig` for this cluster on your machine.

You will also need to have docker installed locally.

## Getting `fairing`

**Note**: This projects requires python 3

```bash
pip install fairing
```

Or, in a Jupyter Notebook, create a new cell and execute: `!pip install fairing`.

## Training

`fairing` provides a `@Train` class decorator allowing you to specify how you want your model to be packaged and trained.  
Your model needs to be defined as a class to work with `fairing`. 

This limitation is needed in order to enable usage of more complex training strategies and simplify usage from within a Jupyter Notebook.

Following are a series of example that should help you understand how fairing works.
<!-- The train decorator 
* `package`: Defines the repository (this could be your DockerHub username, or something like `somerepo.acr.io` on Azure for example) and name that should be used to build the image. You can control wether you want to publish the image by setting `publish` to `True`.
* `strategy`: Specify which training strategy should be used (more details below).
* `architecture`: Specify which architecture should be used. (more details below)
* `tensorboard`: [Optional] If specified, will spawn an instance of TensorBoard to monitor your trainings
  * `log_dir`: Directory where the summaries are saved.
  * `pvc_name`: Name of an existing `PermanentVolumeClaim` that should be mounted.
  * `public`: If set to `True` then a public IP will be created for TensorBoard (provided your Kubernetes cluster supports this). Otherwise only a private IP will be created. -->

<!-- ### Training Strategies -->

#### Simple Training

Your class needs to define a `train` method that will be called during training:

```python
from fairing.train import Train

@Train(repository='<your-repo-name>')
class MyModel(object):
    def train(self):
      # Training logic goes here

```
<!-- No `strategy` is specified here, since the default `strategy` is `basicTrainingStrategy`. -->

Complete example: [examples/simple-training/main.py](./examples/simple-training/main.py)


#### Hyperparameters Tuning

Allows you to run multiple trainings in parallel, each one with different values for your hyperparameters.

Your class should define a `hyperparameters` method that returns an dictionary of hyperparameters and their values.
This dictionary will be automatically passed to your `train` method. 
Don't forget to add a new argument to your `train` method to received the hyperparameters.

```python
from fairing.train import Train
from fairing.strategies.hp import HyperparameterTuning

@Train(
    repository='<your-repo-name>',
    strategy=HyperparameterTuning(runs=6),
)
class MyModel(object):
    def hyperparameters(self):
      return {
        'learning_rate': random.normalvariate(0.5, 0.45)
      }

    def train(self, hp):
      # Training logic goes here
```

To specify that we wanted to train our model using hyperparameters tuning, and not just a simple training, 
we passed a new `strategy` parameter to the `@Train` decorator, and specified the number of runs we wish to be created.


Complete example: [examples/hyperparameter-tuning/main.py](./examples/hyperparameter-tuning/main.py)

#### Population Based Training

We can also ask `fairing` to train our code using [Population Based Training](https://deepmind.com/blog/population-based-training-neural-networks/).

This is a more advanced training strategies that needs hook into different lifecycle steps of your model, thus we need to define several additional method into our model class.

A multiple read/write PVC name needs to be pass to the `PopulationBasedTraining` strategie. This is used to store and exchange the different models generated by our training to enable the `explore/exploit` mechanism of Population Based Training.

```python
from fairing.train import Train
from fairing.strategies.pbt import PopulationBasedTraining

@Train(
    repository='<your-repo-name>',
    strategy=PopulationBasedTraining(
        population_size=10,
        exploit_count=6,
        steps_per_exploit=5000,
        pvc_name='<pvc-name>',
        model_path = MODEL_PATH
    )
)
class MyModel(object):
    def hyperparameters(self):
      # returns the dictionary of hyperparameters
    
    def build(self, hp):
      # build the model
    
    def train(self, hp):
      # training logic
    
    def save(self):
      # save the model at MODEL_PATH
    
    def restore(self, model_path):
      # restore the model from MODEL_PATH
```

Complete example: [examples/population-based-training/main.py](./examples/population-based-training/main.py)


<!-- ### Training Architectures

#### Basic Architure

This is the default `architecture`, each training run will be a single container acting in isolation.
No `architecure` is specified since this is the default value.

```python
# Note: we are note specifiying any architecture since this is the default value
@Train(package={'name': '<your-image-name>', 'repository': '<your-repo-name>', 'publish': True})
class MyModel(object):
    ...
```

Complete example: [examples/simple-training/main.py](./examples/simple-training/main.py) -->

## Usage with Kubeflow

### Simple TfJob

Instead of creating native `Jobs`, `fairing` can leverage Kubeflow's `TfJobs` assuming you have Kubeflow installed in your cluster.
Simply pass the Kubeflow architecture to the train decorator (note that you can still use all the training strategies mentionned above):

```python
from fairing.train import Train
from fairing.architectures.kubeflow.basic import BasicArchitecture

@Train(repository='wbuchwalter', architecture=BasicArchitecture())
class MyModel(object):
    def train(self):
       # training logic
```


### Distributed Training

Using Kubeflow, we can also ask `fairing` to start [distributed trainings](https://www.tensorflow.org/deploy/distributed) instead.
Simply import `DistributedTraining` architecture insteda of the `BasicArchitecture`:

```python
from fairing.train import Train
from fairing.architectures.kubeflow.distributed import DistributedTraining

@Train(
    repository='<your-repo-name>',
    architecture=DistributedTraining(ps_count=2, worker_count=5),
)
class MyModel(object):
    ...
```

Specify the number of desired parameter servers with `ps_count` and the number of workers with `worker_count`.
Another instance of type master will always be created.

See [https://github.com/Azure/kubeflow-labs/tree/master/7-distributed-tensorflow#modifying-your-model-to-use-tfjobs-tf_config](https://github.com/Azure/kubeflow-labs/tree/master/7-distributed-tensorflow#modifying-your-model-to-use-tfjobs-tf_config) to understand how you need to modify your model to support distributed training with Kubeflow.

Complete example: [examples/distributed-training/main.py](./examples/distributed-training/main.py)

### From a Jupyter Notebook

To make `fairing` work from a Jupyter Notebook deployed with Kubeflow, a few more requirements are needed (such as Knative Build deployed).
Refer [to the dedicated documentation and example](examples/kubeflow-jupyter-notebook/).

## TensorBoard

You can easily attach a TensorBoard instance to monitor your training:

```python
@Train(
    repository='<your-repo-name>',
    tensorboard={
      'log_dir': LOG_DIR,
      'pvc_name': '<pvc-name>',
      'public': True # Request a public IP
    }
)
class MyModel(object):
    ...
```
