#! /bin/bash

#Sets up docker, nvidia docker git-lfs and rocker which are used to clone and setup docker containers

#COPIED FROM OFFICIAL DOCKER INSTALL INSTRUCTIONS
# https://docs.docker.com/engine/install/ubuntu/

#remove incorrect docker
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do sudo apt-get remove $pkg; done

# Add Docker's official GPG key:
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update

# Install docker
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
#END OFFICIAL DOCKER INSTALL



#INSTALL NVIDIA DOCKER 
#https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update
sudo apt install -y nvidia-docker2 nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

sudo apt install -y git-lfs

#Install rocker and rocker extensions which are used to launch the devcontainer
# pip install rocker off-your-rocker git+https://github.com/blooop/deps_rocker

echo "testing docker install"

docker run hello-world

echo "you may need to restart your machine"

echo "you may need to add this to /etc/docker/daemon.json"
echo "cat /etc/docker/daemon.json 
{
    "runtimes": {
        "nvidia": {
            "args": [],
            "path": "nvidia-container-runtime"
        }
    }
"


#INSTALL PIXI
curl -fsSL https://pixi.sh/install.sh | bash
echo 'eval "$(pixi completion --shell bash)"' >> ~/.bashrc

#INSTALL UV
curl -LsSf https://astral.sh/uv/install.sh | sh

sudo groupadd docker
sudo usermod -aG docker $USER
newgrp docker || true
