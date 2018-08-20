import signal
import sys
import types
import logging
import shutil

# from fairing.backend import get_backend, Native
from fairing.docker import DockerBuilder
from fairing.utils import is_runtime_phase
from fairing.options import TensorboardOptions, PackageOptions
from fairing.architectures.native.basic import BasicArchitecture
from fairing.strategies.basic import BasicTrainingStrategy
from fairing.metaparticle import MetaparticleClient

logger = logging.getLogger('fairing')


class Trainer(object):
    def __init__(self,
                 package,
                 tensorboard=None,
                 architecture=BasicArchitecture(),
                 strategy=BasicTrainingStrategy(),
                 builder=DockerBuilder()):
        self.strategy = strategy
        self.architecture = architecture
        self.tensorboard_options = TensorboardOptions(
            **tensorboard) if tensorboard else None
        self.package = PackageOptions(**package)
        self.backend = self.architecture.get_associated_backend()
        self.strategy.set_architecture(self.architecture)
        self.image = self.get_image()
        self.builder = builder

    def get_image(self):
        return "{repo}/{name}:latest".format(
            repo=self.package.repository,
            name=self.package.name
        )

    def compile_ast(self):
        svc = {
            "name": self.package.name,
            "guid": 1234567
        }

        volumes = None
        volume_mounts = None
        if self.tensorboard_options:
            svc, volumes, volume_mounts = self.backend.add_tensorboard(
                svc, self.package.name, self.tensorboard_options)

        svc, env = self.strategy.add_training(
            svc, self.image, self.package.name, volumes, volume_mounts)
        return svc, env
    
    def get_metaparticle_client(self):
        return MetaparticleClient()

    def deploy_training(self):
        ast, env = self.compile_ast()

        self.builder.write_dockerfile(self.package, env)
        self.builder.build(self.image)

        if self.package.publish:
            self.builder.publish(self.image)
        
        mp = self.get_metaparticle_client()

        def signal_handler(signal, frame):
            mp.cancel(self.package.name)
            sys.exit(0)
        signal.signal(signal.SIGINT, signal_handler)
        mp.run(ast)
        
        print("Training(s) launched.")

        mp.logs(self.package.name)

    def start_training(self, user_class):
        self.strategy.exec_user_code(user_class)

# @Train decorator
class Train(object):
    def __init__(self, package, tensorboard=None, architecture=BasicArchitecture(), strategy=BasicTrainingStrategy()):
        self.trainer = Trainer(package, tensorboard, architecture, strategy)

    def __call__(self, cls):
        class UserClass(cls):
            # self refers to the Train instance
            # user_class is equivalentto self in the UserClass instance
            def __init__(user_class):
                user_class.is_training_initialized = False

            def __getattribute__(user_class, attribute_name):
                # Overriding train in order to minimize the changes necessary in the user
                # code to go from local to remote execution.
                # That way, by simply commenting or uncommenting the Train decorator
                # Model.train() will execute either on the local setup or in kubernetes
                
                if attribute_name != 'train' or user_class.is_training_initialized:
                    return super(UserClass, user_class).__getattribute__(attribute_name)

                if attribute_name == 'train' and not is_runtime_phase():
                    return super(UserClass, user_class).__getattribute__('_deploy_training')

                print(type(self))
                print(type(user_class))
                user_class.is_training_initialized = True
                self.trainer.start_training(user_class)
                return super(UserClass, user_class).__getattribute__('_noop_attribute')
            
            def _noop_attribute(user_class):
                pass

            def _deploy_training(user_class):
                self.trainer.deploy_training()


        return UserClass