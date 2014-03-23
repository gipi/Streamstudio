# -*- mode: ruby -*-
# vi: set ft=ruby :

# Vagrantfile API/syntax version. Don't touch unless you know what you're doing!
VAGRANTFILE_API_VERSION = "2"

$script = <<SCRIPT
echo ********************
echo I am provisioning...
echo ********************
apt-get update
aptitude install -y ubuntu-minimal xfce4 gdm virtualbox-guest-x11
aptitude install -y  gobject-introspection python-gi gir1.2-gtk-3.0 gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0
aptitude install -y gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good
SCRIPT

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = "streamstudio"
  config.vm.box_url = "https://dl.dropboxusercontent.com/s/xymcvez85i29lym/vagrant-debian-wheezy64.box"

  config.vm.provision :shell, :inline => $script

  config.vm.provider :virtualbox do |vb|
    # Don't boot with headless mode
    vb.gui = true

   # Use VBoxManage to customize the VM. For example to change memory:
   vb.customize ["modifyvm", :id, "--memory", "1024"]
  end
  #
end
