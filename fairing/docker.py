import shutil
import os
import json
import logging
import sys

from docker import APIClient
from fairing.notebook import get_notebook_name, is_in_notebook

logger = logging.getLogger('fairing')


def get_exec_file_name():
    exec_file = sys.argv[0]
    slash_ix = exec_file.find('/')
    if slash_ix != -1:
        exec_file = exec_file[slash_ix + 1:]
    return exec_file


class DockerBuilder:
    def __init__(self):
        self.docker_client = None
    
    def get_base_image(self):
        if os.environ.get('FAIRING_DEV', None) != None:
            try:
                uname =  os.environ['FAIRING_DEV_DOCKER_USERNAME']
            except KeyError:
                raise KeyError("FAIRING_DEV environment variable is defined but "
                                "FAIRING_DEV_DOCKER_USERNAME is not. Either set " 
                                "FAIRING_DEV_DOCKER_USERNAME to your Docker hub username, "
                                "or set FAIRING_DEV to false.")
            return '{uname}/fairing:latest'.format(uname=uname)
        return 'library/python:3.6'

    def generate_dockerfile_content(self, env):
        # executor = 'python'
        extra_install_steps = ''
        exec_file = get_exec_file_name()

        if is_in_notebook():
            nb_name = get_notebook_name()
            extra_install_steps = ("RUN pip install jupyter nbconvert\n"
                                   "RUN jupyter nbconvert --to script /app/{}\n").format(nb_name)

            exec_file = nb_name.replace('.ipynb', '.py')

        env = env if env else []
        env_str = ""
        for e in env:
            env_str += "ENV {} {}\n".format(e['name'], e['value'])

        return ("FROM {base_image}\n"
                "ENV FAIRING_RUNTIME 1\n"
                "COPY ./ /app/\n"
                "RUN pip install --no-cache -r /app/requirements.txt\n"
                "{extra_install_steps}"
                "{env_str}"
                "CMD python /app/{exec_file}").format(                   
                    base_image=self.get_base_image(),
                    exec_file=exec_file,
                    env_str=env_str,
                    extra_install_steps=extra_install_steps)

    def write_dockerfile(self, package, env):
        if hasattr(package, 'dockerfile') and package.dockerfile is not None:
            shutil.copy(package.dockerfile, 'Dockerfile')
            return       

        content = self.generate_dockerfile_content(env)
        with open('Dockerfile', 'w+t') as f:
            f.write(content)

    def build(self, img, path='.'):
        print('Building docker image {}...'.format(img))
        if self.docker_client is None:
            self.docker_client = APIClient(version='auto')

        bld = self.docker_client.build(
            path=path,
            tag=img,
            encoding='utf-8'
        )

        for line in bld:
            self._process_stream(line)

    def publish(self, img):
        print('Publishing image {}...'.format(img))
        if self.docker_client is None:
            self.docker_client = APIClient(version='auto')

        # TODO: do we need to set tag?
        for line in self.docker_client.push(img, stream=True):
            self._process_stream(line)

    def _process_stream(self, line):
        raw = line.decode('utf-8').strip()
        lns = raw.split('\n')
        for ln in lns:
            # try to decode json
            try:
                ljson = json.loads(ln)

                if ljson.get('error'):
                    msg = str(ljson.get('error', ljson))
                    logger.error('Build failed: ' + msg)
                    raise Exception('Image build failed: ' + msg)
                else:
                    if ljson.get('stream'):
                        msg = 'Build output: {}'.format(
                            ljson['stream'].strip())
                    elif ljson.get('status'):
                        msg = 'Push output: {} {}'.format(
                            ljson['status'],
                            ljson.get('progress')
                        )
                    elif ljson.get('aux'):
                        msg = 'Push finished: {}'.format(ljson.get('aux'))
                    else:
                        msg = str(ljson)
                    logger.info(msg)

            except json.JSONDecodeError:
                logger.warning('JSON decode error: {}'.format(ln))