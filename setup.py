from setuptools import setup

setup(name='streamstudio',
      version='0.2',
      description='Multimedia application to manage multiple video/audio streams for streaming purpose',
      url='http://github.com/gipi/Streamstudio',
      author='Gianluca Pacchiella, Pier Paolo Pittavino',
      author_email='gp@ktln2.org',
      license='GPLv3',
      packages=['streamstudio'],
      entry_points = {
          'gui_scripts': [
            'streamstudio = streamstudio:start',
          ]
      },
      zip_safe=False)
