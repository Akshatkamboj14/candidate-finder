#!/bin/bash

set -e

sudo hostnamectl set-hostname master

if [ -f /etc/kubernetes/admin.conf ]; then
  echo "Cluster already initialized; skipping kubeadm init"
else
  sudo kubeadm init --cri-socket=unix:///var/run/crio/crio.sock
  
  # Configure kubeconfig for ubuntu user
  sudo mkdir -p /home/ubuntu/.kube
  sudo cp /etc/kubernetes/admin.conf /home/ubuntu/.kube/config
  sudo chown ubuntu:ubuntu /home/ubuntu/.kube/config
  
  # Install Weave Net CNI
  sudo -u ubuntu kubectl apply -f https://github.com/weaveworks/weave/releases/download/v2.8.1/weave-daemonset-k8s.yaml
  
  # Wait until node is Ready
  echo "Waiting for node to become Ready..."
  until sudo -u ubuntu kubectl get nodes | grep -q ' Ready '; do
      sleep 5
  done
  
  # Remove control-plane taint
  sudo -u ubuntu kubectl taint node $(hostname) node-role.kubernetes.io/control-plane:NoSchedule- || true
  
  # Wait for kube-system pods
  echo "Waiting for kube-system pods to be Ready..."
  until sudo -u ubuntu kubectl get pods -n kube-system | grep -Ev 'STATUS|Running' | wc -l | grep -q '^0$'; do
      sleep 5
  done
  
  echo "Kubernetes control-plane setup complete."
fi




# echo "Updating package lists..."
# sudo apt update -y
# sudo apt upgrade -y

# # -------------------------------
# # Install Node.js & npm (for React)
# # -------------------------------
# echo "Installing Node.js and npm..."
# # Using NodeSource PPA for latest LTS Node
# curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
# sudo apt install -y nodejs
# echo "Node.js version:"
# node -v
# echo "npm version:"
# npm -v

# # -------------------------------
# # Install Docker
# # -------------------------------
# echo "Installing Docker..."
# sudo apt install -y \
#     ca-certificates \
#     curl \
#     gnupg \
#     lsb-release

# # Add Docker official GPG key
# sudo mkdir -p /etc/apt/keyrings
# curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# # Set up repository
# echo \
#   "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
#   $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# # Install Docker Engine
# sudo apt update -y
# sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# # Enable Docker service
# sudo systemctl enable docker
# sudo systemctl start docker
# sudo usermod -aG docker $USER && newgrp docker

# echo "Docker version:"
# docker --version
# echo "Docker Compose version:"
# docker compose version

# sudo apt install python3.12-venv
# python3 -m venv .venv
