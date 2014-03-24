# -*- mode: ruby -*-
# vi: set ft=ruby :

# Vagrantfile API/syntax version. Don't touch unless you know what you're doing!
VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = "streamstudio"
  config.vm.box_url = "https://dl.dropboxusercontent.com/s/xymcvez85i29lym/vagrant-debian-wheezy64.box"

  config.vm.provision :ansible do |ansible|
    ansible.playbook = "provision/streaming.yml"
    # On Vagrant < 1.3 this used to be `inventory_file`...
    # ansible.inventory_file = "provisioning/hosts-vagrant"
    ansible.verbose = 'v'
    ansible.host_key_checking = false
  end

  config.vm.provider :virtualbox do |vb|
    # Don't boot with headless mode
    vb.gui = false

   # Use VBoxManage to customize the VM. For example to change memory:
   vb.customize ["modifyvm", :id, "--memory", "1024"]
  end
  #
end
