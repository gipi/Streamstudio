from setuptools import setup, find_packages

setup(name='streamstudio',
      version='0.2',
      description='Multimedia application to manage multiple video/audio streams for streaming purpose',
      url='http://github.com/gipi/Streamstudio',
      author='Gianluca Pacchiella, Pier Paolo Pittavino',
      author_email='gp@ktln2.org',
      license='GPLv3',
      packages=find_packages(),
      package_data= {
          'streamstudio.gui': ['glade/*',],
      },
      entry_points = {
          'gui_scripts': [
            'streamstudio = streamstudio:start',
          ]
      },
      zip_safe=False)
