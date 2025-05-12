#!/bin/bash

echo "🔧 Installing required packages for PyQt6 graphics support..."

# Update package lists
sudo apt update

# Install mesa drivers (for OpenGL + software fallback)
sudo apt install -y \
  libgl1-mesa-dri \
  libgl1-mesa-glx \
  libegl1 \
  libegl-mesa0 \
  mesa-utils

# Install Vulkan support (optional, but helps Qt)
sudo apt install -y \
  libvulkan1 \
  vulkan-tools \
  vulkan-validationlayers

# Install XWayland for compatibility with Wayland
sudo apt install -y xwayland

# (Optional) Install tools to verify graphics environment
sudo apt install -y glxinfo inxi

# Confirm completion
echo "✅ Done. You may want to log out and switch to an X11 session if you're using Wayland."
echo "   To test graphics rendering, run: glxinfo | grep 'OpenGL'"
