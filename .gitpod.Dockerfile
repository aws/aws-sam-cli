FROM gitpod/workspace-full

# Install custom tools, runtimes, etc.
# For example "bastet", a command-line tetris clone:
# RUN brew install bastet
#
# More information: https://www.gitpod.io/docs/config-docker/
ENV PYENV_VIRTUALENV_DISABLE_PROMPT=1
RUN pyenv install 3.6.8
RUN pyenv install 3.7.2
RUN pyenv local 3.6.8 3.7.2
RUN pyenv virtualenv 3.7.2 samcli37
RUN pyenv activate samcli37
RUN pip install black
RUN pip install pylint